# Walkthrough: PagerMonitor Development and Features

## Version Information
- **CalVer**: `2026.10.11.3`
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
  - Multi-SDR watchdog process monitoring and self-healing.

### 7. Multi-SDR Watchdog & Self-Healing
- **Automatic Process Crash Recovery**:
  - Previously, if an SDR background process (`rtl_fm` or `multimon-ng`) crashed, the instance was retained in `active_instances` with dead processes, preventing the supervisor loop from restarting it.
  - Implemented real-time process monitoring checking `p1.poll()`, `p2.poll()`, and thread liveness.
  - On unexpected termination, `stop_instance_procs` cleans up remaining resources and triggers an automatic restart with backoff protection to avoid tight CPU loops.
- **Persistent Logging & Real-time Alerts**:
  - Automatically records a system event in the database (`messages.db`) upon watchdog recovery (`address: SYSTEM`, `frequency: RESTART`, `alias: <Instance Name>`).
  - Allows searching and auditing receiver restarts weeks or months later directly in the Dashboard search and Statistics filters.
  - Pushes an immediate Server-Sent Event (SSE) to all connected clients displaying a floating Toast notification banner and highlighting the recovery row in amber (`RESTART` badge).

### 8. Statistics Table DataTables 2 Migration
- Converted historical messages table in `statistics.html` to DataTables 2.
- Resolved column layout overlap where frequency and timestamp badges collided.
- Added persistent table settings (`stateSave`), customizable pagination (25, 50, 100, All), fast filtering, column sorting, and smooth message deletion/locking.

### 9. Vertical Meta Badges & Smooth Goto Top Navigation
- **Vertical Badge Stacking in FREQUENCY / META**:
  - Replaced horizontal inline-block layout with a flex column container (`.meta-wrapper`).
  - Metadata badges (`[Frequency]`, `[Bitrate]`, `[Function]`, `[Duplicate]`) now cleanly stack underneath each other across the Dashboard, Alarms, and Statistics tables.
- **Floating "Goto Top" Button**:
  - Re-introduced `#scrollToTop` button appearing when scrolled down > 150px.
  - Smoothly animates both the inner table container and page window back to top on click.
- **Automatic Scroll on DataTables Pagination**:
  - Bound DataTables `page.dt` event to automatically scroll back to the top of the table upon page change.

### 10. Unified "Rules & Triggers" View & CalVer in Sidebar
- **Unified Navigation & Page**:
  - Combined separate "Capcode Alias" and "Alert Words" pages into a single **Rules & Triggers** (`/rules`) view with sub-tabs.
  - Maintained full backwards compatibility with `/aliases` and `/alerts` routes seamlessly mapping to the new interface.
- **CalVer Display in Sidebar**:
  - Injected `app_version` globally via Flask context processor `inject_globals`.
  - Displayed version tag (`vYYYY.0M.0D`) under "POCSAG Monitor" in the sidebar logo when the sidebar is expanded.
  - Automatically hidden when the sidebar is collapsed to keep icons clean.

### 11. Watchdog USB Cooldown, Health Verification & SDR Telemetry
- **Elimination of Duplicate Recovery Events**:
  - When an SDR process died, previously the system attempted an instant restart. If the USB driver was still releasing handles (`usb_claim_interface error -6`), the new process crashed immediately, causing a second restart 3 seconds later.
  - Added a 2-second USB cooldown pause upon crash detection to allow the kernel / libusb stack to cleanly release devices.
- **Startup Stability Verification Before Recovery Announcement**:
  - The watchdog now runs an asynchronous 2.5-second stability grace period after starting `rtl_fm` and `multimon-ng`.
  - Only when both processes are verified actively running (`p1.poll() is None and p2.poll() is None`) is a single, verified recovery event logged to the database and broadcast via SSE.
  - If a process fails during the startup period, a descriptive error with exit codes is logged, no false recovery is broadcast, and an orderly backoff retry is scheduled.
- **Live Process Telemetry & Diagnostics**:
  - Elevated `rtl_fm` stderr error and warning messages to `logger.warning`/`logger.error` so USB driver resets and errors are fully visible in container logs.
  - Added `get_sdr_runtime_status()` returning active PID numbers, uptime, and last recorded error.
  - Updated Settings -> SDR Receivers cards to show real-time status badges (`Running (PID: 1234)` or `Not Running`).

### 12. Full Database History Loading & Active Alias Protection
- **Full Database Message Loading**:
  - Removed the arbitrary `limit=200` query parameter when initializing the live Dashboard (`/`) and default `100` limit in `/api/messages`.
  - The client now fetches all database records into DataTables 2 so searches (e.g. `RESTART`, specific addresses, keywords) search across the entire database history rather than just the latest 200 rows.
- **Active Alias Preservation**:
  - Restructured message processing in `sdr_processor.py` so alias lookup occurs before the garbage filter.
  - User-configured active aliases (e.g. `1245952` -> "Nätverkssynk") are permanently exempt from the noise/entropy filter so their transmissions are never dropped.
### 13. Full-Width Settings Overhaul, Live Typography Preview & Seamless Auto-Save
- **Bred och Luftig Gränssnittslayout (Full Width)**:
  - Tidigare var inställningssidan låst till en smal `max-width: 800px` kolumn som lämnade över hälften av skärmen tom.
  - Skapade `.settings-container` med full responsiv bredd (`max-width: 1440px`, 100% vidd) som ger generöst utrymme för kort, reglage och tabeller.
- **Sömlös Automatisk Sparning (Auto-Save)**:
  - Eliminerade alla manuella "Spara"-knappar i inställningsfliken.
  - Dropdowns (`theme`, `message_font`) och togglar (`garbage_filter`, `auto_prune_enabled`) sparas omedelbart vid förändring.
  - Sliders (`message_font_size_slider`, `garbage_sensitivity_slider`) och textfält (`auto_prune_days`) sparas med bakgrunds-debouncing (350–400 ms) för mjuk och snabb interaktion.
  - Implementerade en diskret statusindikator i sidhuvudet (`#autoSaveBadge`) med realtidslägen: "Alla ändringar sparade" (grön bock), "Sparar ändringar..." (snurrande laddare) och "Kunde inte spara" (röd varning).
- **Interaktiv Live Typography & Appearance Preview**:
  - Delade upp "Utseende & Visning" i en tvåkolumns split-layout: inställningskontroller till vänster och en levande förhandsgranskningsruta till höger.
  - Förhandsgranskningen visar ett realistiskt larmmeddelande och uppdaterar typsnitt (`font-family`) samt textstorlek (`font-size`) i realtid när användaren drar i reglagen.
- **Modern Modal för SDR-Mottagare**:
  - Ersatte webbläsarens inbyggda `prompt()` med en integrerad modaldialog för att lägga till nya mottagare med namn och frekvensvalidering.
- **Svensk Lokalisering av Inställningar**:
  - Samtliga flikar, formulärfält, hjälpetiketter och dialoger i inställningsfliken är översatta till ren svenska.
- **Optimerad SDR-Processomstart**:
  - Ändrade `/api/settings` i `app.py` så att processomstart av `rtl_fm` och `multimon-ng` endast sker när faktiska radio-/hårdvarunycklar ändras. Ändringar av typsnitt, textstorlek, tema eller gallring avbryter inte längre radiomottagningen.

