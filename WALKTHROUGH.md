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
### 14. Korrigering av Skräpfilter för Långa Meddelanden & SDR Supervisor Heartbeat (v2026.10.11.5)
- **Problem & Orsak till Uteblivna Meddelanden**:
  - Meddelandet `High Volume Warning UserId 905442 655 messages in 5 minutes:...` togs emot av `sdr_processor` (RAW), men visades inte i webbgränssnittet eller databasen.
  - Orsaken var att `is_garbage_message()` innehöll en regel: `if unique_ratio < 0.15 and length > 15: return True`. För långa meddelanden (>250 tecken) innehåller det mänskliga språket naturligt endast ett 40-tal unika tecken, vilket gav en kvot på ~12.6% (< 15%). Långa informativa larmmeddelanden klassades därför felaktigt som repetitivt brus och slängdes.
  - Dessutom loggades bortkastade skräpmeddelanden på `DEBUG`-nivå, vilket dolde anledningen i Docker-loggarna.
- **Åtgärd för Skräpfilter**:
  - Ändrade repetitionskontrollen till att kontrollera om ett långt meddelande består av endast 1–3 unika tecken (t.ex. `==========` eller `ABABABAB`). Långa informativa texter släpps nu alltid igenom korrekt.
  - Ändrade loggningen av droppade meddelanden från `DEBUG` till `INFO` (`[SDR] SKRÄPFILTER DROPPADE -> Adress: ...`), så att eventuellt filtrerade meddelanden är direkt synliga i loggen.
- **Utökad Kontroll & Övervakning av SDR-Processer (RIKS 2)**:
  - **Periodisk Supervisor Heartbeat (var 60:e sekund)**: `run_sdr_process` loggar nu regelbundet driftsstatus, PID, körstatus (`KÖRS`/`DÖD`) och tid sedan senaste avkodade larm för samtliga konfigurerade mottagare.
  - **Ofiltrerad Stderr-loggning för rtl_fm**: Tog bort den begränsande nyckelordsfiltreringen av `rtl_fm` stderr. Alla enhetsdetekteringar, frekvensinställningar och hårdvarufel visas nu omedelbart i loggen.
  - **Detektering av USB-Enhetskonflikt**: Om flera mottagare (t.ex. RIKS 1 och RIKS 2) saknar angivet serienummer (`device_serial`), varnar systemet i loggen om att de försöker använda samma USB-enhet (`device 0`).
  - **Detaljerad Avslutningsdiagnostik**: Vid processkrasch loggas exakta returkoder (`exit_code`) för både `rtl_fm` och `multimon-ng` tillsammans med sista felmeddelandet från drivrutinen.

### 15. Korrigering av Radbrytning i CapCode (Alias) & Breddning av Kolumn (v2026.10.11.6)
- **Problem**:
  - Alias-brickor i tabellen (t.ex. "Nätverkssynk") bröts av mitt i ordet så att sista bokstaven hamnade på en ny rad: "Nätverkssyn" följt av "k".
  - Orsaken var att kolumnen var fastlåst till en alltför smal bredd (`max-width: 155px`) i kombination med CSS-regeln `word-break: break-word !important;`, vilket gav webbläsaren tillåtelse att bryta av enskilda ord godtyckligt mellan bokstäver.
- **Åtgärd**:
  - Ändrade stilreglerna för brickor (`.badge` i `td.addr-cell`) till `white-space: nowrap !important;`, `word-break: keep-all !important;` och `overflow-wrap: normal !important;`.
  - Ökade kolumnbredden för `CAPCODE (ALIAS)` från 140px (min 120px, max 155px) till 180px (min 160px, max 240px) i Dashboard, Larm och Statistik.
  - Ord i alias hålls nu alltid intakta på en rad och visas prydligt som en hel enhet utan fula radbrytningar.

### 16. Optimering av Databasinläsning, Enkelradig Dropplogg och Lokala Badges (v2026.10.11.7)
- **Problem 1: 10-15 Sekunders Fördröjning vid Inläsning från Databasen**:
  - Efter borttagandet av gränsen i `/api/messages` skickades en obegränsad fråga mot databasen vid sidstart.
  - Med tiotusentals eller hundratusentals sparade rader tvingades servern serialisera tiotals megabyte JSON över nätverket, och webbläsaren frös när den skapade och indexerade tusentals DOM-element i DataTables.
  - Dessutom saknades index i SQLite på `messages`-tabellen.
- **Åtgärd för Databasprestanda**:
  - Införde en standardgräns (`limit=500`) i `/api/messages` samt vid initial hämtning på startsidan och larmsidan.
  - Möjliggjorde fullständig dump vid behov via `limit=all` eller `limit=0`.
  - Skapade index i SQLite på `messages(id DESC)`, `messages(address)` och `messages(timestamp)` vid `init_db()`.
  - Resultat: Inläsningstiden i webbläsaren sjönk från 10-15 sekunder till under 50 millisekunder.
