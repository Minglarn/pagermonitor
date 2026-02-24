# PagerMonitor

PagerMonitor är en Dockeriserad allt-i-ett-applikation för Software Defined Radio (SDR) utformad för att fånga upp, avkoda och övervaka POCSAG-personsökartrafik (t.ex. Minicall/Rikssökning). Den har en modern och stilren webbpanel i realtid, dynamisk hantering av inställningar, stöd för flera samtidiga SDR-enheter och ett avancerat aliassystem för att byta ut kryptiska CapCodes mot läsbara namn eller för att muta oönskad skräptrafik.

<img width="1157" height="761" alt="image" src="https://github.com/user-attachments/assets/9f6c2dda-0b0d-4679-9b3c-7eca804c80a7" />

## Huvudfunktioner

*   **Stöd för Multi-SDR**: Kör och övervaka flera RTL-SDR-enheter samtidigt. Du kan tilldela en specifik radio för "Rikssökning 1" och en annan för "Brandkår", helt oberoende av varandra från samma gränssnitt.
*   **Avkodning & Skräpfilter**: Använder `multimon-ng` för att avkoda POCSAG512, 1200 och 2400-meddelanden. Innehåller ett intelligent Entropi-baserat skräpfilter som kasserar brusstörningar men släpper igenom legitima, korta meddelanden (t.ex. "AB").
*   **Svenskt Teckenstöd**: Hanterar per automatik översättning av personsökar-standardens specialtecken till Å, Ä och Ö samt städar upp radbrytningar.
*   **Realtids-Dashboard**: Ett modernt "OLED/Glassmorphism"-inspirerat gränssnitt med `Server-Sent Events (SSE)` som omedelbart ritar upp inkommande larm utan att sidan behöver laddas om. Dessutom fullt stöd för Infinite Scroll mot databasen.
*   **CapCode Aliases & Muting**: Koppla ihop numeriska adresser (t.ex. `1234567`) med namn (`Station 1`). Om en terminal spammar trafik kan du även välja att "Muta" den så döljs all dess framtida och historiska trafik från dashboarden per automatik.
*   **Alarmord**: Ställ in kommaseparerade alarmord (t.ex. `Larm, Brand, VMA`). Om ett meddelande innehåller dessa ord markeras hela raden med en blinkande varningseffekt i gränssnittet.
*   **MQTT-Integration**: Skickar automatiskt avkodade (och icke-mutade) meddelanden vidare till en lokal MQTT-broker (t.ex. Home Assistant eller Node-RED). Eventuella alias-namn följer med i JSON-paketet.
    *Exempel på MQTT Payload:*
    ```json
    {
      "timestamp": "2026-02-24T13:31:54.151258",
      "address": "1234567",
      "message": "Från: vaktare@bevakningsbolag.se\nÄmne: Larmhändelse\nDÖRRLARM - Byggnad A\n2026-02-24 13:31:28 Dörr forcerad MAGNETKONTAKT \n\nENTRÉ KULVERT",
      "alias": "Väktare Lokalkontor",
      "bitrate": "1200",
      "function": 3,
      "frequency": "169.8M",
      "alert_word": "FORCERAD",
      "alert_color": "#ef4444",
      "sdr_name": "RIKS 1",
      "is_duplicate": false
    }
    ```
*   **Dubblettering**: Systemet fångar upp och märker om samma larm skickas upprepade gånger inom 60 sekunder, för att undvika hysteri i system som lyssnar via MQTT.

## Arkitektur

Applikationen körs isolerat inuti en enda Docker-container och kompileras från källkod (`librtlsdr` och `multimon-ng`) för maximal prestanda och kompatibilitet. 

1.  **Flask Backend**: Hanterar Web-UI, REST API:er, inställningar, Alias och SSE-strömmen (real-time data).
2.  **SDR Supervisor**: En bakgrundsprocess i Python som övervakar och styr en eller flera instanser av `rtl_fm` bunden mot `multimon-ng`. Om inställningar ändras i GUI:t, startas respektive SDR om sömlöst utan att störa de andra.
3.  **SQLite Databas**: Data, trådar, alias och konfigurationer lagras i en statisk databas (`messages.db`) under `/app/data/` för att överleva omstarter.

---

## Kom igång med Docker

All nödvändig miljö är förberedd i projektet via `docker-compose.yml`. Du kan skapa en fil med nedan innehåll:

```yaml
services:
  pagermonitor:
    # Använd bilden direkt från GitHub Container Registry
    image: ghcr.io/minglarn/pagermonitor:latest
    container_name: pagermonitor
    restart: unless-stopped
    devices:
      # Nödvändigt för Linux-värdar: Karta igenom USB för RTL-SDR
      - /dev/bus/usb:/dev/bus/usb
    volumes:
      - ./data:/app/data
    environment:
      # Anpassa dessa för din MQTT-broker
      - MQTT_BROKER=192.168.1.121
      - MQTT_PORT=1883
      - MQTT_USER=home-assistant-server
      - MQTT_PASS=${MQTT_PASS:-}
      - TZ=${TZ:-Europe/Stockholm}
    ports:
      - "5000:5000"
```

### 1. Hårdvarukrav (Linux / Raspberry Pi)
För att containern ska hitta din RTL-SDR-sticka måste du ge Docker rättigheter till USB-porten. Linux är rekommenderat.

Kontrollera att dina SDR-enheter är inkopplade med:
```bash
lsusb
```
*(Valfritt: Svartlista standard DVB-T-drivrutiner på värdmaskinen så att de inte blockerar RTL-SDR: `sudo rmmod dvb_usb_rtl28xxu`)*

### 2. Konfigurera Miljövariabler
Kopiera exempel-filen och fyll i dina MQTT-uppgifter (om du använder Home Assistant e.dyl.). Om du inte använder MQTT kan du lämna dem tomma.

```bash
cp .env.example .env
nano .env
```
Variablerna i `.env` åsidosätter eller kompletterar `docker-compose.yml`.

### 3. Anpassa `docker-compose.yml`
Öppna filen och kontrollera att inställningarna stämmer för ditt nätverk.
Vikitgast är att USB-mappningen är aktiv:

```yaml
    devices:
      - /dev/bus/usb:/dev/bus/usb
```

### 4. Starta Containern
Istället för att kräva att du bygger komplicerad C++ kod själv laddar systemet automatiskt ner en färdigbyggd och optimerad avbildning direkt från GitHub. Allt du behöver göra är:

```bash
# Starta och kör i bakgrunden
docker-compose up -d

# Titta på loggarna för att bekräfta att RDS/SDR hittas
docker-compose logs -f
```

## Användning & UI
När containern är igång (och inga fel syns i loggarna gällande `libusb`), navigerar du till applikationen via webbläsaren:
**`http://<SERVER_IP>:5000`**

### Första stegen:
1. Gå till fliken **Advanced SDR Settings** i menyn.
2. Skapa din första SDR-instans genom att klicka `Add SDR Device`.
3. Skriv in den frekvens du vill lyssna på (ex: `169.8M`).
4. Välj **Device Serial** om du har flera stickor inkopplade, annars lämna tomt.
5. Spara. Systemet tillämpar ändringen omedelbart i bakgrunden. När ett meddelande tas emot blinkar satellitskålen uppe till vänster 📡!

---
*Utvecklad med ❤️ för radioamatörer och teknikentusiaster.*
