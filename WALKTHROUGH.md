# Walkthrough: PagerMonitor Development and Features

## Version Information
- **CalVer**: `2026.10.11`
- **Date**: 2026-10-11
- **Language**: English

---

## Overview of Implemented Features

### 1. Dedicated Alarms Page with DataTables
- **Navigation**: Sidebar link `Alarms` (`/alarms`, with `/larm` retained as backwards-compatible alias).
- **Template**: `templates/larm.html`.
- **DataTables Integration**:
  - Rebuilt table using **DataTables 2** for client-side sorting on all columns (ID, timestamp, frequency, CapCode, message, hit word).
  - **Dynamic Auto-Sizing**: All metadata columns (`#`, `Timestamp`, `Frequency / Meta`, `CapCode`, `Hit`, `Actions`) shrink tightly to their exact content (`width: 1%; white-space: nowrap`), while the `Message` column automatically expands to consume all available display width.
  - **Real-Time SSE Sync**: Incoming alarms from Server-Sent Events (`/stream`) are instantly added via `dataTable.row.add(rowNode).draw(false)` and animated with subtle alert pulsing (`new-alarm-pulse`).
  - **Controls**: Configurable pagination (25, 50, 100, All), quick filtering search input synchronized with header search, and dark glassmorphic styling matching OLED themes.
  - **Inline Actions**: Protect/lock messages from retention purging, delete with confirmation modal, and interactive CapCode alias editing.

### 2. Database Stat & Automated Retention (Settings -> Database Stat)
- **Tab Overhaul**: Renamed the Maintenance tab to **Database Stat**.
- **Metric Cards (KPIs)**:
  - **Total Messages**: Complete row count.
  - **Watchlist Hits**: Count of messages triggering alert words.
  - **Database Size**: Formatted disk usage (KB / MB).
  - **Oldest Entry**: Timestamp of the earliest recorded message.
  - **Newest Entry**: Timestamp of the latest recorded message.
  - **Protected Messages**: Number of locked messages immune to automatic deletion.
  - **Unique CapCodes**: Count of distinct pager addresses in storage.
  - **Duplicate Messages**: Count of detected duplicate transmissions.
- **Automated Data Retention & Pruning**:
  - **Audit Findings**: Previously, `prune_messages()` was only executed when manually triggered via button click. No automated scheduler existed.
  - **Implementation**:
    - Added `auto_prune_enabled` and `auto_prune_days` settings.
    - Added `auto_prune_if_enabled()` in `database.py`.
    - Integrated a daemon background thread `start_prune_scheduler()` in `app.py` executing pruning every 6 hours.
    - Fixed SQLite ISO date compatibility using `datetime(replace(timestamp, 'T', ' '))` to ensure accurate chronological filtering against SQLite `datetime('now', '-' || ? || ' days')`.
    - Automatic `VACUUM` executed after purging to reclaim disk space.
  - **Manual Actions**: Buttons for immediate message pruning by retention days and full database purge.

### 3. Application Security & HTTP Hardening
- **HTTP Basic Authentication**:
  - Configurable via `AUTH_USER` and `AUTH_PASS` in `docker-compose.yml` and `.env`.
  - Disabled when `AUTH_PASS` is empty (suitable for reverse proxy deployments like Nginx Proxy Manager).
  - Uses `hmac.compare_digest` with UTF-8 encoding to resist timing attacks.
- **Security Response Headers**:
  - `X-Frame-Options: SAMEORIGIN` (prevents Clickjacking).
  - `X-Content-Type-Options: nosniff` (prevents MIME sniffing).
  - `X-XSS-Protection: 1; mode=block`.
  - `Referrer-Policy: strict-origin-when-cross-origin`.
  - `Content-Security-Policy`.
- **Payload Protection**:
  - Maximum upload / request body capped at 2MB (`MAX_CONTENT_LENGTH`) to protect against memory exhaustion attacks.

### 4. Internationalization & English Translation
- Converted all user interface templates (`index.html`, `larm.html`, `aliases.html`, `alerts.html`, `statistics.html`, `settings.html`, `sdr_settings.html`) to English.
- Converted API response messages and internal logs to English.
- Updated documentation (`README.md`, `WALKTHROUGH.md`, `CHANGELOG.md`) to English.
- Strictly verified that no emojis are present across any templates or pages.

### 5. Automated Test Suite
- Automated pytest test suite covering:
  - Security headers and authentication enforcement.
  - Alarms endpoint (`/alarms`) and query filtering (`alerts_only=1`).
  - Database statistics endpoint (`/api/database/stats`).
  - Auto-prune logic and timestamp comparison.
