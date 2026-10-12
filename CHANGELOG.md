# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Calendar Versioning (CalVer) `YYYY.0M.0D`.

## [2026.10.12.2] - Extended POCSAG Multimon Buffer & One-Click Message Copying

### Added
- **One-Click Message Copy Action**:
  - Added a dedicated copy button (`.copy-btn`) to the actions column in Database Explorer (`statistics.html`), Live Monitor (`index.html`), and Alarms view (`larm.html`).
  - Automatically copies full message text to clipboard using the Clipboard API with legacy fallback support.
  - Visual feedback on copy: the icon transitions to a green checkmark (`fa-check`) with a "Kopierad!" tooltip for 1.5 seconds.
- **Extended POCSAG Buffer in multimon-ng**:
  - Patched `multimon.h` and `pocsag.c` during Docker build, increasing internal POCSAG receive buffer from 512 bytes to 4,096 bytes and string buffers to 8,192 characters.
  - Prevents premature truncation and `Warning: Message too long` sync drops on lengthy CAD (Computer-Aided Dispatch) emergency messages exceeding 500 characters.

## [2026.10.12.1] - Fix SDR Processor Ingestion Pipeline & Persistence

### Fixed
- **SDR Message Ingestion & Persistence Pipeline**:
  - Fixed an errant `else` block indentation regression in `sdr_processor.py` that caused decoded POCSAG/AFSK messages to be logged as `RAW` but completely bypass database storage (`save_message`), MQTT publishing (`publish_message`), and live web client callbacks (`new_message_callbacks`).
  - Restored real-time stream delivery to the DataTables dashboard and historical database logging.
  - Added regression test `test_monitor_instance_saves_and_broadcasts_message` to verify that incoming multimon-ng output lines are parsed, saved to the database, published to MQTT, and broadcast to live SSE streams.

## [2026.10.11.10] - Prominent Zebra Striping, Edge-to-Edge Dividers & Razor-Sharp Badge Typography

### Added
- **Prominent Zebra Striping (Dark & Light Themes)**:
  - Added distinct alternating row backgrounds across DataTables in Dashboard, Alarms, and Statistics views.
  - In Dark theme: odd rows use `#0a0a0a` and even rows use `#141b24` with high-contrast hover (`rgba(56, 189, 248, 0.12)`).
  - In Light theme: odd rows use `#ffffff` and even rows use `#eef2f6` with smooth hover (`#e2e8f0`).
  - Added specialized alternating tinting for highlighted alert rows.

### Fixed
- **Edge-to-Edge Dividers & Table Alignment**:
  - Removed inner padding (`padding: 0 !important;`) on table containers so table rows, zebra striping, and column/row dividers extend all the way flush to the outer panel borders.
  - Relocated control padding to DataTables layout rows (`.dt-layout-row`) for search, page length, and pagination controls.
  - Added clean cell padding on first and last columns (`1rem`) to keep contents beautifully aligned.
- **Razor-Sharp Badge/Pill Typography (Removed Filter Effect)**:
  - Fixed blurry and fuzzy appearance on badges/pills by removing `transform: scale(1.02)` and transform transitions that triggered Chromium GPU subpixel rasterization blur.
  - Replaced fractional `calc(var(--msg-size) * 0.9)` with clean, crisp `0.8125rem` / `0.72rem` integer font sizing.
  - Added `-webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; text-rendering: geometricPrecision;`.
  - Added dedicated `.badge.meta.badge-freq` class with rich, high-contrast colors in both dark and light modes, replacing washed-out inline purple styles.

## [2026.10.11.9] - Restored Vertical Column Dividers in DataTables

### Fixed
- **Vertical Column Dividers (Restored)**:
  - Re-added crisp vertical separator lines (`border-right: 1px solid var(--panel-border)`) between all table columns across `thead th` and `tbody td` in Dashboard, Alarms, and Statistics tables.
  - Suppressed the divider on the last column (`:last-child { border-right: none }`) to maintain clean outer card borders.

## [2026.10.11.8] - Clean Flat Table Layout, Minimized Sidebar Margins & Compact Heartbeat

