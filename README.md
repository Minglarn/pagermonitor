# PagerMonitor

PagerMonitor is a Dockerized, all-in-one Software Defined Radio (SDR) application designed to intercept, decode, and monitor POCSAG pager traffic (like Minicall). It features a sleek, real-time web dashboard, dynamic settings management, and an alias system to replace raw CapCodes with readable names or mute unwanted spam.

## Features
*   **SDR Integration**: Built-in support for RTL-SDR (`rtl_fm`) via USB passthrough.
*   **Message Decoding**: Uses `multimon-ng` to decode POCSAG512, 1200, and 2400 messages.
*   **Real-Time Dashboard**: A premium, "glassmorphism" styled web UI that displays incoming messages instantly using Server-Sent Events (SSE).
*   **CapCode Aliases & Muting**: Map cryptic addresses to readable names (e.g., "Fire Station City"), or explicitly mute specific addresses so they don't clutter the history or database.
*   **Dynamic Settings UI**: Change frequencies (e.g., 169.8M) and RF gain on the fly without restarting the entire Docker container.
*   **MQTT Integration**: Automatically forwards decoded and unmuted messages to a local MQTT broker (e.g., Home Assistant).
*   **Swedish Character Support**: Automatically cleans up and translates specific pager characters to Å, Ä, and Ö, and handles `<CR><LF>` line breaks correctly.

## Architecture
The application runs entirely within a single Docker container, compiled from source for maximum compatibility and minimal footprint:
1.  **Flask Backend**: Serves the API, Web UI, and SSE streams.
2.  **SDR Processor**: A background thread that spins up `rtl_fm | multimon-ng`, pipes the output, formats it, and stores it in SQLite.
3.  **SQLite Database**: A local `messages.db` handles settings, aliases, and message history.

## Setup & Run (Docker Compose)
To run PagerMonitor, simply use the provided `docker-compose.yml`. 

1. Create a `.env` file and set your MQTT password:
   ```env
   MQTT_PASS=your_secure_password
   ```
2. Start the container:
   ```bash
   docker-compose up -d
   ```
*(Note: If running on Linux/Raspberry Pi, ensure `/dev/bus/usb` passthrough is uncommented in the compose file so the container can reach your RTL-SDR dongle).*

## Environment Variables
- `MQTT_BROKER`: IP address of your MQTT broker (default: 192.168.1.121).
- `MQTT_PORT`: Port of your MQTT broker (default: 1883).
- `MQTT_USER`: MQTT username.
- `MQTT_PASS`: MQTT password (feed via `.env`).

## Accessing the URL
Once running, navigate to `http://<your-docker-ip>:5000` to access the Dashboard, settings, and aliases.
