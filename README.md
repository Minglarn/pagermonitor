# PagerMonitor

[![Version](https://img.shields.io/badge/version-2026.10.14.31-blue.svg)](CHANGELOG.md)
[![GitHub last commit](https://img.shields.io/github/last-commit/Minglarn/pagermonitor)](https://github.com/Minglarn/pagermonitor/commits/main)
[![GitHub issues](https://img.shields.io/github/issues/Minglarn/pagermonitor)](https://github.com/Minglarn/pagermonitor/issues)
[![GitHub stars](https://img.shields.io/github/stars/Minglarn/pagermonitor?style=social)](https://github.com/Minglarn/pagermonitor/stargazers)
[![Docker](https://img.shields.io/badge/docker-GHCR-blue.svg?logo=docker&logoColor=white)](https://github.com/Minglarn/pagermonitor/pkgs/container/pagermonitor)


PagerMonitor is a complete, containerized Software Defined Radio (SDR) platform designed to capture, decode, and monitor POCSAG pager transmissions. The system features a modern real-time dark web interface, dynamic receiver configuration, multi-SDR receiver support, a CapCode alias management engine, automated database maintenance, and a dedicated alarms view for monitored keywords.

<p align="center">
  <img src="docs/screenshots/dashboard_preview.png" alt="PagerMonitor Real-time Monitor" width="100%">
</p>

---

## Core Features

* **Multi-SDR Support**: Run and monitor multiple RTL-SDR devices simultaneously. Assign individual receivers to distinct frequencies and sample rates, managed independently from a unified web interface.
* **Dedicated Alarms View**: A standalone page that aggregates all messages matching your monitored alert keywords in real time, complete with color-coded alert badges.
* **Real-time Docker & System Console**: Universal bottom-docked terminal available across all views that streams 100% of container and Python logs via SSE, with ANSI/log-level color badges, word-wrap toggling, autoscroll, and real-time text filtering.
* **Decoding & Noise Filtering**: Powered by `multimon-ng` for decoding POCSAG 512, 1200, and 2400 baud. Features an intelligent entropy-based junk filter that discards noise and corrupted frames while preserving short legitimate messages.
* **Character Set Support**: Built-in support for European and Swedish character sets (converting legacy pager representations to Å, Ä, and Ö) alongside clean newline formatting.
* **Real-time Live Stream**: Modern user interface utilizing `Server-Sent Events (SSE)` for instantaneous message delivery without page reloads. Includes infinite scrolling for full database history browsing.
* **CapCode Aliases & Muting**: Map numeric pager addresses (e.g. `1234567`) to descriptive names (e.g. `Station Central`). Mute noisy or unwanted addresses directly from the interface.
* **Watchlist & Alert Words**: Configure custom comma-separated watchwords (e.g. `FIRE, ACCIDENT, CPR, AMBULANCE`). Matched messages are highlighted and streamed to the dedicated Alarms tab.
* **Database Stats & Automated Retention**: Comprehensive database metric cards (total messages, watchlist hits, storage footprint, date ranges, duplicates, protected rows) and scheduled auto-pruning.
* **HTTP Security & Hardening**: Optional HTTP Basic Authentication configurable via environment variables, hardened HTTP response headers (X-Frame-Options, X-Content-Type-Options, Content Security Policy), and request payload size caps to guard against denial of service.
* **MQTT Integration**: Automatically forwards decoded messages to any local or remote MQTT broker (e.g. Home Assistant or Node-RED). Aliases and alert tags are included in the JSON payload.
* **Deduplication Engine**: Automatically identifies and flags duplicate transmissions occurring within a configurable 60-second window to prevent repetitive notifications.

---

## MQTT Payload & Home Automation

### JSON Payload Example
```json
{
  "timestamp": "2026-10-11T14:30:00.000000",
  "address": "1234567",
  "message": "ALARM: COMMERCIAL BUILDING FIRE\nSTATION STREET 1\nUNITS 1 AND 2 DISPATCHED",
  "alias": "Fire Department",
  "bitrate": "1200",
  "function": 3,
  "frequency": "169.8M",
  "alert_word": "FIRE",
  "alert_color": "#ef4444",
  "sdr_name": "Receiver 1",
  "is_duplicate": false
}
```

### Home Assistant Automation Example
```yaml
alias: "PagerMonitor: Send Priority Alert"
description: "Dispatches mobile notification when a monitored keyword is hit"
triggers:
  - trigger: mqtt
    topic: pagermonitor/alarms
conditions:
  - condition: template
    value_template: >-
      {{ trigger.payload_json.alert_word | length > 0 and
      trigger.payload_json.is_duplicate == false }}
actions:
  - action: notify.mobile_devices_notification
    data:
      title: >-
        {{ trigger.payload_json.alert_word }}: {{ trigger.payload_json.alias if
        trigger.payload_json.alias != '' else trigger.payload_json.address }}
      message: "{{ trigger.payload_json.message }}"
      data:
        color: "{{ trigger.payload_json.alert_color }}"
        tag: "pagermonitor-{{ trigger.payload_json.address }}"
        priority: high
        ttl: 0
mode: queued
max: 10
```

---

## System Architecture

The application runs in an isolated container compiled from source (`librtlsdr` and `multimon-ng`) for maximum performance and driver compatibility:

1. **Flask Backend**: Serves the web interface, REST API, authentication middleware, and Server-Sent Events stream.
2. **SDR Supervisor**: Python background supervisor managing `rtl_fm` and `multimon-ng` subprocesses. Changing radio parameters in the UI triggers seamless live restarts.
3. **Automated Scheduler**: Background maintenance thread executing database retention checks every 6 hours.
4. **SQLite Database**: Messages, CapCode aliases, alert words, and SDR settings are persisted inside `/app/data/pagermonitor.db`.

---

## Quickstart with Docker Compose

Preconfigured deployment via [docker-compose.yml](docker-compose.yml):

```yaml
services:
  pagermonitor:
    image: ghcr.io/minglarn/pagermonitor:latest
    container_name: pagermonitor
    restart: unless-stopped
    devices:
      # Grants container access to the host USB SDR dongles on Linux
      - /dev/bus/usb:/dev/bus/usb
    volumes:
      - ./data:/app/data
    environment:
      - MQTT_BROKER=${MQTT_BROKER:-127.0.0.1}
      - MQTT_PORT=${MQTT_PORT:-1883}
      - MQTT_USER=${MQTT_USER:-}
      - MQTT_PASS=${MQTT_PASS:-}
      - MQTT_TOPIC=${MQTT_TOPIC:-pagermonitor/alarms}
      - TZ=${TZ:-Europe/Stockholm}
      # HTTP Basic Authentication (leave AUTH_PASS empty to disable)
      - AUTH_USER=${AUTH_USER:-admin}
      - AUTH_PASS=${AUTH_PASS:-}
    ports:
      - "7090:5000"
```

### 1. Hardware Requirements (Linux / Raspberry Pi)
Ensure Docker has access to your USB RTL-SDR dongles:

```bash
lsusb
```

*(Tip: Blacklist default Linux DVB-T kernel drivers if they block RTL-SDR: `sudo rmmod dvb_usb_rtl28xxu`)*

### 2. Configure Environment Variables
Copy the example file and update your configuration:

```bash
cp .env.example .env
nano .env
```

If running behind an authenticating reverse proxy (like Nginx Proxy Manager), leave `AUTH_PASS` blank. If deploying directly, provide a strong password for `AUTH_PASS`.

### 3. Launch Container
```bash
# Start in background
docker compose up -d

# Inspect live logs
docker compose logs -f
```

---

## Web Interface Overview

Access the web interface at:
**`http://<SERVER_IP>:7090`**

### Navigation
* **Dashboard**: Real-time live feed of incoming pager traffic.
* **Alarms**: Dedicated view for messages triggering watchlist hits.
* **Aliases**: Map CapCodes to readable names and toggle muting.
* **Alert Words**: Manage keywords that trigger alarms and highlighted badges.
* **Statistics**: Historical graphs, hourly frequency charts, and daily logs.
* **Settings**: Configure SDR hardware, audio filters, and inspect **Database Stat** KPI cards & automated data retention.
