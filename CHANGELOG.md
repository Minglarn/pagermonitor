# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Calendar Versioning (CalVer) `YYYY.0M.0D`.

## [2026.10.11.1] - Multi-SDR Watchdog Self-Healing & Statistics DataTables 2

### Added
- **Multi-SDR Watchdog & Self-Healing**: Automatically monitors background `rtl_fm` and `multimon-ng` processes. If a process terminates unexpectedly (e.g. USB interrupt or decoding fault), resources are cleaned up and restarted automatically with backoff throttling.
- **Persistent Watchdog Restart Auditing**: Logs each automatic recovery to `messages.db` (`address: SYSTEM`, `frequency: RESTART`) so restarts can be searched and reviewed weeks later.
- **Real-Time Restart Notifications**: Broadcasts recovery events over Server-Sent Events (SSE) displaying a floating Toast notification banner and highlighting the recovery row in amber in the Live Monitor table.
- **Statistics Table DataTables 2 Migration**: Converted the historical messages table on the Statistics page to DataTables 2 with persistent settings (`stateSave`), column sorting, responsive pagination (25, 50, 100, All), and instant search.
- **Badge Collision Fix**: Separated timestamps and frequency badges with dedicated column classes to prevent overlapping in the Statistics table view.
- **Watchdog Unit Test Suite**: Added automated tests verifying process failure detection, resource cleanup, and restart triggering.

## [2026.10.11] - Database Stat Dashboard, Auto-Pruning, Alarms View & English Localization

### Added
- **Database Stat Dashboard**: Overhauled Settings -> Maintenance into a modern "Database Stat" view featuring 8 KPI cards: Total Messages, Watchlist Hits, Database Disk Size, Oldest Entry, Newest Entry, Protected Messages, Unique CapCodes, and Duplicate Count.
- **Automated Retention & Auto-Pruning Scheduler**: Integrated background daemon thread executing every 6 hours to automatically prune records older than the configured threshold (default: 30 days) and reclaim space with SQLite `VACUUM`.
- **Dedicated Alarms View & Dashboard with DataTables 2**: Rebuilt both the live Dashboard (`/`) and Alarms view (`/alarms`) with DataTables 2 for client-side sorting, pagination, search, and real-time SSE stream integration.
- **Sticky Table Headers & Compact Controls**: Implemented sticky header rows (`position: sticky`) for DataTables tables so column titles remain pinned during scrolling, and compressed the controls toolbar height by over 50% for maximum screen real estate.
- **DataTables Settings Persistence (stateSave)**: Enabled persistent table state saving in `localStorage` (`stateDuration: 1 year`) so user preferences (page length, sort orders, search filters) are automatically remembered across reloads.
- **CapCode (Alias) Word Wrapping**: Enabled multi-line text wrapping for long alias names (e.g. "Naturhistoriska Riksmuseet") to maintain compact column boundaries without squeezing message text.
- **Statistics Date Range Picker**: Replaced manual text entry with interactive From and To date pickers (`color-scheme: dark`) with instant popup pickers, quick presets (Today, Yesterday, 7 Days, 30 Days), and dynamic activity distribution charts.
- **Full English Localization**: Converted all UI templates, labels, forms, dialogs, API status strings, and documentation into English.
- **HTTP Basic Authentication**: Optional username/password authentication configured via `AUTH_USER` and `AUTH_PASS` in `docker-compose.yml` and `.env`.
- **Timing Attack Resistance**: Uses `hmac.compare_digest` with UTF-8 encoding for credential validation.
- **Security Response Headers**: Added `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`, `Referrer-Policy`, and `Content-Security-Policy`.
- **DoS Protection**: Capped request payload size to 2MB (`MAX_CONTENT_LENGTH`).
- **REST API Endpoints**:
  - `GET /api/database/stats` returns real-time aggregated metrics.
  - `POST /api/settings` supports `auto_prune_enabled` and `auto_prune_days`.
  - `POST /api/messages/prune` returns deleted message count.

### Fixed
- **SQLite ISO Timestamp Pruning**: Fixed query to use `datetime(replace(timestamp, 'T', ' ')) < datetime('now', '-' || ? || ' days')` so ISO timestamps stored by Python match SQLite datetime comparisons accurately.
- **Repository Clean-up**: Removed untracked temporary diff files, scratch scripts, and exposed local configurations from git history.
- **Hardened `.gitignore`**: Excluded local SQLite databases, debug logs, diffs, and `.env` credentials from being committed.
- **Emoji Removal**: Fully purged all emojis from all web templates and documentation.

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
