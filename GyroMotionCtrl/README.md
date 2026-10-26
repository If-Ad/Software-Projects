# 🎮 GyroMotionCtrl

A creative software integration project that transforms a standard smartphone into a wireless motion-tracking gamepad. This project bypasses the need for physical hardware microcontrollers (like Arduino or ESP32) by leveraging a phone's built-in gyroscope, accelerometer, and local Wi-Fi networking to control platformer games like Super Mario.

---

## ✨ Features

* **Hardware-Free Prototyping:** Uses a smartphone's existing IMU sensors instead of purchasing separate hardware sensor modules[cite: 1].
* **Real-Time Data Streaming:** Transmits sensor coordinates and tilt data over a local IP network via UDP/TCP[cite: 1].
* **Cross-Platform Bridge:** A custom receiver script on the computer catches the incoming mobile data and maps it into keyboard/emulator inputs.
* **Low-Latency Wireless Control:** Smooth responsiveness for controlling retro games wirelessly.

## ⚙️ Setup & Installation

Follow these steps to connect your smartphone sensors to your computer:

> 📌 **Prerequisite:** Your smartphone **must have a built-in hardware Gyroscope sensor** for motion tracking to work properly.

### 1. Network Requirements
* Ensure both your **computer and smartphone are connected to the same Wi-Fi network**.

### 2. Find Your Computer's Local IP Address
* **On Windows:** 
  1. Open the Command Prompt (`cmd`).
  2. Type `ipconfig` and press Enter.
  3. Look for your active network adapter and note down the **IPv4 Address** (e.g., `192.168.x.x`).
* **On Mac / Linux:** 
  1. Open your terminal.
  2. Type `ifconfig` (or `ip a` on Linux) and press Enter.
  3. Note down your local IPv4 address.

### 3. Configure the Mobile App
1. Open your sensor streaming app on your smartphone.
2. Locate the **Remote Address** settings.
3. Enter your computer's local IPv4 address that you noted down in Step 2.
4. Select/enable **Gyroscope** and **Accelerometer** as your active sensors in the app.

### 4. Run & Play
1. Start your desktop receiver script or program.
2. Tap **Start** on your phone's streaming app to begin transmitting sensor data over your local network[cite: 1].
3. Tilt and move your phone to control the game!
