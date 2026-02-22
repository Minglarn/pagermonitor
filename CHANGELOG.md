# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Calendar Versioning (CalVer) `YYYY.0M.0D`.

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