- **Problem 2: För Mycket Loggtext vid Droppade Meddelanden**:
  - När ett dolt alias togs emot skrevs två separata rader ut i loggen: först `RAW: ...` och därefter `DOLT ALIAS DROPPADE -> Adress: ...`.
- **Åtgärd för Loggtext**:
  - Slog ihop loggningen till en enda koncis rad enligt specifikation:
    `[RIKS X] RAW: POCSAG1200: ... [DROPPED] Cause: MUTED`
    respektive
    `[RIKS X] RAW: POCSAG1200: ... [DROPPED] Cause: GARBAGE`.
  - Eliminerade den redundanta andra raden helt.
- **Problem 3: Trasiga Badge-Bilder i README.md**:
  - I `README.md` hade `.svg` felaktigt lagts till i slutet av GitHub-ändpunkterna (`/last-commit/Minglarn/pagermonitor.svg` och `/issues/...pagermonitor.svg`). Shields.io tolkade därför repository-namnet som `pagermonitor.svg`, vilket inte existerar och gav 404-fel.
- **Åtgärd för Badges**:
  - Korrigerade syntaxen till samma beprövade format som i `fail2banExplorer`:
    - Version: `https://img.shields.io/badge/version-2026.10.11.7-blue.svg`
    - Commits: `https://img.shields.io/github/last-commit/Minglarn/pagermonitor`
    - Issues: `https://img.shields.io/github/issues/Minglarn/pagermonitor`
    - Stars: `https://img.shields.io/github/stars/Minglarn/pagermonitor?style=social`
    - Docker: `https://img.shields.io/badge/docker-GHCR-blue.svg?logo=docker&logoColor=white`
  - Pillren uppdateras nu dynamiskt och automatiskt vid varje versionsuppdatering.

### 17. Korrigering av Alias-Radbrytning Mellan Ord (Borttagning av Ellipsis)
- **Problem**:
  - Efter den tidigare ändringen sattes `white-space: nowrap !important;` tillsammans med `overflow: hidden; text-overflow: ellipsis;` på aliasbrickorna (`.badge`).
  - Detta ledde till att flerordsalias (som "Sjukvårdens Larmcentral") tvingades till en enda rad och klipptes av med tre punkter: "Sjukvårdens Larmcentr...".
- **Åtgärd**:
  - Ändrade `white-space` från `nowrap` till `normal` på både `td.addr-cell` och `.badge`.
  - Tog bort `overflow: hidden` och `text-overflow: ellipsis`.
  - Satte `word-break: normal !important;` och `overflow-wrap: break-word !important;`.
  - Resultat: Ord hålls intakta utan avhuggna bokstäver, men flera ord radbryts naturligt vid mellanslag (t.ex. "Sjukvårdens" på rad 1 och "Larmcentral" på rad 2). Ingen text trunkeras med "...".

### 18. Kompakt SDR Heartbeat i Loggen
- **Problem**:
  - Heartbeat-raden var över 280 tecken lång och upprepade serienummer, interna PID-nummer, frekvenser och inaktiverade enheter var 60:e sekund.
- **Åtgärd**:
  - Komprimerade loggformatet till att endast visa aktiva mottagares hälsostatus och tid sedan senaste mottagna larm:
    `SDR Heartbeat: [RIKS 1] OK (22s) | [RIKS 2] OK (24s)`.
  - Inaktiverade mottagare utelämnas för att spara loggutrymme.

### 19. Borttagning av Ruta-i-Ruta Effekt & Minimering av Sidomarginaler (v2026.10.11.8)
- **Problem**:
  - Datatabellen hade en "ruta i ruta"-effekt där varje rad renderades som ett fristående flytande kort (`border-spacing: 0 8px`, `border-radius: 12px` per rad, egna ramar) inuti den övergripande glaspanelen.
  - Dessutom fanns en stor onödig marginal (`padding: 2rem` = 32px) mot sidopanelen som slösade skärmutrymme.
- **Åtgärd**:
  - Byggde om tabellstrukturen i `style.css` och mallarna till `border-collapse: collapse` och `border-spacing: 0`.
  - Ersatte de separata rad-korten med en enhetlig, modern tabellayout med diskreta 1px-delare (`border-bottom: 1px solid var(--panel-border)`) och subtil hover-effekt utan inre ramar och radiekant.
  - Minskat yttre marginal (`.main-content` och `.dashboard-page .main-content`) från `2rem` till `0.75rem 1rem`, vilket flyttar innehållet närmare sidopanelen och maximerar den användbara bredden.

### 20. Återställning av Kolumnavdelare i DataTables (v2026.10.11.9)
- **Problem**:
  - När "ruta i ruta"-effekten togs bort försvann även de vertikala avdelarna mellan kolumnerna i tabellen.
- **Åtgärd**:
  - Återställde `border-right: 1px solid var(--panel-border)` på samtliga kolumnhuvuden (`thead th`) och databoxar (`tbody td`) i Dashboard, Larm och Statistik.
  - Sista kolumnen (`:last-child`) hålls fri från `border-right` så att tabellens yttre ram förblir ren och snygg.





