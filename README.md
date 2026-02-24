# PagerMonitor

PagerMonitor is a Dockerized all-in-one application for Software Defined Radio (SDR) designed to capture, decode, and monitor POCSAG pager traffic (e.g., Minicall/Rikssökning). It features a modern and stylish real-time web dashboard, dynamic settings management, support for multiple simultaneous SDR devices, and an advanced alias system to replace cryptic CapCodes with readable names or to mute unwanted junk traffic.

<img width="1157" height="761" alt="image" src="https://github.com/user-attachments/assets/9f6c2dda-0b0d-4679-9b3c-7eca804c80a7" />

## Main Features

*   **Multi-SDR Support**: Run and monitor multiple RTL-SDR devices simultaneously. You can assign a specific radio for "Broadcasting 1" and another for "Fire Dept", completely independent of each other from the same interface.
*   **Decoding & Junk Filter**: Uses `multimon-ng` to decode POCSAG512, 1200, and 2400 messages. Includes an intelligent Entropy-based junk filter that discards noise interference but allows legitimate, short messages (e.g., "AB").
*   **Swedish Character Support**: Automatically handles translation of special characters from the pager standard to Å, Ä, and Ö, and cleans up line breaks.
*   **Real-time Dashboard**: A modern "OLED/Glassmorphism" inspired interface with `Server-Sent Events (SSE)` that immediately displays incoming alarms without needing to reload the page. Also includes full support for Infinite Scroll against the database.
*   **CapCode Aliases & Muting**: Link numerical addresses (e.g., `1234567`) with names (`Station 1`). If a terminal spams traffic, you can also choose to "Mute" it, which automatically hides all its future and historical traffic from the dashboard.
*   **Alert Words**: Set comma-separated alert words (e.g., `Alarm, Fire, SOS`). If a message contains these words, the entire row is marked with a flashing warning effect in the interface.
*   **MQTT Integration**: Automatically forwards decoded (and non-muted) messages to a local MQTT broker (e.g., Home Assistant or Node-RED). Any alias names are included in the JSON payload.
    *Example MQTT Payload:*
    ```json
    {
      "timestamp": "2026-02-24T13:31:54.151258",
      "address": "1234567",
      "message": "From: guard@securitycompany.com\nSubject: Alarm Event\nDOOR ALARM - Building A\n2026-02-24 13:31:28 Door forced MAGNETIC CONTACT \n\nENTRANCE CULVERT",
      "alias": "Guard Local Office",
      "bitrate": "1200",
      "function": 3,
      "frequency": "169.8M",
      "alert_word": "FORCED",
      "alert_color": "#ef4444",
      "sdr_name": "RIKS 1",
      "is_duplicate": false
    }
    ```

    *Example Home Assistant Automation:*
    ```yaml
    alias: "PagerMonitor: Send Important Alarms"
    description: Sends notification to mobile devices only if alert_word is not empty
    triggers:
      - topic: pagermonitor/alarms
        trigger: mqtt
    conditions:
      - condition: template
        value_template: >-
          {{ trigger.payload_json.alert_word | length > 0 and
          trigger.payload_json.is_duplicate == false }}
    actions:
      - data:
          title: >-
            {{ trigger.payload_json.alert_word }}: {{ trigger.payload_json.alias if
            trigger.payload_json.alias != '' else trigger.payload_json.address }}
          message: "{{ trigger.payload_json.message }}"
          data:
            color: "{{ trigger.payload_json.alert_color }}"
            tag: pagermonitor-{{ trigger.payload_json.address }}
            priority: high
            ttl: 0
        action: notify.mobile_devices_notification
    mode: queued
    max: 10
    ```
*   **De-duplication**: The system catches and marks repeated alarms sent within 60 seconds to avoid hysteria in systems listening via MQTT.

## Architecture

The application runs isolated inside a single Docker container and is compiled from source (`librtlsdr` and `multimon-ng`) for maximum performance and compatibility.

1.  **Flask Backend**: Handles Web-UI, REST APIs, settings, Aliases, and the SSE stream (real-time data).
2.  **SDR Supervisor**: A background process in Python that monitors and controls one or more instances of `rtl_fm` bound to `multimon-ng`. If settings are changed in the GUI, the respective SDR is restarted seamlessly without disturbing the others.
3.  **SQLite Database**: Data, threads, aliases, and configurations are stored in a static database (`messages.db`) under `/app/data/` to survive restarts.

---

## Getting Started with Docker

All necessary environment is prepared in the project via `docker-compose.yml`. You can create a file with the content below:

```yaml
services:
  pagermonitor:
    # Use the image directly from GitHub Container Registry
    image: ghcr.io/minglarn/pagermonitor:latest
    container_name: pagermonitor
    restart: unless-stopped
    devices:
      # Necessary for Linux hosts: Map USB for RTL-SDR
      - /dev/bus/usb:/dev/bus/usb
    volumes:
      - ./data:/app/data
    environment:
      # Customize these for your MQTT broker
      - MQTT_BROKER=192.168.1.121
      - MQTT_PORT=1883
      - MQTT_USER=home-assistant-server
      - MQTT_PASS=${MQTT_PASS:-}
      - TZ=${TZ:-Europe/Stockholm}
    ports:
      - "5000:5000"
```

### 1. Hardware Requirements (Linux / Raspberry Pi)
For the container to find your RTL-SDR dongle, you must give Docker permissions to the USB port. Linux is recommended.

Check that your SDR devices are connected with:
```bash
lsusb
```
*(Optional: Blacklist default DVB-T drivers on the host machine so they don't block RTL-SDR: `sudo rmmod dvb_usb_rtl28xxu`)*

### 2. Configure Environment Variables
Copy the example file and fill in your MQTT details (if using Home Assistant etc.). If you are not using MQTT, you can leave them empty.

```bash
cp .env.example .env
nano .env
```
Variables in `.env` override or supplement `docker-compose.yml`.

### 3. Customize `docker-compose.yml`
Open the file and verify that the settings are correct for your network.
The most important part is that USB mapping is active:

```yaml
    devices:
      - /dev/bus/usb:/dev/bus/usb
```

### 4. Start the Container
Instead of requiring you to build complicated C++ code yourself, the system automatically downloads a pre-built and optimized image directly from GitHub. All you need to do is:

```bash
# Start and run in the background
docker-compose up -d

# Look at the logs to confirm that RDS/SDR is found
docker-compose logs -f
```

## Usage & UI
Once the container is running (and no errors are seen in the logs regarding `libusb`), navigate to the application via your browser:
**`http://<SERVER_IP>:5000`**

### First Steps:
1. Go to the **Advanced SDR Settings** tab in the menu.
2. Create your first SDR instance by clicking `Add SDR Device`.
3. Enter the frequency you want to listen to (e.g., `169.8M`).
4. Select **Device Serial** if you have multiple dongles connected, otherwise leave empty.
5. Save. The system applies the change immediately in the background. When a message is received, the satellite dish at the top left flashes 📡!

---
*Developed with ❤️ for radio amateurs and tech enthusiasts.*
