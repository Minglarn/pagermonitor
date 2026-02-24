# PagerMonitor

PagerMonitor är en Dockeriserad allt-i-ett-applikation för Software Defined Radio (SDR) utformad för att fånga upp, avkoda och övervaka POCSAG-personsökartrafik (t.ex. Minicall/Rikssökning). Den har en modern och stilren webbpanel i realtid, dynamisk hantering av inställningar, stöd för flera samtidiga SDR-enheter och ett avancerat aliassystem för att byta ut kryptiska CapCodes mot läsbara namn eller för att muta oönskad skräptrafik.

## Huvudfunktioner

*   **Stöd för Multi-SDR**: Kör och övervaka flera RTL-SDR-enheter samtidigt. Du kan tilldela en specifik radio för "Rikssökning 1" och en annan för "Brandkår", helt oberoende av varandra från samma gränssnitt.
*   **Avkodning & Skräpfilter**: Använder `multimon-ng` för att avkoda POCSAG512, 1200 och 2400-meddelanden. Innehåller ett intelligent Entropi-baserat skräpfilter som kasserar brusstörningar men släpper igenom legitima, korta meddelanden (t.ex. "AB").
*   **Svenskt Teckenstöd**: Hanterar per automatik översättning av personsökar-standardens specialtecken till Å, Ä och Ö samt städar upp radbrytningar.
*   **Realtids-Dashboard**: Ett modernt "OLED/Glassmorphism"-inspirerat gränssnitt med `Server-Sent Events (SSE)` som omedelbart ritar upp inkommande larm utan att sidan behöver laddas om. Dessutom fullt stöd för Infinite Scroll mot databasen.
*   **CapCode Aliases & Muting**: Koppla ihop numeriska adresser (t.ex. `1234567`) med namn (`Station 1`). Om en terminal spammar trafik kan du även välja att "Muta" den så döljs all dess framtida och historiska trafik från dashboarden per automatik.
*   **Alarmord**: Ställ in kommaseparerade alarmord (t.ex. `Larm, Brand, VMA`). Om ett meddelande innehåller dessa ord markeras hela raden med en blinkande varningseffekt i gränssnittet.
*   **MQTT-Integration**: Skickar automatiskt avkodade (och icke-mutade) meddelanden vidare till en lokal MQTT-broker (t.ex. Home Assistant eller Node-RED). Eventuella alias-namn följer med i JSON-paketet.
*   **Dubblettering**: Systemet fångar upp och märker om samma larm skickas upprepade gånger inom 60 sekunder, för att undvika hysteri i system som lyssnar via MQTT.

## Arkitektur

Applikationen körs isolerat inuti en enda Docker-container och kompileras från källkod (`librtlsdr` och `multimon-ng`) för maximal prestanda och kompatibilitet. 

1.  **Flask Backend**: Hanterar Web-UI, REST API:er, inställningar, Alias och SSE-strömmen (real-time data).
2.  **SDR Supervisor**: En bakgrundsprocess i Python som övervakar och styr en eller flera instanser av `rtl_fm` bunden mot `multimon-ng`. Om inställningar ändras i GUI:t, startas respektive SDR om sömlöst utan att störa de andra.
3.  **SQLite Databas**: Data, trådar, alias och konfigurationer lagras i en statisk databas (`messages.db`) under `/app/data/` för att överleva omstarter.

---

## Kom igång med Docker

All nödvändig miljö är förberedd i projektet via `docker-compose.yml`.

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

### 4. Bygg och Starta
Eftersom systemet laddar ner och bygger radiodrivrutinerna direkt vid installation kan första bygget ta några minuter.

```bash
# Starta bygget och kör i bakgrunden
docker-compose up -d --build

# Monitera loggarna för att se att mjukvaran hittat dina SDR-enheter
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
