# PagerMonitor

[![Version](https://img.shields.io/badge/version-2026.10.11-007ec6.svg)](CHANGELOG.md)
[![Last Commit](https://img.shields.io/github/last-commit/Minglarn/pagermonitor.svg)](https://github.com/Minglarn/pagermonitor/commits/main)
[![Issues](https://img.shields.io/github/issues/Minglarn/pagermonitor.svg)](https://github.com/Minglarn/pagermonitor/issues)
[![Stars](https://img.shields.io/github/stars/Minglarn/pagermonitor?style=social)](https://github.com/Minglarn/pagermonitor/stargazers)

PagerMonitor är en komplett, containeriserad plattform för Software Defined Radio (SDR) utformad för att fånga upp, avkoda och övervaka POCSAG-personsökartrafik (t.ex. Minicall och Rikssökning). Systemet har ett modernt mörkt webbgränssnitt i realtid, dynamisk mottagarkonfiguration, stöd för flera parallella SDR-enheter, ett kraftfullt alias-system för CapCodes samt en dedikerad larmvy för bevakade händelser.

---

## Huvudfunktioner

* **Multi-SDR-stöd**: Kör och övervaka flera RTL-SDR-enheter samtidigt. Du kan tilldela en specifik mottagare för en frekvens och en annan för en annan, helt oberoende av varandra från samma gränssnitt.
* **Dedikerad LARM-vy**: En separat sida i menyn som i realtid samlar alla meddelanden som har fått en träff (HIT) på dina bevakade ord, komplett med färgkodade larmbrickor.
* **Avkodning och skräpfilter**: Använder `multimon-ng` för att avkoda POCSAG512, 1200 och 2400. Innehåller ett intelligent entropibaserat skräpfilter som sorterar bort brus och felaktiga avkodningar, men släpper igenom legitima korta meddelanden.
* **Fullt stöd för svenska tecken**: Automatisk konvertering av personsökarstandardens specialtecken till Å, Ä och Ö samt snygg formatering av radbrytningar.
* **Realtidsdashboard**: Modernt gränssnitt med `Server-Sent Events (SSE)` som omedelbart visar inkommande larm utan att webbläsaren behöver ladda om sidan. Fullt stöd för historisk bläddring via infinite scroll mot databasen.
* **CapCode-alias och döljfunktion**: Koppla sifferadresser (t.ex. `1234567`) till begripliga namn (t.ex. `Station Centrum`). Om en adress skickar oönskat brus kan du dölja den, vilket tar bort dess meddelanden från flödet.
* **Bevakade ord**: Lägg till kommaseparerade bevakningsord (t.ex. `BRAND, OLYCKA, HLR, AMBULANS`). Om ett meddelande innehåller något av orden markeras raden tydligt och visas i larmvyn.
* **HTTP-säkerhet och åtkomstkontroll**: Inbyggt stöd för HTTP Basic Auth via miljövariabler, härdade säkerhetsheaders (skydd mot Clickjacking, MIME-sniffing och XSS) samt begränsning av förfrågningsstorlek för DoS-skydd.
* **MQTT-integration**: Vidarebefordrar automatiskt avkodade meddelanden till en lokal MQTT-broker (t.ex. Home Assistant eller Node-RED). Eventuella alias inkluderas i JSON-strukturen.
* **Deduplicering**: Systemet upptäcker och flaggar upprepade meddelanden som skickas inom 60 sekunder för att undvika dubbla notiser i anslutna system.

---

## MQTT-struktur och hemautomation

### Exempel på JSON-nyttolast
```json
{
  "timestamp": "2026-10-11T14:30:00.000000",
  "address": "1234567",
  "message": "LARM: STOR BRAND I BYGGNAD\nSTATIONSGATAN 1\nSTYRKA 1 OCH 2 LARMADE",
  "alias": "Raddningstjanst",
  "bitrate": "1200",
  "function": 3,
  "frequency": "169.8M",
  "alert_word": "BRAND",
  "alert_color": "#ef4444",
  "sdr_name": "Mottagare 1",
  "is_duplicate": false
}
```

### Exempel på Home Assistant-automation
```yaml
alias: "PagerMonitor: Skicka prioriterade larm"
description: "Skickar avisering till mobila enheter nar ett bevakat ord traffas"
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

## Arkitektur

Applikationen körs isolerat i en container och byggs från källkod (`librtlsdr` och `multimon-ng`) för högsta prestanda och drivrutinskompatibilitet.

1. **Flask Backend**: Hanterar webbgränssnittet, REST API, inställningar, alias, säkerhetskontroll och SSE-strömmen för realtidsdata.
2. **SDR Supervisor**: En bakgrundsprocess i Python som övervakar och styr instanser av `rtl_fm` kopplade mot `multimon-ng`. Om inställningar ändras i gränssnittet startas berörd SDR om sömlöst i bakgrunden.
3. **SQLite-databas**: Meddelanden, alias och inställningar lagras i en SQLite-databas under `/app/data/` för att bevaras mellan omstarter.

---

## Snabbstart med Docker Compose

All nödvändig miljö är förberedd i [docker-compose.yml](docker-compose.yml):

```yaml
services:
  pagermonitor:
    image: ghcr.io/minglarn/pagermonitor:latest
    container_name: pagermonitor
    restart: unless-stopped
    devices:
      # Nodvandigt pa Linux for att ge containern atkomst till USB-mottagaren
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
      # HTTP-autentisering (lamna AUTH_PASS tomt for att inaktivera)
      - AUTH_USER=${AUTH_USER:-admin}
      - AUTH_PASS=${AUTH_PASS:-}
    ports:
      - "7090:5000"
```

### 1. Hårdvarukrav (Linux / Raspberry Pi)
För att containern ska hitta din RTL-SDR-dongel krävs att Docker har åtkomst till USB-porten.

Kontrollera att dina SDR-enheter är anslutna:
```bash
lsusb
```

*(Tips: Svartlista standard-DVB-T-drivrutiner på värddatorn om de blockerar RTL-SDR: `sudo rmmod dvb_usb_rtl28xxu`)*

### 2. Konfigurera miljövariabler
Kopiera exempelfilen och fyll i dina uppgifter:

```bash
cp .env.example .env
nano .env
```

Om du vill skydda webbgränssnittet med lösenord sätter du `AUTH_PASS` i `.env`. Kör du bakom en reverse proxy som Nginx Proxy Manager kan du lämna `AUTH_PASS` tomt och låta proxyn hantera behörigheten.

### 3. Starta containern
```bash
# Starta i bakgrunden
docker compose up -d

# Folj loggarna for att se att mottagaren startar korrekt
docker compose logs -f
```

---

## Gränssnitt och användning

Öppna webbläsaren och navigera till:
**`http://<SERVER_IP>:7090`**

### Sidonavigering
* **Dashboard**: Realtidsöversikt över all inkommande trafik.
* **LARM**: Dedikerad vy för händelser som har fått en träff på bevakade ord.
* **Alias**: Hantera kopplingar mellan CapCode-adresser och läsbara namn samt döljfunktion.
* **Bevakade ord**: Lägg till och redigera ord som ska trigga larm och färgmarkeras.
* **Statistik**: Diagram och historisk statistik över meddelandevolymer, tider och frekvenser.
* **Inställningar**: Konfigurera radiofrekvens, gain, teckenuppsättning och SDR-enheter.
