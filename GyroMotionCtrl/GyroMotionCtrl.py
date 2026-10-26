"""
Hybrid SensaGram -> Virtual Xbox Controller (vgamepad)
WITH BUTTON B: Upward phone acceleration = press B

Sensors:
  - accelerometer: absolute tilt (stick) + upward acceleration (Button B)
  - gyroscope: flick boost + yaw

Controls:
  Left stick X = Roll
  Left stick Y = Pitch (top-down = forward)
  Right stick Y = Yaw/Rudder (twist phone)
  Button B = Press when phone accelerates upward

Console keys: c=centre  q=quit  [ ]=gyro gain
"""

import socket
import json
import math
import select
import time
from collections import deque

import vgamepad as vg

try:
    import msvcrt
    HAVE_CONSOLE = True
except ImportError:
    HAVE_CONSOLE = False

# --------------------------------------------------------------------------
# TUNING
# --------------------------------------------------------------------------
UDP_IP = "0.0.0.0"
UDP_PORT = 8080

ACCEL_RANGE = 7.0
ACCEL_GAIN = 1.0
GYRO_GAIN = 0.9
GYRO_TAU = 0.18
YAW_GAIN = 1.6
YAW_TAU = 1.2
DEADZONE = 0.03

ROLL_SIGN = -1.0
PITCH_SIGN = 1.0

SMOOTH_WINDOW = 5

# ---- Button B (upward acceleration) tuning ----
UP_ACCEL_INDEX = 1          # accelerometer axis for upward movement (0=X, 1=Y, 2=Z)
PRESS_THRESHOLD = 4.0       # m/s^2: press B when upward accel exceeds this
RELEASE_THRESHOLD = 2.0     # m/s^2: release B when below this (hysteresis)
LONG_PRESS_TIME = 1.0       # seconds: phone held up this long = long press B

# --------------------------------------------------------------------------
# Virtual controller + UDP socket
# --------------------------------------------------------------------------
gamepad = vg.VX360Gamepad()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind((UDP_IP, UDP_PORT))
except OSError as exc:
    print(f"[WARN] Bind to {UDP_IP}:{UDP_PORT} failed: {exc}")
    sock.bind(("127.0.0.1", UDP_PORT))

bound = sock.getsockname()
print(f"[OK] Listening on {bound[0]}:{bound[1]}")
if bound[0] == "127.0.0.1":
    print("[WARN] Localhost only. Run as Admin for LAN.")
else:
    print(f"[OK] Send to {bound[0]}:{bound[1]}")
print("[OK] Controls: Left stick=roll/pitch  Right stick=yaw  Button B=phone-up")
print("[OK] Keys: c=center  q=quit  [ ]=gyro gain")
print("-" * 60)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def map_range(value, in_min, in_max, out_min=-1.0, out_max=1.0):
    if in_max == in_min: return 0.0
    clamped = max(min(value, in_max), in_min)
    return (clamped - in_min) / (in_max - in_min) * (out_max - out_min) + out_min

def clamp(value, low=-1.0, high=1.0):
    return max(low, min(high, value))

def apply_deadzone(value, dz=DEADZONE):
    if abs(value) < dz: return 0.0
    s = 1.0 if value > 0 else -1.0
    return s * (abs(value) - dz) / (1.0 - dz)

def classify(name):
    if not name: return None
    n = str(name).lower()
    return "gyro" if "gyro" in n else ("accel" if "accel" in n else None)

def extract_sensors(p):
    found = []
    st = p.get("sensor") or p.get("type")
    sv = p.get("values")
    if st and isinstance(sv, list):
        found.append((st, sv))
    for k in ("sensors","data","sensorData"):
        b = p.get(k)
        if isinstance(b, dict):
            for name, vals in b.items():
                if isinstance(vals, list) and vals:
                    found.append((name, vals))
    return found


# --------------------------------------------------------------------------
# Control state
# --------------------------------------------------------------------------
accel_buf = deque(maxlen=SMOOTH_WINDOW)
base_roll = base_pitch = 0.0
center_roll = center_pitch = 0.0
boost_roll = boost_pitch = yaw_pos = 0.0

# Button B state
b_pressed = False
b_press_start = 0.0
b_long_reported = False

last_rx = time.time(); last_print = 0.0; last_packet = time.time()
have_accel = have_gyro = False
accel_roll_raw = accel_pitch_raw = 0.0

def reset_sticks():
    gamepad.left_joystick_float(0.0, 0.0)
    gamepad.right_joystick_float(0.0, 0.0)
    gamepad.update()

def release_b():
    global b_pressed, b_long_reported
    if b_pressed:
        b_pressed = False
        gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
        b_long_reported = False
        print("[B] Released")

