# 🎮 GyroLink: Smartphone Motion Controller

A creative software integration project that transforms a standard smartphone into a wireless motion-tracking gamepad[cite: 1]. This project bypasses the need for physical hardware microcontrollers (like Arduino or ESP32) by leveraging a phone's built-in gyroscope, accelerometer, and local Wi-Fi networking to control desktop games like Super Mario[cite: 1].

---

## ✨ Features

* **Hardware-Free Prototyping:** Uses a smartphone's existing IMU sensors instead of purchasing separate hardware sensor modules[cite: 1].
* **Real-Time Data Streaming:** Transmits sensor coordinates and tilt data over a local IP network via UDP/TCP[cite: 1].
* **Cross-Platform Bridge:** A custom receiver script on the computer catches the incoming mobile data and maps it into keyboard/emulator inputs.
* **Low-Latency Wireless Control:** Smooth responsiveness for controlling retro games wirelessly.
