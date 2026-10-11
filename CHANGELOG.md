# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Calendar Versioning (CalVer) `YYYY.0M.0D`.

## [2026.10.11] - LARM-sida och HTTP-säkerhetshärdning

### Added
- Ny dedikerad sida för **LARM** (`/larm`) i sidomenyn som enbart listar händelser som får en träff (HIT) på bevakade ord i realtid.
- Backend- och API-stöd för filtrering på enbart larmade meddelanden (`/api/messages?alerts_only=1`).
- Färgkodade larmord-brickor i tabellen för tydlig överblick av vilket ord som triggat larmet.
- Konfigurerbar HTTP Basic Auth via miljövariabler (`AUTH_USER` och `AUTH_PASS`) i `docker-compose.yml`.
- Timing attack-skyddad lösenordsvalidering med `hmac.compare_digest` med fullt stöd för svenska tecken.
- Härdade säkerhetsheaders på samtliga HTTP-svar: `X-Frame-Options` (Clickjacking), `X-Content-Type-Options`, `X-XSS-Protection`, `Referrer-Policy` och `Content-Security-Policy`.
- Begränsning av inkommande nyttolast (`MAX_CONTENT_LENGTH = 2MB`) för att skydda mot DoS-minnesöverbelastning.
- Full försvenskning av sidonavigering i samtliga vyer.

### Fixed
- Åtgärdat felaktigt antal bindningsparametrar vid automatisk initiering av SDR-instanser i databasen.
- Sanerat publika filer: Raderat temporära diff-filer, loggar och scratch-skript från versionshanteringen.
- Härdat `.gitignore` för att utesluta databaser, loggar och lokala konfigurationsfiler.
- Anonymiserat nätverkskonfiguration i `docker-compose.yml` för att förhindra exponering av interna adresser.
- Omskrivit `README.md` på svenska utan emojis och uppdaterat dokumentation och walkthrough.

## [2026.02.22] - Initial Release & Upgrades

### Added
- Multi-stage Dockerfile to build `librtlsdr` and `multimon-ng` from source as an all-in-one container.
- GitHub Actions CI/CD workflow to auto-build and push images to `ghcr.io`.
- Flask-based Python backend integrating SQLite, MQTT (`paho-mqtt`), and subprocess SDR polling.
- Premium web UI with dark mode, glassmorphism design, and real-time dashboard.
- Settings management UI to dynamically change SDR Frequency, Gain, and Device Serial without restarting the container.
- Alias system (CapCode -> Name mappings) with UI page to manage and identify incoming messages.
- Quick Alias Modal directly on the Dashboard to instantly attach names to CapCodes without navigating away.
- Mute/Hide feature to ignore messages from specific spam CapCodes.
- Server-Sent Events (SSE) implementation to push new alarm messages to the frontend instantly, removing the need for HTTP interval polling.
- Text parsing to translate pager strings to Swedish characters (Å, Ä, Ö) and convert `<CR><LF>` into proper HTML line breaks.
- Set default Docker timezone to `Europe/Stockholm` so logs and timestamps are correct.

### Fixed
- Fixed an infinite "death loop" crashing the container (Exit Code 137) due to unhandled `rtl_fm` pipe closures causing Memory Leaks / OOM errors.
- Removed unsupported `rtl_tcp` configurations as native `rtl_fm` in `librtlsdr` does not support it, defaulting securely to USB pass-through.