### Fixed
- **Clean Flat Table Layout (Eliminated "Box-in-Box" Effect)**:
  - Eliminated the disjointed card-per-row layout (`border-spacing: 0 8px`, `border-radius: 12px` per row) across Dashboard, Alarms, and Statistics tables.
  - Replaced with a cohesive `border-collapse: collapse` table layout with sleek, unified horizontal 1px dividers (`border-bottom: 1px solid var(--panel-border)`), transparent row backgrounds, and subtle hover highlights.
  - Removed inner nested borders and radius on `td:first-child` / `td:last-child`.
- **Minimized Sidebar Margins**:
  - Reduced outer `.main-content` and `.dashboard-page .main-content` padding from `2rem` (32px) down to `0.75rem 1rem`, significantly reducing wasted whitespace against the sidebar and expanding usable table width.
  - Adjusted header margin-bottom to `0.75rem` and streamlined table-container padding.
- **Compact SDR Heartbeat Logging**:
  - Replaced the verbose 285-character multi-line heartbeat with a concise 55-character summary:
    `SDR Heartbeat: [RIKS 1] OK (22s) | [RIKS 2] OK (24s)`.
  - Suppressed disabled SDR instances from regular log spam.
- **Alias Multi-Word Wrapping Without Ellipsis**:
  - Restored natural word wrapping (`white-space: normal`) on CapCode aliases, allowing compound names ("Sjukvårdens Larmcentral") to wrap cleanly at whitespace without truncation or `...` ellipsis.

## [2026.10.11.7] - DB Load Latency Fix, Streamlined Drop Logging & Local Repository Badges

### Fixed
- **Database Load Latency (10-15s Freeze)**:
  - Fixed severe UI loading lag caused by unbounded message queries fetching the entire historical database without limit.
  - Added a responsive default limit (`limit=500`) to `/api/messages` and client initialization in Dashboard (`/`) and Alarms (`/larm`), while preserving full unconstrained exports via `limit=all` or `limit=0`.
  - Added SQLite composite indexes on `messages(id DESC)`, `messages(address)`, and `messages(timestamp)` in `init_db()`, reducing query execution from seconds to <2 milliseconds.
- **SDR Processor Log Redundancy**:
  - Consolidated multi-line drop outputs into a concise single-line format:
    `[RIKS X] RAW: POCSAG1200: ... [DROPPED] Cause: MUTED` (and `[DROPPED] Cause: GARBAGE`).
  - Eliminated the redundant secondary log line (`DOLT ALIAS DROPPADE -> Adress: ...`).
- **README Badges & Shields.io Formatting**:
  - Fixed broken badges in `README.md` by adopting the proven formatting pattern from `fail2banExplorer`.
  - Removed accidental `.svg` extensions from repository-level GitHub endpoints (`/last-commit/...` and `/issues/...`) that caused shields.io to search for a non-existent `pagermonitor.svg` repository.
  - Added `-blue.svg` color suffix to version badge and linked Docker GHCR package badge.

## [2026.10.11.6] - Fix CapCode Alias Word Breaking & Expand Column Width

### Fixed
- **CapCode (Alias) Word Breaking**: Eliminated word splitting (e.g. "Nätverkssyn" / "k") across all live and historical tables by replacing `word-break: break-word` with `white-space: nowrap`, `word-break: keep-all`, and `overflow-wrap: normal`.
- **Expanded Alias Column Width**: Widened the `CAPCODE (ALIAS)` column from 140px (min 120px, max 155px) to 180px (min 160px, max 240px) across Dashboard, Alarms, and Statistics views, ensuring descriptive single-word and compound aliases fit comfortably on a single line.

## [2026.10.11.5] - Long Message Garbage Filter Fix, SDR Supervisor Heartbeat & Device Conflict Diagnostics

### Fixed
- **Garbage Filter Repetition Calculation for Long Messages**: Fixed a critical flaw in `is_garbage_message` where legitimate multi-line messages over ~250 characters (e.g. system volume warnings, incident reports) were erroneously classified as repetitive noise and silently discarded due to low `unique_ratio`. Repetitive noise is now accurately detected by checking for messages with 3 or fewer distinct characters across >15 length.
- **Transparent Filter Logging**: Promoted dropped garbage message logging from `DEBUG` to `INFO` so filtered messages and their addresses are directly visible in Docker/system logs with the exact snippet dropped.