print("Waiting for SensaGram...")

try:
    while True:
        # --- keyboard input (non-blocking) ---
        if HAVE_CONSOLE and msvcrt.kbhit():
            try:
                k = msvcrt.getch().decode("utf-8", "ignore").lower()
            except Exception:
                k = ""
            if k == "q":
                print("\nStopping.")
                break
            elif k == "c":
                center_roll = accel_roll_raw
                center_pitch = accel_pitch_raw
                print(f"[OK] Centre set (r={center_roll:.2f} p={center_pitch:.2f})")
            elif k == "]":
                GYRO_GAIN = min(GYRO_GAIN + 0.1, 3.0)
                print(f"[OK] Gyro gain = {GYRO_GAIN:.1f}")
            elif k == "[":
                GYRO_GAIN = max(GYRO_GAIN - 0.1, 0.0)
                print(f"[OK] Gyro gain = {GYRO_GAIN:.1f}")

        # --- wait for UDP packet (timeout lets us decay boost continuously) ---
        ready, _, _ = select.select([sock], [], [], 0.01)
        now = time.time()
        dt = min(now - last_rx, 0.1)
        last_rx = now

        received = False
        if ready:
            try:
                data, _ = sock.recvfrom(4096)
            except OSError:
                data = None
            if data:
                received = True
                last_packet = now
                try:
                    payload = json.loads(data.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    payload = None

                if payload:
                    for name, values in extract_sensors(payload):
                        kind = classify(name)
                        if kind is None or len(values) < 3:
                            continue
                        vx, vy, vz = float(values[0]), float(values[1]), float(values[2])

                        if kind == "accel":
                            accel_buf.append((vx, vy))
                            ax = sum(p[0] for p in accel_buf) / len(accel_buf)
                            ay = sum(p[1] for p in accel_buf) / len(accel_buf)
                            accel_roll_raw = ax
                            accel_pitch_raw = ay
                            base_roll = apply_deadzone(map_range(ax - center_roll, -ACCEL_RANGE, ACCEL_RANGE))
                            base_pitch = apply_deadzone(map_range(ay - center_pitch, -ACCEL_RANGE, ACCEL_RANGE))

                            # ---- Button B: upward acceleration ----
                            up_val = [vx, vy, vz][UP_ACCEL_INDEX]
                            if up_val > PRESS_THRESHOLD:
                                if not b_pressed:
                                    b_pressed = True
                                    b_press_start = now
                                    b_long_reported = False
                                    gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                                    print("[B] PRESSED")
                            elif up_val < RELEASE_THRESHOLD:
                                if b_pressed:
                                    release_b()

                            have_accel = True

                        elif kind == "gyro":
                            boost_roll += vx * GYRO_GAIN * dt
                            boost_pitch += vy * GYRO_GAIN * dt
                            yaw_pos += vz * YAW_GAIN * dt
                            have_gyro = True

        # --- decay transient boost even when no packet arrives ---
        if not received:
            decay = math.exp(-dt / GYRO_TAU)
            boost_roll *= decay
            boost_pitch *= decay
            yaw_pos *= math.exp(-dt / YAW_TAU)

        # --- Button B long press detection ---
        if b_pressed:
            hold = now - b_press_start
            if hold > LONG_PRESS_TIME and not b_long_reported:
                b_long_reported = True
                print(f"[B] LONG PRESS ({hold:.1f}s)")

        # --- combine stick outputs ---
        roll = clamp((base_roll + boost_roll) * ROLL_SIGN)
        pitch = clamp((base_pitch + boost_pitch) * PITCH_SIGN)
        yaw = clamp(yaw_pos)

        if have_accel or have_gyro:
            gamepad.left_joystick_float(x_value_float=roll, y_value_float=pitch)
            gamepad.right_joystick_float(0.0, yaw)
            gamepad.update()

            if now - last_print > 0.1:
                last_print = now
                src = ("A" if have_accel else "-") + ("G" if have_gyro else "-")
                b_state = "B" if b_pressed else "-"
                print(f"[{src}{b_state}] roll={roll:+.3f} pitch={pitch:+.3f} yaw={yaw:+.3f} "
                      f"(base r={base_roll:+.3f} p={base_pitch:+.3f})")

        # --- safety: reset if phone stops streaming ---
        if now - last_packet > 1.5:
            if have_accel or have_gyro or b_pressed:
                print("[WARN] Stream timeout - resetting")
                reset_sticks()
                release_b()
                base_roll = base_pitch = 0.0
                boost_roll = boost_pitch = yaw_pos = 0.0
                have_accel = have_gyro = False

except KeyboardInterrupt:
    print("\nStopping.")

finally:
    reset_sticks()
    release_b()
    print("[OK] Sticks reset. Bye.")