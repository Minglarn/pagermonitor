# Walkthrough: PagerMonitor Development and Features

## Version Information
- **CalVer**: `2026.10.11`
- **Date**: 2026-10-11
- **Language**: English

---

## Overview of Implemented Features

### 1. Dedicated Alarms Page & Dashboard with DataTables 2
- **DataTables 2 in Alarms and Dashboard**: Both the live Dashboard (`/`) and Alarms view (`/alarms`) are powered by DataTables 2 for instant client-side sorting, pagination, search, and real-time SSE row additions.
- **Sticky Table Headers**: Column header rows (`<thead>`) remain fixed at the top of the viewport during scrolling using `position: sticky; top: 0;` and solid blurred backdrop styling, keeping column contexts visible through large datasets.
- **Compact Controls Toolbar**: The top controls row (`.dt-layout-row` housing page length and search input) has been vertically compressed by over 50% with reduced padding and streamlined inputs for maximum vertical screen efficiency.
- **Persistent Table Settings (stateSave)**: Enabled persistent state saving in `localStorage` for 1 year (`stateSave: true; stateDuration: 31536000`). User selections such as rows per page (25, 50, 100, All), column sorting directions, and search filters are preserved across page reloads and sessions.
- **CapCode (Alias) Word Wrapping**: Solved the issue where long alias names (e.g. "Naturhistoriska Riksmuseet") stretched the table. Applied `white-space: normal; word-break: break-word;` with bounded width (~140px) so long names wrap cleanly without eating message space.
- **Dynamic Auto-Sizing**: Metadata columns (`#`, `Timestamp`, `Frequency / Meta`, `CapCode`, `Hit`, `Actions`) shrink tightly to their content, allowing the `Message` column to consume all available display width.

### 2. Interactive Date Range Picker in Statistics
- **From & To Date Pickers**: Replaced manual text entry with native interactive date pickers with `color-scheme: dark` that open calendar popups on click (`showPicker()`).
- **Quick Presets**: Instant selection buttons for "Today", "Yesterday", "Last 7 Days", and "Last 30 Days".
- **Dynamic Range Activity**: If From and To are identical, displays a 24-hour distribution. If a range is selected, displays daily activity distribution and lists all messages in the selected interval.
- **Backend Endpoints**: Added `GET /api/stats/range?start=...&end=...` and `GET /api/stats/range-activity?start=...&end=...`.

### 3. Database Stat & Automated Retention (Settings -> Database Stat)
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

### 4. Application Security & HTTP Hardening
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

### 5. Internationalization & English Translation
- Converted all user interface templates (`index.html`, `larm.html`, `aliases.html`, `alerts.html`, `statistics.html`, `settings.html`, `sdr_settings.html`) to English.
- Converted API response messages and internal logs to English.
- Updated documentation (`README.md`, `WALKTHROUGH.md`, `CHANGELOG.md`) to English.
- Strictly verified that no emojis are present across any templates or pages.

### 6. Automated Test Suite
- Automated pytest test suite covering:
  - Security headers and authentication enforcement.
  - Alarms endpoint (`/alarms`) and query filtering (`alerts_only=1`).
  - Database statistics endpoint (`/api/database/stats`).
  - Auto-prune logic and timestamp comparison.