### Added
- **Periodic Supervisor Heartbeat**: Integrated a 60-second periodic heartbeat into `sdr_processor.py` logging the real-time operational status, PID, running state, and time since last decoded message for every configured SDR receiver.
- **Unrestricted rtl_fm Stderr Logging**: Removed aggressive keyword filtering on `rtl_fm` stderr output, allowing all device initialization, tuner frequency tuning, device enumeration, and USB errors (`usb_open`, `usb_claim_interface`, `no matching device`) to be immediately visible in container logs.
- **Multi-SDR USB Device Conflict Detection**: Added explicit warnings when multiple SDR instances lack assigned `-d` serial/device index numbers, warning of potential device 0 contention between dongles.
- **Detailed Exit Diagnostics**: Enhanced process termination logging to report exact exit codes for both `rtl_fm` and `multimon-ng` along with the last captured stderr output from the failing process.

## [2026.10.11.4] - Full-Width Settings Overhaul, Live Typography Preview & Seamless Auto-Save

### Added
- **Full-Width Responsive Settings Layout**: Expanded the settings container from an 800px column to a full-width responsive grid (`max-width: 1440px`) utilizing modern widescreen displays.
- **Interactive Live Typography Preview**: Added a side-by-side real-time POCSAG message preview in the "Utseende & Visning" tab that dynamically reflects font family, text size slider changes, and theme styling in real-time.
- **Seamless Auto-Save (Zero Save Buttons)**: Removed manual "Save" buttons across appearance, font, slider, and retention forms. Toggles and selects save immediately on change; range sliders and numeric inputs save with debounced background requests.
- **Auto-Save Status Badge**: Added an animated header badge displaying live synchronization states ("Alla ändringar sparade", "Sparar ändringar...", "Kunde inte spara").
- **Modal-Based SDR Receiver Creation**: Replaced browser `prompt()` with an integrated modal dialog for adding new SDR receivers with custom name and frequency validation.
- **SDR Card Grid**: Redesigned multi-SDR receiver cards into an adaptive responsive grid with quick-toggle switches and hardware management links.

### Changed
- **Targeted SDR Process Restarts**: Optimized `/api/settings` to only restart radio decoding processes (`rtl_fm` / `multimon-ng`) when actual radio/hardware parameters change, allowing instant appearance and retention adjustments without interrupting live reception.
- **Complete Swedish Localization in Settings**: Translated all settings tabs, forms, descriptions, tooltips, and modal dialogs to Swedish.

## [2026.10.11.3] - Unified Rules & Triggers, Watchdog USB Health Verification & CalVer Sidebar

### Added
- **Unified Rules & Triggers Management**: Combined CapCode Aliases and Alert Words into a streamlined tabbed view under `/rules` with automatic routing and backward compatibility for `/aliases` and `/alerts`.
- **Dynamic CalVer Sidebar Display**: Injected `app_version` via Flask context processor and displayed the version badge under "POCSAG Monitor" in the sidebar when expanded.
- **Live SDR Process Status & PIDs**: Added `get_sdr_runtime_status()` exposing live `rtl_fm` and `multimon-ng` PID numbers, process health, and error messages on the SDR Receivers cards in Settings.
- **Floating Goto Top Button & Pagination Auto-Scroll**: Restored the floating `#scrollToTop` button and implemented automatic scroll-to-top on DataTables pagination.

### Changed
- **Vertical Metadata Badges**: Aligned frequency, bitrate, function code, and duplicate badges vertically within the `FREQUENCY / META` column across all tables.
- **Watchdog USB Cooldown & Stability Verification**: Eliminated duplicate restart log entries by giving USB hardware a 2.5-second cooldown and actively verifying process liveness and PID stability before logging recovery.
- **Elevated Stderr Diagnostics**: Promoted `rtl_fm` error strings (`usb_claim_interface`, `resetting`, `failed`) from DEBUG to WARNING/ERROR so USB driver issues are directly visible in logs.

## [2026.10.11.2] - Filter SSE Heartbeat & Activity Pings in Live Tables

### Fixed
- **SSE Ping Filter in Live Table**: Fixed an issue where background activity pings (`{type: 'ping'}`) emitted when garbage/duplicate messages are filtered triggered row additions with `undefined` values and `Invalid Date` in the live monitor. Now validates that received event payloads have a valid message `id` before adding to the table.

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
