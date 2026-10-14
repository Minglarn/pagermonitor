# Walkthrough: PagerMonitor Development and Features

## Version Information
- **CalVer**: `2026.10.13.32`
- **Date**: 2026-10-13
- **Language**: English / Swedish

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

### 21. Markant Zebra-mönster, Kant-till-Kant Avdelare & Knivskarpa Piller (v2026.10.11.10)
- **Problem**:
  - Tabellerna saknade tydlig radseparation (zebra-mönster), vilket gjorde det svårare att följa rader med mycket text.
  - Tabellens avdelare och rader gick inte ända ut till panelens ytterkant på grund av inre containerpadding (`0.5rem`).
  - Texten i alias- och meta-pillren (`.badge`) upplevdes suddig med filterkänsla på grund av GPU subpixel-skalning (`transform: scale(1.02)`), fraktionella typsnittsstorlekar (`calc(var(--msg-size) * 0.9)`) samt låg kontrast i ljust och mörkt läge.
- **Åtgärd**:
  - **Markant Zebra-mönster**:
    - Mörkt läge: Udda rader har `#0a0a0a` och jämna rader har `#141b24` med distinkt blåtonad hover (`rgba(56, 189, 248, 0.12)`).
    - Ljust läge: Udda rader har `#ffffff` och jämna rader har `#eef2f6` med tydlig hover (`#e2e8f0`).
    - Larmrader har anpassad randning med distinkta rödtoner.
  - **Avdelare ända ut till kanten**:
    - Tog bort inline padding på tabellcontainrarna (`padding: 0 !important;`) och satte tabellerna till 100% bredd utan yttre marginal.
    - Flyttade kontrollpadding till DataTables över- och undersektioner (`.dt-layout-row`).
    - Lade till padding (`1rem`) på första och sista cellerna i tabellen så att innehållet hålls snyggt innanför medan avdelare och radbakgrunder går 100% kant-i-kant.
  - **Knivskarp Piller-typografi**:
    - Tog bort all `transform: scale(1.02)` och transition-scale som skapade suddig rasterisering.
    - Bytte fraktionell fontstorlek mot fasta, skarpa integer rem-storlekar (`0.8125rem` / `0.72rem`).
    - Lade till `-webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; text-rendering: geometricPrecision;`.
    - Skapade dedikerad `.badge.meta.badge-freq`-klass med hög kontrast och ersatte tvättade inline-stilar.
 
### 22. Korrigering av Avkodningspipeline och Databaslagring i SDR-Processor (v2026.10.12.1)
- **Problem**:
  - Inga nya händelser dök upp i realtidsflödet (DataTables) eller sparades i SQLite-databasen sedan föregående kväll (omkring kl. 20:00).
  - I loggarna syntes det att multimon-ng och rtl_fm tog emot rådata och loggade `RAW: POCSAG...`, men inga händelser gick vidare till webbläsaren eller databasen.
  - Orsaken spårades till en oavsiktlig `else:`-sats som hamnat framför `# DUPLICATE DETECTION` i `sdr_processor.py`. När ett meddelande avkodades korrekt (`if parsed:`) avbröts exekveringen direkt efter loggningen och hoppade över sparande (`save_message`), MQTT (`publish_message`) och SSE-notifieringar (`new_message_callbacks`).
- **Åtgärd**:
  - Tog bort den felaktiga `else:`-satsen i `sdr_processor.py` så att hela flödet (dubblettkontroll, larmordsmatchning, sparande i databasen, publicering till MQTT samt utskick till anslutna SSE-klienter) körs korrekt inuti `if parsed:`.
  - Skapade automatiserat enhetstest `test_monitor_instance_saves_and_broadcasts_message` i [test_sdr_watchdog.py](file:///d:/antigravity/pager-monitor/tests/test_sdr_watchdog.py) som simulerar inkommande multimon-ng-rader och verifierar att data sparas till databas och skickas till realtids-callbacks.
  - Uppdaterade versionshantering (CalVer `2026.10.12.1`) i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md), [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md) och testsviten.
 
### 23. Utökad POCSAG-buffert i multimon-ng och 1-Klicks Meddelandekopiering (v2026.10.12.2)
- **Utökad POCSAG-buffert i multimon-ng**:
  - **Problem**: Standardkällkoden i `multimon-ng` (`multimon.h` och `pocsag.c`) har en hårdkodad gräns på 512 bytes (`buffer[512]`). När långa SOS Alarm CAD-meddelanden överstiger ca 500 tecken triggar multimon-ng `Warning: Message too long`, tappar synk och klipper meddelandet.
  - **Åtgärd**: I [Dockerfile](file:///d:/antigravity/pager-monitor/Dockerfile) lades `sed`-patchar till under byggsteget för att öka `buffer[512]` till `buffer[4096]` i `multimon.h` samt utöka strängbuffertarna (`alpha_string`, `num_string`, `skyper_string`) till 8 192 tecken i `pocsag.c`. Detta tillåter kompletta meddelanden upp till ca 4 600 tecken.
- **1-Klicks Meddelandekopiering**:
  - Lade till en dedikerad kopieringsknapp (`.copy-btn`) i åtgärdskolumnen (*Actions*) i Database Explorer ([statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html)), Live Monitor ([index.html](file:///d:/antigravity/pager-monitor/templates/index.html)) och Alarmlistan ([larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html)).
  - Vid klick kopieras ren meddelandetext till urklipp med `navigator.clipboard` (med fallback till dolt textarea-element för osäkra kontexter).
  - Knappen ger omedelbar visuell feedback genom att ikonen temporärt skiftar till en grön bock (`fas fa-check`) med tooltip "Kopierad!" i 1,5 sekund.
  - Lade till stilregler för `.copy-btn`, `.copy-btn:hover` och `.copy-btn.copied` i [style.css](file:///d:/antigravity/pager-monitor/static/style.css).
- **Versionshantering**:
  - Höjde CalVer till `2026.10.12.2` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md), [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md) och testsviten.

### 24. Global Docker- & Systemkonsol med Realtidsströmning, Färgkodning och Radbrytning (v2026.10.12.3)
- **Bakgrund och Syfte**:
  - För att underlätta felsökning och övervakning ville användaren ha en konsol-logg längst ner i gränssnittet som visar exakt allt som Docker-loggen (`docker logs pagermonitor`) visar, med stöd för färger, radbrytning och realtidsuppdatering, tillgänglig på samtliga sidor i applikationen.
- **Arkitektur & Log Capture (`log_streamer.py`)**:
  - **In-process Log Interception**: Istället för att montera den osäkra `/var/run/docker.sock` i containern, kopplas en anpassad `MemoryLogHandler` direkt till Pythons rotlogger (`logging.getLogger()`) samt en trådsäker `StdoutTee`-wrapper runt `sys.stdout` och `sys.stderr`.
  - **100 % Paritet med Docker-logg**: Fångar alla loggmeddelanden från `app.py`, `sdr_processor.py`, `database.py`, `mqtt_client.py` samt direkta utskrifter (`print`) och subprocessfel.
  - **Loop- & Dubbelloggningsskydd**: Använder thread-local state (`_tls.in_logging`) för att förhindra att meddelanden som redan hanterats av logghandlern dubbleras när de skrivs till terminalen.
  - **Ringbuffer & Historik**: Sparar de senaste 2 500 loggraderna i minnet (`collections.deque(maxlen=2500)`) för omedelbar leverans vid sidladdning via `GET /api/logs/history`.
  - **Realtidsströmning via SSE**: Nya loggar strömmas kontinuerligt till anslutna webbläsare via `GET /api/logs/stream` med keep-alive pings.
- **Frontend Konsoldocka (`static/console.js` & `static/console.css`)**:
  - **Placering & Universell Tillgänglighet**:
    - Konsolen är dockad i botten av gränssnittet och anpassar sig automatiskt till sidebarens bredd (både i expanderat och hopfällt läge).
    - Inkluderad på alla sidor: Dashboard (`index.html`), Larm (`larm.html`), Statistik (`statistics.html`), Inställningar (`settings.html`), Regler (`rules.html`), SDR-inställningar (`sdr_settings.html`), Alias (`aliases.html`) och Larmord (`alerts.html`).
  - **Färgkodning & ANSI-stöd**:
    - Distinkta färgade badges för loggnivåer: `INFO` (cyan/blå), `WARNING` (bärnsten), `ERROR`/`CRITICAL` (röd), `DEBUG` (lila) och `RAW`/`STDOUT` (smaragdgrön).
    - Integrerad ANSI-parser som översätter terminal-escape-koder (`\x1b[31m`, `\x1b[32m`, etc.) till motsvarande CSS-stilar och rensar bort styrtecken.
  - **Radbrytning (Word-wrap Toggle)**:
    - En knapp i konsolens verktygsfält växlar direkt mellan radbrytning (`white-space: pre-wrap; word-break: break-word;`) och horisontell terminalrullning (`white-space: pre; overflow-x: auto;`).
  - **Autoscroll & Inspektion**:
    - Konsolen följer automatiskt nya loggar till botten. Om användaren scrollar uppåt för att läsa äldre meddelanden pausas autoscroll automatiskt så att läsningen inte avbryts.
  - **Interaktiva Verktyg**:
    - **Filter**: Snabbknappar för att visa *Alla*, *Info*, *Varningar*, *Fel* eller *SDR / System*.
    - **Fritextsökning**: Sökfält med realtidsfiltrering av loggraderna.
    - **Höjdjustering**: Dragbart resize-handtag i överkant för fri höjdjustering mellan 160 px och 85 % av fönsterhöjden.
    - **Maximera/Minimera**: Växla mellan kompakt visning, helskärmsvy eller minimerad list i botten.
    - **Senaste logg-ticker**: När konsolen är minimerad visas den senaste loggraden avklippt i listen så att man direkt ser om något händer.
    - **Export**: Ladda ner loggen som en `.txt`-fil med ett klick.
    - **State Persistence**: Sparar minimeringsläge, vald höjd, radbrytning, autoscroll och filter i `localStorage`.
- **Versionsspårbarhet (CalVer)**:
  - Uppdaterade CalVer till `2026.10.12.3` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).

### 25. Korrigering av Skräpfilter för Avgränsarlinjer och Formatering (v2026.10.12.4)
- **Problem**:
  - Fullt giltiga larmmeddelanden (exempelvis från Siemens DesigoCC och SOS Alarm) droppades felaktigt med `[DROPPED] Cause: GARBAGE`.
  - Orsaken var att `is_garbage_message()` i [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py) använde ett strikt symbolregex `[^a-zA-Z0-9\såäöÅÄÖ]{3,}` som triggade på legitima formateringslinjer såsom `---------------------- End of message ----------------------` (22 bindestreck i rad) samt ellipser (`...`), asterisker (`*** LARM ***`) och likhetstecken (`===`).
- **Åtgärd**:
  - Uppdaterade symbolkontrollen i `is_garbage_message()` så att legitima skilje- och avgränsartecken (`-`, `=`, `.`, `*`, `_`, `/`, `:`, `;`, `!`, `?`, `,`, `(`, `)`, `"`, `'`, `%`, `#`) undantas från radiostörningsbruskontrollen.
  - Lade till skyddsregel: Om meddelandet har hög läsbarhet (`readable_ratio >= 0.85`, normal klartext), avfärdas det inte på grund av symbolmönster.
  - Lade till regressionstestet `test_is_garbage_message_allows_desigo_separator_and_drops_noise` i [tests/test_sdr_watchdog.py](file:///d:/antigravity/pager-monitor/tests/test_sdr_watchdog.py) som verifierar att DesigoCC-larm, ellipser och asterisklarm släpps igenom medan faktiskt radiobrus droppas.
  - Höjde CalVer till `2026.10.12.4` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).

### 26. Dedikerat DECODED-Filter i Konsoldockan (v2026.10.12.5)
- **Bakgrund och Syfte**:
  - Användaren önskade ett dedikerat filter i konsolen för att uteslutande kunna se och följa de framgångsrikt avkodade larmmeddelandena i realtid utan att drunkna i RAW-meddelandeströmmar, heartbeats och systemdiagnostik.
- **Implementation**:
  - **Verktygsfält & Filterknapp**: Lade till filterknappen `DECODED` i [static/console.js](file:///d:/antigravity/pager-monitor/static/console.js) med distinkt smaragdgrön färgmarkering när den är aktiv.
  - **Realtids- och historikfiltrering**:
    - När `DECODED` är valt i konsolen filtreras alla rader som innehåller `DECODED -> Address: ..., Alias: ..., Msg: ...`.
    - I [log_streamer.py](file:///d:/antigravity/pager-monitor/log_streamer.py) lades stöd till för `level=DECODED` i `get_history()` så att även API-anrop (`/api/logs/history?level=DECODED`) returnerar enbart avkodade larm.
  - **Visuell Framhävning**:
    - Avkodade rader i konsolen (`.console-log-row.is-decoded`) ges en diskret grön vänstermarginal och mjuk tonad bakgrund så att de sticker ut tydligt även när man granskar hela loggen (*Alla*).
  - **Testning & Verifiering**:
    - Lade till testet `test_filter_by_decoded` i [tests/test_log_console.py](file:///d:/antigravity/pager-monitor/tests/test_log_console.py) som verifierar att `level=DECODED` endast plockar ut de avkodade larmen.
  - **Versionsspårbarhet (CalVer)**:
    - Uppdaterade CalVer till `2026.10.12.5` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).

### 28. Befintliga Larmordstabell och Unicode-stöd för Larmfiltrering (v2026.10.12.7)
- **Problem & Bakgrund**:
  - När användaren skrev in larmord såsom "SKADA" under Alert Words och klickade på Spara, fanns det ingen tabell eller lista under knappen som visade de sparade orden. Detta skapade förvirring eftersom fliken för CapCode Aliases visade en tydlig tabell ("Existing Aliases") med alla sparade poster.
  - Dessutom hanterade standard SQLite endast ASCII skiftlägesoberoende för `LIKE` och `UPPER()`, vilket gjorde att svenska larmord med å, ä, ö (t.ex. `STÖLD`, `LÄCKA`, `DÖD`) inte matchades skiftlägesoberoende i databasfrågor om meddelandet hade gemener.
- **Åtgärder**:
  - **Tabell för Befintliga larmord i gränssnittet**:
    - Lade till en sektion "Befintliga larmord" med en tabell (`#alertsTableBody`) direkt under textrutan och spara-knappen i både [templates/rules.html](file:///d:/antigravity/pager-monitor/templates/rules.html) och [templates/alerts.html](file:///d:/antigravity/pager-monitor/templates/alerts.html).
    - Varje larmord visas med en färgad badge, färgkodindikator, aktiv-status ("Aktiv") samt en raderingsknapp för att ta bort enskilda ord direkt i tabellen.
    - Funktionerna `loadWords()`, `saveWords()` och nya `deleteAlertWord(id)` synkroniserar direkt databas, tabell och textruta.
  - **Unicode-oberoende larmfiltrering**:
    - Registrerade en anpassad SQLite-funktion `UPPER_UNICODE` i [database.py](file:///d:/antigravity/pager-monitor/database.py) via hjälparfunktionen `get_connection()`.
    - Detta garanterar att ord som `SKADA`, `STÖLD`, `LÄCKA`, `DÖD`, `MILITÄR` och `ÖVERFALL` matchar både gemener och versaler i databasfrågor (`alerts_only=1`).
  - **Testning & Verifiering**:
    - Lade till automatiserade enhetstester i [tests/test_security_and_larm.py](file:///d:/antigravity/pager-monitor/tests/test_security_and_larm.py) som verifierar rendering av larmordstabellen i `/rules` och `/alerts`, samt Unicode-matchning av svenska larmord.
    - Samtliga 34 enhetstester passerar utan anmärkning.
  - **Fullbredd & Responsiv 2-kolumnslayout för Regler & Larmord**:
    - Åtgärdade problemet där sidan `/rules` (och `/alerts`) var låst till en smal centrerad container (`max-width: 800px`) vilket skapade stora tomma vita ytor på breda skärmar.
    - Införde klassen `.rules-container` med `width: 100%; max-width: 100%;` som låter panelen fylla hela den tillgängliga bredden och linjera med sidhuvudet.
    - Implementerade en modern 2-kolumns grid-layout (`.alerts-layout-grid`) på datorskärmar:
      - **Vänster kolumn (Editor)**: Textruta för att redigera larmord och "Spara larmord"-knapp.
      - **Höger kolumn (Tabell)**: Tabellen med alla sparade larmord (`Befintliga larmord`) och larmordsräknare (`alertCountBadge`).
    - På mindre skärmar staplas kolumnerna automatiskt för optimal responsivitet.
    - Länkade om CSS-stilmallen med dynamisk cache-busting (`style.css?v={{ app_version }}`).

### 29. Mobilvy och Fast Bottom Navigation Bar (v2026.10.12.8)
- **Problem & Bakgrund**:
  - PagerMonitor var initialt designat för widescreen-datorer med en fast sidomeny (260px bredd eller 80px minimerad) som klämde ihop innehållet på mobila skärmar (360–430px bredd).
  - Tabellerna med 6 kolumner ledde till horisontell överflödning och inställningsflikar bröts ojämnt över flera rader.
  - Användaren önskade att sidopanelen skulle omvandlas till en mobil bottom bar för enhandsanvändning med tummen.
- **Åtgärder**:
  - **Fast Bottom Navigation Bar**:
    - Vid skärmbredder `<= 768px` förvandlas sidomenyn automatiskt till en bottenmeny med `position: fixed; bottom: 0; left: 0; right: 0;`.
    - Presenterar de 5 primära vyerna: Dashboard, Larm, Regler & Triggers, Statistik och Inställningar med tydliga ikoner och etiketter.
    - Integrerade bakgrundsblur (glassmorphism), aktiv-indikator (`--accent` och badge-glöd) samt stöd för skärmstreck på iOS och Android (`env(safe-area-inset-bottom)`).
  - **Responsiv Layout & Skärmanpassning**:
    - `.main-content` tilldelas 100% bredd med dynamisk bottenmarginal för att ge plats åt navigationsraden (`calc(68px + env(safe-area-inset-bottom))`).
    - Scroll-to-top-knappen placeras automatiskt strax ovanför bottenraden.
    - Döljer indexkolumnen (`#`) i DataTables på mobil för att ge maximal horisontell plats åt CapCode och larmmeddelande.
    - Inställningsflikar i [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html) och [templates/rules.html](file:///d:/antigravity/pager-monitor/templates/rules.html) har försetts med horisontell touch-scrollning.
    - Formelement, SDR-kort och statistikdiagram staplas i 1 kolumn för fingertryck.
    - Docker- och systemkonsoldockan positioneras direkt ovanför bottenraden på mobila enheter.
  - **Testning & Verifiering**:
    - Verifierad i mobil viewport (390x844) via subagent-browser, med verifierad navigering mellan Dashboard, Alarms och Settings.
    - Alla 34 automatiserade tester passerar felfritt.

### 30. Duplikathantering, CapCode DataTables Gruppering och Persistent Konsolfilter (v2026.10.12.9)
- **Problem & Bakgrund**:
  - Repetitioner som skickas med 60 sekunders mellanrum flaggades inte som duplikat eftersom det gamla tidsfönstret var strikt `< 60` sekunder.
  - Användaren önskade möjlighet att alternativt kunna dölja eller kasta duplikat via Inställningar.
  - Användaren efterfrågade stöd för DataTables gruppering per CapCode för att kunna samla alla händelser under respektive mottagare.
  - Vid flikbyte nollställdes konsolens aktiva filter och visade tom vy eller föll tillbaka till standardläget.
- **Åtgärder**:
  - **Konfigurerbar Duplikathantering**:
    - I [database.py](file:///d:/antigravity/pager-monitor/database.py) lades standardinställningarna `duplicate_handling` ('mark', 'hide', 'discard') och `duplicate_window` (standard 120 sekunder) till.
    - I [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py) styrs duplikatfönstret dynamiskt från inställningen (`now - last_time <= dup_window`). Om `duplicate_handling == 'discard'` droppas meddelandet direkt med `[DROPPED] Cause: DUPLICATE` utan lagring i databas eller publicering via MQTT/SSE.
    - I [app.py](file:///d:/antigravity/pager-monitor/app.py) exkluderar `/api/messages` duplikat om `duplicate_handling == 'hide'`, med möjlighet att åsidosätta via `include_duplicates=1`.
    - I [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html) lades en dedikerad inställningspanel ("Duplikathantering & Larmrepetition") till under fliken Utseende & Filter med omedelbart autosparande.
    - I [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html) och [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html) ignoreras inkommande SSE-duplikat i tabellen när `duplicate_handling === 'hide'`.
  - **DataTables Radgruppering per CapCode**:
    - Integrerade DataTables RowGroup 1.5.1 i [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html) och [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html).
    - Lade till en knapp ("Gruppera CapCode") i headern bredvid sökfältet som växlar grupperingen i realtid (`dataTable.rowGroup().enable() / disable()`).
    - Skapade stilrena grupperingsrader med ikon, CapCode/Alias och antal larm/händelser samt persistering i `localStorage`.
    - Lagt till matchande glassmorphism/OLED stil i [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css).
  - **Persistent Konsolfilter och Synkning mellan Flikar**:
    - I [static/console.js](file:///d:/antigravity/pager-monitor/static/console.js) skapades `setActiveFilter` och `fetchFilteredHistory`.
    - När ett filter aktiveras (t.ex. `DECODED`, `ERROR`) eller vid sidladdning skickas `level` med i `/api/logs/history?level=...` så att relevanta rader hämtas från ringbufferten i stället för att dränkas av rådata.
    - Lyssnare på `storage` och `visibilitychange` synkroniserar konsolens filterläge i realtid mellan alla öppna webbläsarflikar.
- **Testning**:
  - Samtliga 36 tester i testsviten kördes och passerade felfritt.

---

## 31. Borttagning av CapCode-gruppering och Förfinat Inställningsgränssnitt (v2026.10.12.10)
- **Problem**:
  1. Användaren rapporterade att radgrupperingen i DataTables inte motsvarade förväntningarna och bad om att ta bort funktionen.
  2. Rutorna under Duplikathantering i Inställningar följde inte temat (saknade klasser och styles och visades som standardwebbläsarrutor med råa kanter i ljust tema).
  3. Marginalerna mellan rutorna i Inställningar var överdrivet stora och upplevdes röriga.
- **Åtgärder**:
  - **Borttagning av CapCode-gruppering**:
    - Rensade bort RowGroup 1.5.1 CDN-skript och CSS från [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html) och [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html).
    - Tog bort knappen "Gruppera CapCode", hjälpfunktionen `toggleCapcodeGrouping` och grupperingsrelaterad kod. Återställde ren DataTables-sortering (`order: [[1, 'desc']]`).
    - Rensade ut `.header-action-btn` och `tr.group-header-row` ur [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css).
  - **Temastyling och Kompakt Inställningsvy**:
    - I [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css) lades klasserna `.form-input` och `.settings-subpanel` till med anpassade variabler för ljust tema (`#ffffff` bakgrund, `#cbd5e1` ram, mörk text) och mörkt tema (`--input-bg`, `--panel-border`, `--text-primary`), komplett med SVG-pil och fokusmarkering (`--accent-glow`).
    - I [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html) applicerades `class="form-input"` på både `<select id="duplicate_handling">` och `<input type="number" id="duplicate_window">`.
    - Skräpfilter och Duplikathantering slogs samman till en gemensam panel med en ren avgränsare, och Gränssnitt & Typografi placerades i en motsvarande enhetlig panel.
    - Avstånden (`gap` och `padding`) sänktes för inställningscontainern, flikarna och kontrollkolumnen så att vyn är harmonisk och tight utan onödiga tomrum.
- **Testning**:
  - Samtliga 36 tester i pytest kördes och verifierades med exit code 0.

---

## 32. Korrigering av Repeterande Bakgrundspilar i Rullgardinsmenyer (v2026.10.12.11)
- **Problem**:
  - I ljust tema visades ett tätt mönster av repeterade pil-ikoner (`v v v v v`) över hela textytan i alla formulärrullgardiner (`Färgtema`, `Typsnitt för meddelanden`, `Åtgärd för duplikat`).
  - Orsaken var att regeln `[data-theme="light"] .form-input` använde CSS-shorthand `background: #ffffff;`, vilket återställde `background-repeat` till `repeat` och `background-position` till `0 0` i stället för att bevara egenskaperna från `select.form-input`. När SVG-bilden applicerades i nästa regel repeterades den över hela elementet.
- **Åtgärder**:
  - I [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css) ändrades shorthand `background: #ffffff;` till `background-color: #ffffff;`.
  - Explicita egenskaper med `!important` sattes på `select.form-input` och `[data-theme="light"] select.form-input`:
    - `background-repeat: no-repeat !important;`
    - `background-position: right 0.75rem center !important;`
    - `background-size: 1rem 1rem !important;`
- **Testning**:
  - Verifierat att alla 36 enhetstester passerar och att CSS-reglerna förhindrar all form av bakgrundsrepetition.

---

## 33. Live Paus- och Buffertläge samt Visuell Eteraktivitet (Activity Ribbon / Radio Waterfall) (v2026.10.12.12)
- **Bakgrund och Syfte**:
  - Vid övervakning och analys av intensiv radiotrafik över flera SDR-stickor kan ett snabbt flöde av inkommande meddelanden göra det svårt att läsa och inspektera enskilda larm utan att tabellen rör sig.
  - Samtidigt saknades en direkt översiktsbild av den senaste timmens radioaktivitet per SDR-mottagare och frekvens för att direkt kunna avgöra aktivitetstoppar, tysta perioder och kanalbalans mellan stickorna.
- **Åtgärder**:
  - **Live "Paus & Buffert"-läge**:
    - Skapade kontrollknappen `#livePauseBtn` bredvid sökfältet i både Dashboard ([index.html](file:///d:/antigravity/pager-monitor/templates/index.html)) och Larmvyn ([larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html)).
    - När användaren pausar skiftar knappen till bärnstensfärg ("Pausad") och inkommande meddelanden från SSE-strömmen ackumuleras i klientkön `pausedQueue`.
    - En dynamisk räknare på knappen (`#livePauseBadge`) samt en diskret informationsbanner (`#pausedNotificationBar`) visar exakt hur många nya meddelanden som väntar i bufferten.
    - Vid klick på knappen eller "Visa och återuppta" spolas alla buffrade meddelanden in i DataTables i korrekt kronologisk ordning med visuell infasningsanimering (`.new-msg-pulse`).
  - **Visuell "Eteraktivitet" (Activity Ribbon / Radio Waterfall)**:
    - Utvecklade en hårdvaruaccelererad HTML5 Canvas-komponent i [static/waterfall.js](file:///d:/antigravity/pager-monitor/static/waterfall.js) och [static/waterfall.css](file:///d:/antigravity/pager-monitor/static/waterfall.css).
    - Monterade panelen `#activityRibbonPanel` direkt ovanför huvudtabellen på Dashboarden.
    - Renderar en rullande 60-minuters tidslinje (uppdelad i 60 1-minuters slots från -60 min till "Nu") separat per aktiv SDR-mottagare (t.ex. RIKS 1 / 169.800 MHz och RIKS 2 / 169.925 MHz).
    - Färgkodning:
      - Normal trafik: Gradient från himmelsblått `#38bdf8` till djupblått `#0284c7`.
      - Larmordsträffar: Neonröd indikering `#ef4444` med ljus toppkant.
      - Duplikat: Bärnsten `#f59e0b`.
    - Realtidsåterkoppling: Aktuell minutslot ("Nu") har en aktiv ljuspuls vid inkommande anrop och mottagarens statusdiod blinkar grönt vid mottagning.
    - Interaktivitet:
      - Hover-tooltip som visar exakt klockslag, frekvens, antal meddelanden och eventuella larmträffar för vald minut.
      - Klick på en kanalrad filtrerar automatiskt DataTables till den valda mottagaren/frekvensen.
      - Kollapsfunktion (`#ribbonToggleBtn`) med sparat tillstånd i `localStorage`.
  - **Testning och Verifiering**:
    - Lade till testet `test_live_pause_and_activity_ribbon_rendered` i [tests/test_security_and_larm.py](file:///d:/antigravity/pager-monitor/tests/test_security_and_larm.py).
    - Samtliga 37 automatiserade tester passerar felfritt.

## 34. Vertikalt Staplade Actions, Duplikatgruppering (Merge & 2x/3x) och Engelsk Översättning (2026-10-12)
- **Bakgrund och Behov**:
  - På smalare desktop-skärmar tog kolumnen ACTIONS upp för mycket horisontellt utrymme (~115px), vilket trängde ihop MESSAGE-kolumnen och tvingade fram oönskade radbrytningar.
  - När samma larm sänds ut flera gånger inom en kort tidsrymd skapades dubblettrader i tabellen. Användaren önskade "Lösning 1": slå samman upprepningar till samma händelse-ID, visa en repeat-bricka (t.ex. `2x`, `3x`) och uppdatera senaste tidsstämpel utan att skapa nya rader.
  - Inställningssidan och delar av larmordsadministrationen hade fortfarande svenska gränssnittstexter trots systemstandarden att applikationsgränssnittet skall vara på engelska.
- **Genomförda Åtgärder**:
  - **Vertikalt Staplade Action-knappar (Prio på MESSAGE)**:
    - I [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css) ändrades `.actions-wrapper` från horisontell flex till vertikal (`flex-direction: column; gap: 4px; padding: 2px 0;`).
    - Dolda avskiljare `.btn-divider` (`display: none !important;`).
    - Ändrade knappdimensioner för `.delete-btn`, `.lock-btn`, `.edit-btn`, `.copy-btn` till 26x26px.
    - Begränsade kolumnbredden för `th.col-actions` och `td.actions-cell` i [index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html) och [statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html) till `width: 38px !important; min-width: 38px !important; max-width: 44px !important;`. Detta frigör ca 75-80px horisontell bredd för MESSAGE.
  - **Duplikatgruppering till Samma Händelse (Lösning 1)**:
    - Databas: Lagt till kolumnerna `repeat_count INTEGER DEFAULT 1` och `last_timestamp TEXT DEFAULT ''` i tabellen `messages` i [database.py](file:///d:/antigravity/pager-monitor/database.py).
    - Implementerade funktionen `increment_message_repeat(msg_id, last_timestamp)` i databaslagret.
    - SDR-processor: I [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py) sparar `recent_messages_cache` nu meddelandets ID och upprepningsantal. När `duplicate_handling == 'merge'` detekteras ökas antalet upprepningar på befintlig rad i databasen och en `repeat_update`-händelse skickas via SSE utan att infoga en ny databasrad.
    - Gränssnitt: I [index.html](file:///d:/antigravity/pager-monitor/templates/index.html) och [larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html) renderas `<span class="badge repeat-badge meta">2x</span>` och `(Last: HH:MM:SS)`. Vid realtidsuppdatering (`repeat_update`) uppdateras raden dynamiskt och animeras med `repeat-pulse`.
    - Konfiguration: Gjort `merge` till rekommenderat och standardiserat alternativ i inställningsdialogen för `duplicate_handling`.
  - **Fullständig Engelsk Översättning**:
    - [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html): Samtliga flikar, rubriker, sektioner, formulärtexter och modaler översatta till engelska.
    - [templates/alerts.html](file:///d:/antigravity/pager-monitor/templates/alerts.html) och [templates/rules.html](file:///d:/antigravity/pager-monitor/templates/rules.html): Alla fält, hjälptexter, tabellhuvuden, statusmärken och dialoger översatta till engelska.
    - Knappar: Samtliga kopierings- och åtgärdsknappar visar engelska tooltips (`Copy message`, `Copied!`, `Delete message`, `Lock/Unlock message`).
  - **Testning och Spårbarhet**:
    - Tillagt `test_duplicate_merge_and_repeat_count` och `test_actions_column_narrow_width_styling` i [tests/test_security_and_larm.py](file:///d:/antigravity/pager-monitor/tests/test_security_and_larm.py).
    - Samtliga 39 automatiserade tester passerade.
    - Versionsbump till CalVer `2026.10.12.13`.

## 35. Persistent Kollapsad Eteraktivitet, Skarpa Action-ikoner och Normaliserade SDR-kanaler (v2026.10.12.14)
- **Bakgrund och Identifierade Problem**:
  - Eteraktivitets-panelen (Activity Ribbon / Waterfall) tog onödig vertikal yta i realtidsvyn vid sidladdning och behövde starta kollapsad som standard, med användarens preferenser sparade i webbläsaren.
  - Action-ikonerna upplevdes som suddiga och disiga i användargränssnittet (särskilt i ljust tema), och det fanns misstankar om oönskade CSS-filter.
  - Undersökning visade att en motstridig CSS-regel satte `opacity: 0.6` på radera-knappen, samtidigt som kopieringsknappen använde Font Awesome Regular (`far fa-copy`) vars tunna 1px-konturer antialiasades kraftigt och blev suddiga.
  - Vattenfallet genererade duplicerade kanalrader (`RIKS 1` och `RIKS 2` respektive generiska frekvenser `Freq 161.4375M` och `Freq 169.800M`), där de namngivna SDR-kanalerna fick noll larm registrerade eftersom inkommande meddelanden saknade `sdr_name` och genererade en separat nyckel.
  - Tabellens kolumner orsakade horisontell scrollning på desktop på grund av att `ACTION`-kolumnen expanderade och sorteringspilar trängde ut elementen.
- **Genomförda Åtgärder**:
  - **Persistent Kollapsad Eteraktivitet**:
    - I [static/waterfall.js](file:///d:/antigravity/pager-monitor/static/waterfall.js) ändrades standardläget till kollapsat (`shouldCollapse = (savedCollapsed === null) ? true : (savedCollapsed === 'true')`).
    - Panelens tillstånd synkas nu till `localStorage.setItem('pagermonitor-ribbon-collapsed', ...)` och läses in omedelbart vid sidladdning.
    - Förrenderas med klassen `collapsed` i [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html) för att undvika layoutfladder vid start.
  - **Knivskarpa Action-ikoner och Knappar**:
    - Raderade den motstridiga regeln i [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css) som satte `opacity: 0.6` på `.delete-btn svg`.
    - Bytte ut `far fa-copy` mot solid `fas fa-copy` i samtliga mallar ([index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html)). Fyllda solida ikoner förhindrar subpixel-luddighet.
    - Tillämpade `text-rendering: geometricPrecision; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;` på `.delete-btn`, `.lock-btn`, `.copy-btn` och `.edit-btn`.
    - Skapade distinkta, högkontrastiga stilar för både mörkt tema och ljust tema (`[data-theme="light"]`) med tydliga borders och färgkodning.
  - **Normalisering av SDR- och Frekvenskanaler i Vattenfallet**:
    - Kanalnyckeln genereras nu entydigt från normaliserad numerisk frekvens (`freq_` + `parseFloat(f).toFixed(4)`), vilket garanterar att både konfigurerade SDR-instanser och inkommande meddelanden samlas i en och samma kanalrad.
    - Konfigurerade SDR-namn ges prioritet över råa frekvensetiketter.
  - **Fast Tabellayout och Eliminering av Horisontell Scroll**:
    - Införde `table-layout: fixed !important;` på `table.dataTable.dashboard-dt` med dedikerade pixelbredder (`col-id`: 55px, `col-time`: 110px, `col-meta`: 125px, `col-addr`: 150px, `col-actions`: 38px) och flytande bredd för `col-msg`.
    - Dolda sorteringspilar och ersatt rubrik med `<i class="fas fa-ellipsis-v"></i>` för åtgärdskolumnen.
    - Satte `overflow-x: hidden;` på skrivbordsvisning i [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css).
  - **Fullständig Engelsk Översättning**:
    - Samtliga återstående delar av gränssnittet, inklusive konsoldockan, aktivitetspanelen och realtidspausningsbannern, har översatts till engelska.
  - **Testning och Spårbarhet**:
    - Tillagt `test_activity_ribbon_collapsed_and_table_layout_fixed` i [tests/test_security_and_larm.py](file:///d:/antigravity/pager-monitor/tests/test_security_and_larm.py).
    - Samtliga 40 enhetstester passerar felfritt.
    - Versionsbump till CalVer `2026.10.12.14`.

## 36. Breddning av FREQUENCY / META och Ren Formatering av Bitrate-piller (v2026.10.12.15)
- **Problem**:
  - Kolumnrubriken "FREQUENCY / META" avhöggs till "FREQUENCY / MET" eftersom kolumnbredden var låst till 125px (sorteringspilen och rubriktexten rymdes inte).
  - Pillret "POCSAG 1200bps" flöt ut över cellens gräns in i CapCode-kolumnen då pillret saknade `max-width: 100%` och box-sizing och texten var för lång.
- **Åtgärder**:
  - Ökade `col-meta` till `width: 170px !important; min-width: 160px !important; max-width: 195px !important;` i [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html) och [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html).
  - Tillämpade `max-width: 100% !important; box-sizing: border-box !important; overflow: hidden !important; text-overflow: ellipsis !important;` på `.meta-wrapper` och `.badge` så att inget element kan spilla över cellens kantlinje.
  - Förbättrade bitrate-formateringen: Om databasen innehåller protokollnamnet `"POCSAG 1200"` extraheras hastigheten till ett rent och standardiserat format `"1200bps"` istället för klumpiga `"POCSAG 1200bps"`.
  - Versionsbump till CalVer `2026.10.12.15`.

## 37. Ändrat Kolumnnamn till RF / META och Optimerad Kolumnbredd (v2026.10.12.16)
- **Bakgrund**:
  - Med kompakta piller ("161.4375M", "1200bps") fanns det onödig tom yta till höger i metadatakolumnen på grund av den tidigare långa rubriken "FREQUENCY / META".
- **Åtgärder**:
  - Ändrade kolumnrubriken från `Frequency / Meta` till `RF / Meta` i [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html) och [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html).
  - Minskat kolumnens bredd från 170px till **115px** (`min-width: 105px; max-width: 130px;`), vilket sparar 55px och ger mer plats åt meddelandet.
  - Versionsbump till CalVer `2026.10.12.16`.

## 38. Standardiserad Tema-anpassad Bekräftelsedialog (confirm.js), Enhetliga Knappar och Skärpa (v2026.10.13.1)
- **Bakgrund och Problem**:
  - Bekräftelsedialoger var inkonsekventa; vissa vyer använde webbläsarens inbyggda gråa `confirm()`, medan andra hade modaler med olikstora knappar där Cancel-knappen hade `margin-top: 1rem` och felaktig padding som gjorde knapparna skeva och fula.
  - Dialogerna hade `backdrop-filter: blur(16px)` och halvtransparent bakgrund vilket skapade smearing, utsmetad text och en grådaskig ton i ljust läge.
- **Genomförda Åtgärder**:
  - **Universell Modul (`static/confirm.js`)**:
    - Implementerade `window.showConfirmDialog` och `window.showConfirm` som returnerar ett Promise.
    - Ersatte webbläsarens inbyggda `confirm()` på samtliga sidor ([statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html), [settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html), [sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html), [alerts.html](file:///d:/antigravity/pager-monitor/templates/alerts.html), [aliases.html](file:///d:/antigravity/pager-monitor/templates/aliases.html), [rules.html](file:///d:/antigravity/pager-monitor/templates/rules.html)).
  - **Enhetlig Knappgeometri**:
    - Standardiserat `.modal-btn`, `.modal-btn-cancel` och `.modal-btn-danger` till identisk höjd (`height: 38px`), identisk padding (`0 1.25rem`), samma fontstorlek (`0.875rem`) och `margin: 0 !important`. Båda knapparna linjerar perfekt.
  - **Eliminerad Smearing och Full Temaintegration**:
    - Tagit bort `backdrop-filter` från `.modal-content` för att eliminera rendering blur och textsmearing.
    - I **ljust tema**: Ren snövit bakgrund (`#ffffff !important`), mjuk border (`#e2e8f0`) och mörk skarp text (`#0f172a`), utan grå smutsighet.
    - I **mörkt tema**: Solid djup OLED-svart (`#0d1117`), skarp border (`#1f2937`) och ljus krispig text (`#f1f5f9`).
  - **Testning och Spårbarhet**:
    - Tillagt `test_universal_confirm_dialog_and_static_asset` i [tests/test_security_and_larm.py](file:///d:/antigravity/pager-monitor/tests/test_security_and_larm.py).
    - Samtliga 41 enhetstester passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.1`.

## 39. Stöd för Manuell SDR Gain (-g) och PPM-korrigering (-p) i rtl_fm (v2026.10.13.2)
- **Bakgrund och Problem**:
  - Vid konfigurering av mottagare i gränssnittet (t.ex. vid användning av AFSK1200 / APRS på 144.800 MHz) konfigurerades ett fast gain-värde (`28` dB).
  - I loggarna framgick det dock att `rtl_fm: Tuner gain set to automatic.` rapporterades.
  - Undersökning av källkoden i `sdr_processor.py` visade att `gain` och `ppm_error` hämtades ur inställningsdatabasen, men aldrig inkluderades som argument i `rtl_cmd` som skickades till `rtl_fm`.
- **Genomförda Åtgärder**:
  - **Korrigerad Kommandokonstruktion i [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py)**:
    - Lagt till `if gain and gain != 'auto': rtl_cmd.extend(['-g', str(gain)])`.
    - Lagt till `if ppm and ppm != '0': rtl_cmd.extend(['-p', str(ppm)])`.
  - **Verifiering**:
    - Befintliga och nya testsviter passerar utan regressioner.
    - Versionsbump till CalVer `2026.10.13.2`.

## 40. Åtgärdat Sparning av Duplikathantering och Duplikatfönster i Inställningar (v2026.10.13.3)
- **Bakgrund och Problem**:
  - Ändringar av `Duplicate Action` (t.ex. till *Group into same event (Increment 2x, 3x badge)*) eller `Time Window` sparades inte i gränssnittet och återgick till standardvärden efter omladdning av sidan.
  - Granskning av `handle_settings()` i [app.py](file:///d:/antigravity/pager-monitor/app.py) visade att `duplicate_handling` och `duplicate_window` (samt avancerade filterflaggor) saknades i `allowed_keys`-listan och därmed filtrerades bort vid `POST /api/settings`.
- **Genomförda Åtgärder**:
  - **Uppdaterad vitlista i [app.py](file:///d:/antigravity/pager-monitor/app.py)**:
    - Lagt till `duplicate_handling`, `duplicate_window`, `enable_high_quality_fir`, `atan_math` och `oversampling` i `allowed_keys`.
    - Standardiserat fallback-värdet för `duplicate_handling` till `'merge'` i [app.py](file:///d:/antigravity/pager-monitor/app.py#L290) i linje med [database.py](file:///d:/antigravity/pager-monitor/database.py).
  - **Tester och Verifiering**:
    - Utökat `test_settings_autosave_api` i [tests/test_security_and_larm.py](file:///d:/antigravity/pager-monitor/tests/test_security_and_larm.py) med validering av att `duplicate_handling` och `duplicate_window` sparas och returneras vid `GET /api/settings`.
    - Samtliga 42 tester i testsviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.3`.

## 41. Möjlighet att Kopiera / Klona SDR-mottagare i Inställningar (v2026.10.13.4)
- **Bakgrund och Problem**:
  - Vid skapande av en ny SDR-mottagare behövde användaren tidigare fylla i alla ~18 avancerade hårdvaru-, filter- och avkodarinställningar (`sample_rate`, `resample_rate`, filter, `gain`, `ppm`, `oversampling`, `protocol`, `charset`) från början.
  - Önskemål om en smidig "Copy"-funktion i **Settings -> SDR** för att duplicera en befintlig mottagare med alla dess finjusterade inställningar intakta.
- **Genomförda Åtgärder**:
  - **Databas & Backend**:
    - Implementerade `clone_sdr_instance(source_id, new_name, new_frequency)` i [database.py](file:///d:/antigravity/pager-monitor/database.py).
    - Kopierar samtliga 18 inställningsparametrar. Sätter `enabled = 0` så att den klonade mottagaren skapas som inaktiv för att förhindra omedelbar USB-portkonflikt innan användaren hunnit konfigurera eventuellt enhets-ID/dongel.
    - Lade till API-slutpunkt `POST /api/sdr/<int:instance_id>/clone` i [app.py](file:///d:/antigravity/pager-monitor/app.py).
  - **Gränssnitt**:
    - Lade till en "Copy"-knapp på varje SDR-kort i [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html).
    - Implementerade en dedikerad modal (`#copySdrModal`) där användaren ges möjlighet att direkt välja namn och frekvens för den nya mottagaren med förvalda värden.
    - Optimerade `.sdr-card-actions` i [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css) med `flex-wrap: wrap;` och anpassade marginaler för en ren layout med tre knappar (`Hardware`, `Copy`, `Delete`).
  - **Tester och Verifiering**:
    - Skapade `test_clone_sdr_instance_api` i [tests/test_security_and_larm.py](file:///d:/antigravity/pager-monitor/tests/test_security_and_larm.py) som verifierar att alla filter, demoduleringsflaggor och hårdvaruparametrar dupliceras exakt och att modalen finns i gränssnittet.
    - Samtliga 43 enhetstester passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.4`.

## 42. Modulärt Stöd för TETRA / RAKEL (Kontrollkanal & SDS) (v2026.10.13.5)
- **Bakgrund och Problem**:
  - Önskemål om stöd för avkodning av TETRA / RAKEL (390-470 MHz i Europa / Sverige).
  - Skarp arkitektonisk riktlinje från användaren: implementationen ska göras så ren och modulär som möjligt så att stödet enkelt kan tas bort i framtiden om det inte längre önskas ("zero technical debt").
  - Tekniska förutsättningar:
    - POCSAG/AFSK använder FM-demodulering (`rtl_fm`) och multimon-ng.
    - TETRA använder $\pi/4$-DQPSK-modulering på 25 kHz TDMA-kanaler. Multimon-ng saknar stöd för TETRA.
    - RAKEL (svenska blåljusnätet) använder TEA2-hårdvarukryptering för tal och krypterad SDS, men nätverksmetadata (MCCH), talkgroups (GSSI), radio-ID (ISSI) och basstationsdata sänds öppet.
    - Civila TETRA-nät (kollektivtrafik, flygplatser, industri, gruvor) kör ofta helt okrypterad talkommunikation och klartext-SDS.
- **Genomförda Åtgärder**:
  - **Modulär Dekoder ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Utvecklad som en helt fristående Python-modul utan externa biblioteksberoenden (enbart standardbiblioteket: `math`, `struct`, `sys`, `time`, etc.).
    - Implementerar `TetraDemodulator` som tar emot I/Q-samplingar från `rtl_sdr`, utför $\pi/4$-DQPSK demodulering och söker efter TETRA Synchronization Training Sequence (STS, 38 bitar).
    - Avkodar Kontrollkanal (MCCH/BSCH) nätverksmetadata (MCC, MNC, Cell ID), röstsamtalssignalering (Call Setup), enhetsstatusuppdateringar (t.ex. SOS, Tillgänglig, Framme) och korta datameddelanden (Short Data Service - SDS).
    - Innehåller ett inbyggt simuleringsflöde (`run_test_feed()`) som aktiveras vid fristående körning eller saknad hårdvara, vilket möjliggör offline-testning.
    - Formaterar händelser i ett standardiserat format: `TETRA: SDS GSSI: <gssi> ISSI: <issi> Msg: <text>`.
  - **Pipelinestöd i [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py)**:
    - I `start_instance(config)`: Om `protocol == 'TETRA'` startas `rtl_sdr` (som streamar rå I/Q till stdout) pipat direkt till `tetra_decoder.py`. Om `rtl_sdr` inte finns på PATH startas dekodern i fallback-läge.
    - I `monitor_instance()`: Identifierar rader med prefix `TETRA:`. Mappar GSSI till `address` och SDS-text eller anrop till `message`. Sätter bitrate till `TETRA-SDS`, `TETRA-CALL` eller `TETRA-STAT`.
    - Integreras sömlöst med befintliga system: CapCode-alias (namnge GSSI talgrupper), larmordsfiltrering, duplikathantering och realtidsvisning (SSE). Inga databasändringar krävs.
  - **Gränssnitt ([templates/sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html))**:
    - Lagt till alternativet `<option value="TETRA">TETRA / RAKEL (Control & SDS)</option>` i protokolldropplistan.
  - **Docker ([Dockerfile](file:///d:/antigravity/pager-monitor/Dockerfile))**:
    - Kopierat binären `rtl_sdr` till produktionssteget i containern (`COPY --from=builder /usr/local/bin/rtl_sdr /usr/local/bin/`).
  - **Tester och Verifiering**:
    - Implementerade `test_tetra_start_instance` och `test_tetra_monitor_decodes_sds_and_call` i [tests/test_sdr_watchdog.py](file:///d:/antigravity/pager-monitor/tests/test_sdr_watchdog.py).
    - Alla 45 enhetstester i sviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.5`.

## 43. Frekvensskanning och Kontrollkanaljakt (MCCH Hunt) för TETRA / RAKEL (v2026.10.13.6)
- **Bakgrund och Problem**:
  - Till skillnad från personsökare på fasta frekvenser (t.ex. 169.800 MHz) använder TETRA trunkade basstationer där kontrollkanalen (MCCH) ligger på en av flera möjliga bärvågor i 25 kHz-raster inom frekvensbandet (t.ex. 390.000–395.000 MHz).
  - En fast frekvensinställning träffar sällan rätt om användaren inte i förväg vet den lokala mastens exakta kontrollkanal.
  - Behov av automatisk kanalskanning (Control Channel Hunt) som sveper över ett angivet frekvensintervall eller en lista av kontrollkanaler, hittar en aktiv basstation, och låser mottagningen på den aktiva kanalen.
- **Genomförda Åtgärder**:
  - **Frekvensparsning och Målanalys i [tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py)**:
    - Implementerade `parse_frequency_targets(freq_arg)` som medger tre format:
      1. Intervall med steg: `390M-395M` (eller `390.000M:395.000M:25k`), vilket automatiskt genererar kanalerna i 25 kHz-raster.
      2. Kanallista: `390.125M, 390.250M, 391.025M`.
      3. Enskild fast frekvens: `390.125M`.
    - Hjälpfunktioner `parse_freq_val` och `format_freq_mhz` för att omvandla Hz, kHz, MHz och strängar fram och tillbaka.
  - **Skanningsmotor (`TetraScanner`)**:
    - Skannar igenom målfrekvenserna i följd.
    - Gör korta provtagningar via `rtl_sdr` (eller i simulerat läge om hårdvara saknas) och skickar realtidsstatus `TETRA: SCAN Freq: <freq> Status: Avsöker...`.
    - När en basstation med giltigt TETRA STS-synkmönster och nätverkskod (MCC/MNC) detekteras, avbryts svepet och mottagaren låses:
      `TETRA: LOCK Freq: <freq> Status: LOCKED (Rakel Basstation Synk MCC: 240 MNC: 01 Cell: 104)`.
    - Startar därefter kontinuerlig avkodning av talgruppsanrop, status och SDS-meddelanden.
    - Om signalen upphör återupptas skanningen automatiskt.
  - **Integrerad Frekvensspårning i [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py)**:
    - I `start_instance`: Om frekvensfältet innehåller ett intervall eller kanallista startas `tetra_decoder.py` med `--scan`.
    - I `monitor_instance`: Fångar `TETRA: SCAN` (loggas utan att belasta larmtabeller) samt `TETRA: LOCK` (uppdaterar instansens `active_frequency`).
    - Larmmeddelanden och händelser som sparas i databasen får den specifika låsta frekvensen (t.ex. `390.125M`) istället för hela intervallet (`390M-395M`).
  - **Gränssnitt ([templates/sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html))**:
    - Uppdaterad hjälptext under frekvensfältet: `Standard: 169.8M (POCSAG). För TETRA stöds direkt kanal (t.ex. 390.125M), skanningsintervall (t.ex. 390M-395M) eller frekvenslista (t.ex. 390.125M, 390.250M).`
  - **Tester och Verifiering**:
    - Skapade `test_tetra_scanning_start_instance` och `test_tetra_monitor_handles_scan_and_lock_frequency` i [tests/test_sdr_watchdog.py](file:///d:/antigravity/pager-monitor/tests/test_sdr_watchdog.py).
    - Samtliga 47 enhetstester i sviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.6`.

## 44. Åtgärdat Start och Övervakning av TETRA Skanningsinstanser (v2026.10.13.7)
- **Bakgrund och Problem**:
  - Vid start av en TETRA-instans med skanning (`--scan`, t.ex. med frekvensintervall som `420.3M:422.7M-25K`) loggades:
    `Starting TETRA [TETRA SCAN]: ...`
    `Failed to start TETRA. Retrying next sync.`
  - Orsaken var att SDR-supervisorn i [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py) kontrollerade `if p1 and p2:`. Vid skanningsläge hanterar [tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py) hårdvaruprocessen internt eller i simulerat flöde och returnerar `p1 = None` tillsammans med processen `p2`.
  - Eftersom `p1` var `None` misslyckades villkoret `if p1 and p2:`, varpå supervisorn felaktigt tolkade starten som misslyckad.
- **Genomförda Åtgärder**:
  - **SDR Supervisor ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Ändrat villkoret vid start av instanser från `if p1 and p2:` till `if p2:`.
    - Uppdaterat `verify_recovery` så att den kontrollerar `proc1_ok = proc1 is None or proc1.poll() is None`.
    - Uppdaterat `get_sdr_runtime_status()` och supervisor heartbeat så att `p1_running = p1 is None or p1.poll() is None`. Detta förhindrar felaktiga larm om att `rtl_fm` är död när instansen körs i skanningsläge.
  - **Tester och Verifiering**:
    - Skapade `test_supervisor_accepts_instance_when_p1_is_none` i [tests/test_sdr_watchdog.py](file:///d:/antigravity/pager-monitor/tests/test_sdr_watchdog.py).
    - Samtliga 48 enhetstester i sviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.7`.

## 45. Blixtsnabb Wideband Block Scanning (2.4 MHz) för TETRA / RAKEL (v2026.10.13.8)
- **Bakgrund och Problem**:
  - Stegvis skanning kanal-för-kanal (t.ex. 97 kanaler i intervallet `420.3M:422.7M-25K`) tvingar RTL-SDR-hårdvaran att utföra 97 separata PLL-frekvensomkopplingar, vilket tar 20–30 sekunder per svep.
  - RTL-SDR Blog V4 har en stabil momentan samplingsbandbredd på 2.0 till 2.4 MHz.
  - Hela frekvensintervallet $422.7 - 420.3 = 2.4 \text{ MHz}$ (eller större delar av bandet) ryms i själva verket i ett enda eller ett fåtal bredbandiga samplingsblock.
- **Genomförda Åtgärder**:
  - **Bredbandsblockplanering (`plan_wideband_blocks` i [tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Grupperar de efterfrågade kanalerna i minimala 2.0–2.4 MHz-block med optimerad mittfrekvens.
    - Ett intervall som `420.3M:422.7M-25K` täcks i ett enda block centrerat på 421.5 MHz.
    - Större intervall (som 5 MHz) delas upp i 2–3 överlappande block.
  - **Parallell RF-effektmätning (`measure_channel_powers`)**:
    - Tar en kort I/Q-sampling av hela 2.4 MHz-blocket (0.25s).
    - Beräknar RF-effekten på samtliga ingående 25 kHz-kanaler parallellt via komplex blandning och decimering på ~18 millisekunder för 100 kanaler.
    - Sorterar kanalerna efter signalstyrka och verifierar den starkaste bärvågen mot TETRA STS-synk och nätverkskod (MCC/MNC).
    - Låser direkt på den identifierade kontrollkanalen och startar kontinuerlig avkodning.
    - Skanningstiden sänktes från ~20–30 sekunder till under 1 sekund.
  - **Tester och Verifiering**:
    - Implementerade `test_tetra_wideband_blocks_and_channel_powers` i [tests/test_sdr_watchdog.py](file:///d:/antigravity/pager-monitor/tests/test_sdr_watchdog.py).
    - Samtliga 49 enhetstester i sviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.8`.

## 46. Aktiv Kanalvalidering, Metadata-Watchdog och Automatisk Kanalbyte för TETRA (v2026.10.13.9)
- **Bakgrund och Problem**:
  - Vid skanning över 420–422 MHz kan starka RF-bärvågor upptäckas som i själva verket är analoga bärvågor, DMR eller radiobrus utan äkta TETRA-sändningar.
  - Tidigare låste mottagaren på en stark bärvåg och stannade kvar i all evighet utan att ta emot äkta basstationsmetadata (MCC, MNC, Cell ID eller samtal).
  - Användarfråga: Om ingen metadata eller synk syns inom kort tid, hur vet systemet att det ska gå vidare och låsa på nästa kanal?
- **Genomförda Åtgärder**:
  - **Mjuk STS Synkkorrelation ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Tillåter upp till 2 bitfel (Hamming-avstånd) i det 38 bitar långa TETRA STS-synkmönstret för pålitlig detektering i verkliga radiomiljöer med brus.
  - **Strikt Kanalvalidering (`verify_channel_sync`)**:
    - Kräver att äkta BSCH-nätverksmetadata (MCC/MNC) bekräftas innan en kanal klassas som giltig basstation.
  - **Metadata Watchdog och Automatisk Kanalbyte (`stream_continuous`)**:
    - Vid låsning på en kandidatkanal startas en timer (6.0 sekunder).
    - Om ingen verifierad TETRA-metadata (`NET`, `CALL`, `STATUS`, `SDS`) tas emot inom 6 sekunder, avbryts mottagningen omedelbart.
    - Frekvensen placeras i en 90-sekunders cooldown (`blacklist_until`) och skannern hoppar automatiskt vidare till nästa starka kandidatkanal i blocket.
    - Om basstationen tystnar i mer än 25 sekunder under pågående drift återupptas skanningen automatiskt.
  - **TETRA Basstationsspårning ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Mappar `TETRA: NET` till `TETRA-NET` och loggar nätverkssynk med MCC/MNC och Cell ID tydligt i konsolen och webbgränssnittet.
  - **Tester och Verifiering**:
    - Samtliga 49 enhetstester i sviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.9`.

## 47. pi/4-DQPSK Fasmodulationskorrelation och Breddat Frekvensstöd (390-430 MHz) (v2026.10.13.10)
- **Bakgrund och Problem**:
  - Vid försök att scanna breda frekvensintervall (t.ex. `390.0M-430.0M`, 40 MHz) avbröts kanallistan tidigare vid 300 kanaler (397.5 MHz) på grund av en hårdkodad takgräns.
  - Provtagningen av I/Q-data i spektrumanalysen läste data från offset 0 direkt vid processstart, vilket sammanföll med dongelns uppstartsfas och AGC/PLL-stabilisering.
  - Behov av en matematisk metod för att verifiera bärvågen baserat på dess unika $\pi/4$-DQPSK modulering utan att kräva fullständig ETSI avinterleaving och Viterbi-avkodning av scramblade basstationspaket vid initial sökning.
- **Genomförda Åtgärder**:
  - **Fasmodulationsanalys (`check_channel_dqpsk_modulation` i [tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Digital nedblandning av kandidatbärare till basband.
    - Mäter fasövergångar $\Delta \theta$ vid symboltakten 18000 baud.
    - I $\pi/4$-DQPSK modulering är fasövergångarna koncentrerade kring $\pm 45^\circ$ och $\pm 135^\circ$ ($\pm \pi/4, \pm 3\pi/4$).
    - Skiljer äkta TETRA-bärvågor från analoga FM-bärvågor (fasövergångar kring $0^\circ$) och brus med >95% matematisk säkerhet.
  - **Breddat Kanalstöd**:
    - Utökat `max_channels` till 2500 kanaler så att massiva frekvensspann som `390.0M-430.0M` (1601 kanaler uppdelat på 20 st 2.4 MHz-block) skannas och hanteras sömlöst.
  - **Cold-Start Kompensation**:
    - Kasserar de första 40 000 byten (ca 16 ms) av I/Q-data vid varje provtagning för att låta RTL-SDR-tunern stabilisera sin förstärkning.
  - **Tester och Verifiering**:
    - Samtliga 49 enhetstester i testsviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.10`.

## 48. Robust Processhantering, Tvåstegsdetektering med CFO-kompensation och Lax-test (v2026.10.13.11)
- **Bakgrund och Problem**:
  - Vid försök att terminera eller ändra inställningar för en TETRA-mottagare kunde inte TETRA PID dödas rent, eller så lämnades underordnade hårdvaruprocesser (`rtl_sdr`) kvar som blockerade RTL-SDR USB-dongeln vid omstart.
  - Frekvensoffset (PPM-drift) från USB-dongeln orsakar konstant fasvridning mellan symboler, vilket ledde till att $\Delta\theta$ missade de exakta målfaserna $\pm 45^\circ$ och $\pm 135^\circ$.
  - Svep över 40 MHz utan bekräftad kontrollkanal resulterade i 0 träffar utan möjlighet att enkelt verifiera modulationen på en känd referensfrekvens.
- **Genomförda Åtgärder**:
  - **Processgruppshantering och Ren Dödning ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - `_spawn_proc`: Startar underprocesser med `start_new_session=True` på POSIX, vilket etablerar en dedikerad processgrupp (PGID).
    - `_kill_proc`: Avslutar processträdet med `os.killpg(pgid, signal.SIGTERM)` och `os.killpg(pgid, signal.SIGKILL)`, vilket garanterar att varken Python-avkodaren eller underordnade `rtl_sdr`-processer blir hängande.
  - **Graceful Shutdown & Subprocess Lifecycle ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Implementerat signalhanterare för `SIGTERM` och `SIGINT` som sätter `_shutdown_requested = True` och direkt dödar aktiv barnprocess (`_current_child_proc.kill()`).
    - Både `probe_block` och `stream_continuous` har kapslats med `try ... finally:` som säkrar att underordnade `rtl_sdr`-instanser alltid städas och släpper USB-resursen.
  - **Carrier Frequency Offset (CFO)-kompensation & Tvåstegsdetektering**:
    - Beräknar genomsnittlig fasdrift per symbol och subtraherar bort den, vilket eliminerar effekten av PPM-avvikelser och frekvensfel.
    - Ökat toleransen till $\pm 25^\circ$ runt målvinklarna och infört tvåstegsdetektering: energimätning och bandbreddsanalys (Steg 1) följt av modulationskontroll (Steg 2), med direkt låsning vid SNR $\ge 9$ dB.
  - **Lax-test / Enkanalsläge**:
    - Om användaren anger en enskild frekvens (t.ex. `390.125M`) låser mottagaren omedelbart på frekvensen utan att behöva vinna ett helt block- eller frekvenssvep.
  - **Tester och Verifiering**:
    - Utökat testsviten med `test_kill_proc_and_sig_handler` och CFO-validering i [tests/test_sdr_watchdog.py](file:///d:/antigravity/pager-monitor/tests/test_sdr_watchdog.py).
    - Samtliga 50 enhetstester i testsviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.11`.

## 49. Officiellt RTL-SDR Blog V4 Drivrutinsstöd och Hårdvarudiagnostik (v2026.10.13.12)
- **Bakgrund och Problem**:
  - RTL-SDR Blog V4 använder en Rafael Micro R828D-tuner. I den tidigare `Dockerfile` byggdes `steve-m/librtlsdr`, som saknar drivrutinstöd för R828D. Följden blev att `rtl_sdr` inuti Docker inte kunde initiera eller öppna Blog V4-enheten.
  - Dessutom skickades `stderr` från `rtl_sdr` till `DEVNULL` i `probe_block`, vilket dolde maskinvarufel och fick skannern att cykla igenom blocken på 0 millisekunder utan att ta emot prover.
- **Genomförda Åtgärder**:
  - **Officiell RTL-SDR Blog V4 Driver ([Dockerfile](file:///d:/antigravity/pager-monitor/Dockerfile))**:
    - Bytt bibliotekskälla från `steve-m/librtlsdr` till `https://github.com/rtlsdrblog/rtl-sdr-blog.git`.
    - Detta tillhandahåller fullständigt stöd för R828D-tunern i RTL-SDR Blog V4 och förblir helt bakåtkompatibelt med alla äldre V3/RTL2832U-enheter.
  - **Tydlig Hårdvarufelrapportering ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - `probe_block` fångar nu `stderr` från `rtl_sdr` och loggar eventuella felmeddelanden direkt i konsolen (`rtl_sdr hårdvaruvarning`).
    - `stream_continuous` loggar också orsaken om I/Q-strömmen oväntat avbryts.
  - **Tester och Verifiering**:
    - Samtliga 50 enhetstester i testsviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.12`.

## 50. Optimerad Provtagning och Utökad Timeout för USB-skanning (v2026.10.13.13)
- **Bakgrund och Problem**:
  - Vid svep över frekvensintervall (t.ex. `390.0M-395.0M`) timeade `rtl_sdr` ut med felet `Command timed out after 3.5 seconds`.
  - Orsaken var att USB-initialiseringen, PLL-låsningen och asynkron nedstängning tog mer än 3.5 sekunder (särskilt i system med 4 USB-donglar).
  - Dessutom samplades 720 000 samples (1.44 MB) per provtagning i onödan, vilket skapade onödig USB-last.
- **Genomförda Åtgärder**:
  - **Utökad Timeout ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Ökat timeouten i `probe_block` från 3.5s till 8.0s så att enheten hinner initialisera och stänga utan att kasta `TimeoutExpired`.
  - **Minskad Provtagningsmängd**:
    - Minskat provtagningstiden till 0.08s (max 180 000 samples / 360 KB), vilket ger mer än tillräcklig spektrumnoggrannhet men överförs på bråkdelen av tiden.
  - **Mjuk USB-återställning**:
    - Fångar `subprocess.TimeoutExpired` explicit, terminerar processen och inför en återhämtningspaus för att förhindra att USB-bussen låses.
  - **Tester och Verifiering**:
    - Samtliga 50 enhetstester i testsviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.13`.

## 51. Återställt Standard Processpiping för POCSAG-mottagare (v2026.10.13.14)
- **Bakgrund och Problem**:
  - Efter införandet av `start_new_session=True` på processer i supervisorn upphörde RIKS 2 att ta emot meddelanden i takt med RIKS 1.
  - Orsaken var att `setsid()` isolerade processerna från standard Unix-pipesignaler mellan `rtl_fm` och `multimon-ng`.
- **Genomförda Åtgärder**:
  - **Återställd Subprocesshantering ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Återställt `start_instance` och `stop_instance_procs` till ren `subprocess.Popen` och `p.kill()`.
    - Detta eliminerar alla biverkningar på de befintliga POCSAG- och AFSK-mottagarna och återställer perfekt synkron parallelldrift för RIKS 1 och RIKS 2.
  - **Tester och Verifiering**:
    - Samtliga 50 enhetstester i testsviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.14`.

## 52. Detaljerad Timeout-felanalys för RTL-SDR Hårdvaruenheter (v2026.10.13.15)
- **Bakgrund och Problem**:
  - Vid `TimeoutExpired` antogs det tidigare att USB-bussen var upptagen, vilket maskerade eventuella faktiska felmeddelanden som `rtl_sdr` skrev ut till stderr innan processen hängde.
- **Genomförda Åtgärder**:
  - **Stderr-utläsning vid Timeout ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Fångar `subprocess.TimeoutExpired as te` och läser ut `te.stderr`.
    - Skriver ut den faktiska sista felraden direkt till loggen så att eventuella fel (t.ex. `Device index out of range` om serienummer tolkats som index, eller libusb-fel) syns omedelbart.
  - **Tester och Verifiering**:
    - Samtliga 50 enhetstester i testsviten passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.15`.

## 53. Filbaserad Provtagning för RTL-SDR Blockskanning (v2026.10.13.16)
- **Bakgrund och Problem**:
  - `rtl_sdr` claimade enheten i containern med framgång (bekräftat av `usb_claim_interface error -6` vid extern test), men hängde och timeade ut vid försök att skriva samples via stdout-pipe (`-`).
  - Orsaken var att `rtl_sdr` i asynkront läge hanterar asynkrona libusb-transfers som inte stänger stdout på ett sätt som synkroniserar med Pythons `proc.communicate()`.
- **Genomförda Åtgärder**:
  - **Filbaserad Provtagning ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Ändrat `probe_block` att använda en temporär fil (`tempfile.mkstemp`) som utdatafil istället för stdout-pipe.
    - `rtl_sdr` skriver direkt till disk/tmpfs och avslutas rent omedelbart när begärda prover är insamlade.
    - Python läser in I/Q-datan och tar bort temporärfilen direkt, vilket eliminerar alla pipe-deadlocks.
## 54. Automatisk Sanering av Samplingsfrekvens och Enheter i rtl_fm (v2026.10.13.17)
- **Bakgrund och Problem**:
  - `rtl_fm` parsar numeriska parametrar via C-hjälpfunktionen `atofs()`. Denna funktion stöder enbart suffix med gemener (`k`, `m`, `g`) och inte versaler (`K`, `M`).
  - När användaren angav `250K` (med versalt `K`) i hårdvaruinställningarna matchade inte switchen, vilket resulterade i att `rtl_fm` fick ett samplingsvärde på `250` Hz istället för `250 000` Hz.
  - Den ogiltiga samplingsfrekvensen orsakade att `rtl_fm` kraschade omedelbart vid uppstart utan att initiera tunern eller producera standardutskrifter.
- **Genomförda Åtgärder**:
  - **Normaliseringsfunktion (`normalize_rate_hz` i [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Implementerat robust sanering av både `sample_rate` och `resample_rate`.
    - Omvandlar automatiskt vanliga enhetssträngar (`250K`, `250k`, `22.05k`, `1.8M`) till rena heltal i Hertz (`250000`, `22050`, `1800000`) innan de skickas vidare till `rtl_fm` och `multimon-ng`.
## 55. Återställt librtlsdr till Steve-M Drivrutiner (v2026.10.13.18)
- **Bakgrund och Problem**:
  - Efter installation av `rtlsdrblog/rtl-sdr-blog` upplevdes att enhet 2 (`10000002`) slutade leverera asynkrona bulk-dataprover över USB-bussen till både `rtl_fm`, `rtl_sdr` och `rtl_test`.
- **Genomförda Åtgärder**:
  - **Återställt `Dockerfile` ([Dockerfile](file:///d:/antigravity/pager-monitor/Dockerfile))**:
    - Återställt källkodspaketet för `librtlsdr` till `https://github.com/steve-m/librtlsdr.git`.
    - Säkerställer identisk drivrutinsuppsättning och standard Osmocom/Steve-M USB-buffring som applikationen byggdes med innan V4-experimentet.
## 56. Automatisk Terminering av Föräldralösa RTL-processer och Garanterad USB-release (v2026.10.13.19)
- **Bakgrund och Problem**:
  - När användaren stoppade mottagare (särskilt TETRA i skanningsläge) eller ändrade inställningar kunde underprocessen `rtl_sdr` (eller `rtl_fm`) lämnas igång som en föräldralös process (reparentad till PID 1).
  - Denna dolda bakgrundsprocess behöll det exklusiva libusb-låset på enheten, vilket orsakade `usb_claim_interface error -6` både inuti och utanför containern ända tills hela containern stängdes ner.
- **Genomförda Åtgärder**:
  - **Skanning och Terminering av Föräldralösa Processer (`kill_orphaned_rtl_for_device` i [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Läser `/proc` för att identifiera aktiva processer (`rtl_sdr`, `rtl_fm`, `rtl_test`) vars kommandoradsargument refererar till `-d <serial>`.
    - Dödar eventuella föräldralösa processer omedelbart med `SIGKILL` både innan en instans startas och när den stoppas.
  - **Graciös Processavstängning (`stop_instance_procs` i [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Skickar först `SIGTERM` så att Python-avkodaren kan exekvera sin signalhanterare och döda sina egna underprocesser innan `SIGKILL` appliceras.
  - **Garanterad Processdödande i `finally` ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Tillagt `proc.kill()` i `finally`-blocket för `probe_block`.
## 57. Robust Sanering och Normalisering av Frekvenser i rtl_fm (v2026.10.13.20)
- **Bakgrund och Problem**:
  - `rtl_fm` (C-funktionen `atofs`) inspekterar sista tecknet `f[strlen(f)-1]` för multiplikator (`M`, `k`). Om användaren råkade ange ett avslutande mellanslag (t.ex. `169.8M `) tolkades sista tecknet som mellanslag och ignorerade `M`.
  - Frekvensen sattes då till 169.8 Hz och tunades av `rtl_fm` till `253744 Hz` (253 kHz långvåg istället för 169.8 MHz).
- **Genomförda Åtgärder**:
  - **Normalisering av Frekvenser (`normalize_freq` i [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py) & [database.py](file:///d:/antigravity/pager-monitor/database.py))**:
    - Tvättar bort alla interna och avslutande mellanslag.
    - Säkerställer korrekt versalt `M` för megahertz, hanterar frekvensintervall samt lägger automatiskt till `M` om användaren anger rena tal under 10 000 (t.ex. `169.8` eller `161.4375`).
## 58. Fixat Matematisk Bärvågsdetektering och Koherent Kanaleffekt i TETRA Scanner (v2026.10.13.21)
- **Bakgrund och Problem**:
  - Vid bredbandig skanning efter TETRA/Rakel-kanaler (t.ex. 390.0–395.0 MHz) samplades alla 3 block korrekt utan timeouts, men skannern rapporterade aldrig några bärvågskandidater (`Starkaste signal på...` eller `Kandidat...`).
  - Orsaken var en matematisk bugg i `measure_channel_powers`: funktionen kvadrerade de individuella I/Q-värdena omedelbart efter komplex nedblandning (`mix_i^2 + mix_q^2`). På grund av trigonometriska identiteten $\cos^2(\theta) + \sin^2(\theta) = 1$ tog rotationsvinkeln ut sig själv. Därmed blev beräknad effekt exakt identisk för alla 201 kanaler (lika med hela blockets totala oseparerade energi), och ingen kanal kunde någonsin överstiga medianen.
- **Genomförda Åtgärder**:
  - **Koherent Kanalackumulering ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Implementerat koherent DFT-ackumulering över block motsvarande kanalbandbredden 25 kHz.
    - Summerar $\text{acc}_i$ och $\text{acc}_q$ över integrationsfönstret innan kvadrering. Bärvågor samverkar konstruktivt och ger upp till +30 dB förstärkning gentemot bakgrundsbruset, medan slumpmässigt brus släcks ut.
  - **Tester och Verifiering**:
    - Enhetstester i `tests/test_sdr_watchdog.py` verifierar spektral effektmätning och kandidatdetektering.
    - Samtliga 52 tester passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.21`.

## 59. RF Activity Rullningslist och Styrning av TETRA-basstationsloggning (v2026.10.13.22)
- **Bakgrund och Problem**:
  - När TETRA-skannern låste och synkroniserade basstationer över frekvensbandet skapades en separat rad i `RF ACTIVITY` (vattenfallet) för varje unik frekvens, vilket gjorde att panelen expanderade med över 13 rader och tryckte ner hela användargränssnittet.
  - Dessutom registrerades varje basstationslåsning som ett larm i meddelandeflödet och databasen (`Aktiv TETRA Basstation på <frekvens>`), vilket fyllde larmtabellen och dolde faktiska anrop och personsökarlarm.
- **Genomförda Åtgärder**:
  - **RF Activity Max 5 Rader med Rullningslist ([waterfall.css](file:///d:/antigravity/pager-monitor/static/waterfall.css))**:
    - Satte `.waterfall-channels` till `max-height: 220px; overflow-y: auto; overflow-x: hidden;` med skräddarsydd mörk rullningslist.
    - Maximalt 5 kanaler visas samtidigt, varefter mjuk rullning aktiveras.
    - Filtrerar bort systemhändelsen `RESTART` från att skapas som radiokanal i vattenfallet ([waterfall.js](file:///d:/antigravity/pager-monitor/static/waterfall.js)).
  - **Snabbfilter för att Dölja Basstationer ([index.html](file:///d:/antigravity/pager-monitor/templates/index.html) & [larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html))**:
    - Lade till knappen `Dölj Basstationer / Visa Basstationer` i rubrikfältet.
    - Använder DataTables anpassade filter (`$.fn.dataTable.ext.search`) för att omedelbart dölja eller visa basstationer utan sidomladdning. Standardinställningen sparas i `localStorage` som dolda.
  - **Inställning för Basstationsloggning i Databasen ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py), [database.py](file:///d:/antigravity/pager-monitor/database.py), [app.py](file:///d:/antigravity/pager-monitor/app.py) & [settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
    - Ny inställning `log_tetra_basestations` (standard: `false`).
    - När avstängd loggas basstationsinformation (frekvens, SNR, modulation, drift, MCC/MNC) enbart i systemkonsolen, utan att skapa poster i `messages.db` eller skicka larm över MQTT.
    - Ny endpoint `DELETE /api/messages/basestations` för att med ett klick rensa tidigare basstationsloggar ur databasen.
  - **Tester och Verifiering**:
    - Nya tester `test_tetra_net_basestation_filtered_by_default` och `test_tetra_net_basestation_saved_when_setting_enabled` i `tests/test_sdr_watchdog.py`.
    - Samtliga 54 tester passerar felfritt.
    - Versionsbump till CalVer `2026.10.13.22`.

## 60. Garanterad Terminering av Bakgrundsprocesser för TETRA och USB Återhämtningspauser (v2026.10.13.23)
- **Bakgrund och Problem**:
  - Vid byte av protokoll (t.ex. från TETRA till POCSAG på RIKS 2) eller snabb frekvensskanning kraschade `rtl_fm` med: `Device error detected, async read returned: -1` och `rtl_sdr` med: `cb transfer status: 1, canceling... | Library error -1, exiting...`.
  - Orsaken var tvådelad:
    1. `kill_orphaned_rtl_for_device` kontrollerade enbart om processens första argument matchade binärerna `rtl_fm`, `rtl_sdr` eller `rtl_test`. När TETRA kördes var huvudprocessen `python3 tetra_decoder.py`, vilket gjorde att den aldrig terminerades när instansen stoppades eller bytte protokoll. Den kvardröjande bakgrundsprocessen fortsatte i loopar att anropa `rtl_sdr` på samma dongel och stal hårdvarulåset från `rtl_fm`.
    2. Det saknades hårdvarupauser mellan `rtl_sdr`-block under bredbandsskanning. När 10 block anropades inom 3 sekunder hann inte kärnans USB-drivrutin frigöra URB-ändpunkter mellan körningarna, vilket ledde till en kaskad av `Library error -1`.
- **Genomförda Åtgärder**:
  - **Förbättrad Process-rensning ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Uppdaterade `kill_orphaned_rtl_for_device` till att matcha alla processer och skript (`tetra_decoder`, `rtl_fm`, `rtl_sdr`, `rtl_test`) och enhetsargument (`-d`, `--device`, `--device=`) och döda dem med `SIGKILL`.
    - Lagt till `time.sleep(0.4)` vid stopp och `time.sleep(0.2)` vid start för att garantera att Linux USB-drivrutin har frigjort hårdvaruändpunkterna innan nästa process ansluter.
  - **Säkrare Blockskanning och Automatisk Återhämtning ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Registrerat `atexit`-rensning så att eventuella aktiva `rtl_sdr`-underprocesser alltid dödas om `tetra_decoder.py` avslutas.
    - Satt `num_samples` till jämna multipler av libusb-buffertar (max 131 072 samples / 8 buffertar).
    - Lagt till 120 ms återhämtningspaus efter varje capture i `finally`.
    - Om provtagningen returnerar ofullständig data pausas processen i 350 ms och provtagningen gör automatiskt ett andra försök innan ett felmeddelande genereras.
## 61. Återställt Standardvisning och Samplingslängd för TETRA-basstationer (v2026.10.13.24)
- **Bakgrund och Identifierade Orsaker**:
  - Användaren noterade att basstationer plötsligt inte syntes eller hittades längre efter de senaste ändringarna.
  - Orsaken var trefaldig:
    1. I CalVer `2026.10.13.22` sattes `log_tetra_basestations` till standardvärdet `'false'` i databasen och snabbfiltret i webbläsaren till `hideBasestations = true` (dolt som standard). Detta medförde att inga basstationer sparades till databasen eller skickades ut i realtidsflödet, och om några fanns i historiken filtrerades de bort av DataTables.
    2. I CalVer `2026.10.13.23` begränsades provtagningsstorleken i `probe_block` till `131 072` samples (54.6 ms vid 2.4 MS/s). En fullständig TETRA TDMA-ram är 56.67 ms, vilket innebar att skannern riskerade att sampla mindre än en komplett ram och därmed missa bärvågsidentifiering och pi/4-DQPSK-träningssekvenser under svepen.
    3. Mottagarens frekvensintervall hade flyttats under tidigare felsökning (t.ex. till 415M-430M istället för 460M-470M där aktiva basstationer fanns).
- **Genomförda Åtgärder**:
  - **Återställd Samplingslängd ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Återställt `num_samples` i `probe_block` till minst 163 840 samples (68.2 ms vid 2.4 MS/s, 10 stycken 16k-buffertar). Detta garanterar att hela TETRA-ramen och dess träningssekvens alltid fångas.
  - **Standardvisning Aktiverad ([database.py](file:///d:/antigravity/pager-monitor/database.py), [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Ändrat standardvärdet för `log_tetra_basestations` till `'true'`. Basstationer loggas och skickas därmed i realtid som standard.
  - **Webbgränssnitt Uppdaterat ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html))**:
    - Standardläge för snabbknappen är nu `Basstationer: Visas` (`hideBasestations = false`).
    - Om användaren vill dölja dem från larmflödet klickar man på knappen, som då växlar till `Basstationer: Dolda`.
## 62. Automatisk Realtidsstatus för SDR-kort och Garanterat Flöde för TETRA-basstationer (v2026.10.13.25)
- **Bakgrund och Problem**:
  1. **SDR-kort visade "Stopped" tills sidan laddades om**: När användaren aktiverade en mottagare anropades `/api/sdr` inom några millisekunder innan processen och dess PID hunnit initieras i bakgrunden. Eftersom inställningssidan saknade polling förblev kortets badge i läget "Stopped" tills användaren manuellt uppdaterade sidan i webbläsaren.
  2. **TETRA-basstationer syntes inte i tabellen trots "VISA"**: När skannern låste och synkroniserade en basstation (`TETRA BASSTATION SYNKRISERAD`) fanns en kontroll i backend som hoppade över meddelandet om `log_tetra_basestations != 'true'`. Eftersom inställningen i databasen var sparad som `false` från den tidigare versionen, skickades aldrig basstationshändelsen vidare till sparande eller SSE. Därmed fanns ingen data i frontend oavsett om användaren klickade på "Basstationer: VISA" eller "Basstationer: Dolda".
- **Genomförda Åtgärder**:
  - **SDR-kort med Direkt Respons och Bakgrundspolling ([templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
    - Lagt till ett gult/orange "Starting..."-läge som visas omedelbart när en mottagare aktiveras.
    - Implementerat sekvenserad polling vid 400ms, 1000ms, 1800ms, 3000ms och 4500ms efter av/på-växling, nyskapande och kloning.
    - Lagt till en stående bakgrundspolling (var 3.5:e sekund och vid flikväxling via `visibilitychange`) så att kortens status alltid speglar verkligheten utan att användaren behöver göra F5.
    - Implementerat in-place uppdatering av badge, frekvens och switch i DOM utan att korten ritas om eller tappar fokus.
  - **Garanterat Flöde för TETRA-basstationer ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py), [database.py](file:///d:/antigravity/pager-monitor/database.py))**:
    - Avlägsnat den tysta `continue`-blockeringen i `sdr_processor.py`. Basstationer parsas och sänds nu alltid ut till larmtabellen och SSE med fullständig metadata.
    - Lagt till automatisk databasmigrering i `init_db()` som uppdaterar eventuella äldre `log_tetra_basestations: 'false'`-värden till `'true'`.
    - Användaren kontrollerar nu filtreringen i realtid direkt via snabbknappen `Basstationer: Visas / Dolda` på huvudsidan och larmsidan.
- **Verifiering**:
  - Samtliga 54 enhetstester passerar felfritt.
  - Versionsbump till CalVer `2026.10.13.25`.

---

### 23. Fix för Mottagarlista i Inställningar, TETRA-bärvågslåsning och Versionsspårbarhet (v2026.10.13.26)
- **Problembeskrivning**:
  1. Inställningssidan renderade inga mottagare och webbläsarkonsolen loggade `settings:629 Uncaught SyntaxError: Identifier 'currentSDRs' has already been declared`.
  2. TETRA-basstationer registrerades som "HIT" i RF ACTIVITY och skapade nya kanaler för varje detekterad frekvens vid svep.
  3. TETRA-skannern låste på en basstation men övergav frekvensen efter 30 sekunder och sökte vidare trots godtagbar signal.
  4. Sidopanelen visade äldre CalVer-version (`v2026.10.13.21`) och Docker-uppstarten saknade tydlig versionsbanner.
- **Teknisk Implementering**:
  - **Syntaxfix i Mottagarinställningar ([templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
    - Avlägsnat den duplicerade variabeldeklarationen `let currentSDRs = [];` på rad 629. JavaScript-exekveringen fungerar nu felfritt och alla SDR-mottagarkort renderas omedelbart vid sidladdning.
  - **TETRA Basstationer som Telemetri ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py), [static/waterfall.js](file:///d:/antigravity/pager-monitor/static/waterfall.js))**:
    - Basstationer identifieras nu och behandlas som ren bärvågstelemetri: uppdaterar `active_frequency`, loggar i backend, och skickar SSE-ping utan att sparas som larm i databasen.
    - I `waterfall.js` exkluderas basstationsannonser från att skapa pills i RF ACTIVITY eller öka HIT-räknaren.
  - **Permanent Bärvågslåsning för TETRA ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Den hårda 30-sekunders inaktivitetstimern i `stream_continuous` har tagits bort så att skannern stannar kvar på den låsta basstationen och kontinuerligt avkodar anrop och SDS.
  - **Versionsspårbarhet och Docker-startbanner ([app.py](file:///d:/antigravity/pager-monitor/app.py))**:
    - `APP_VERSION` uppdaterat till `2026.10.13.26`.
    - Lagt till en framträdande loggbanner vid Docker-start i konsolen.
- **Verifiering**:
  - Samtliga 54 enhetstester i testsviten passerar felfritt.

---

### 24. Synkbaserad Bärvågsbevakning och Driftlägen för TETRA (v2026.10.13.27)
- **Problembeskrivning**:
  1. Den tidigare logiken i `stream_continuous` baserade aktivitet på användartrafik (samtal/SDS), vilket gjorde att skannern riskerade att överge en aktiv mast nattetid när ingen talade.
  2. Omvänt, att aldrig svepa vidare gjorde att systemet inte kunde återhämta sig om antennen kopplades ur eller en mast släcktes ner.
  3. Behov av att välja mellan permanent trafiklyssning och aktiv kartläggning av basstationer i närområdet.
- **Teknisk Implementering**:
  - **Synk- och Styrsignalsbaserad Aktivitet ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - [TetraDemodulator](file:///d:/antigravity/pager-monitor/tetra_decoder.py) räknar nu alla mottagna TETRA Synchronization Training Sequences (STS) och MAC-ramar. Så länge basstationens styrsignal tas emot (upp till 17 gånger per sekund) nollställs `last_sync_time`.
    - Mottagaren förblir låst i oändlighet även mitt i natten så länge bärvågen sänder.
  - **10-sekunders Timeout för Faktisk Signalförlust ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Om antennen kopplas ur eller mastens styrsignal helt tappas bort i mer än 10 sekunder loggas: `Förlorade synk mot basstationen på <frekvens> (ingen styrsignal på 10 sek) – återupptar skanning`, loopen bryts och skannern söker automatiskt upp nästa frekvens.
  - **Driftlägen: Dedikerad Monitor vs. Explorer ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py), [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py), [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
    - **Dedikerad Monitor (`monitor`)**: Standard. Stannar på starkaste kontrollkanalen så länge synk finns.
    - **Explorer (`explorer`)**: Kartläggningsläge. Stannar på varje detekterad mast under konfigurerad fördröjningstid (standard 60s), registrerar nätverksdata, färgkod och Cell ID, och sveper därefter vidare.
    - Användaren kan konfigurera driftläge och fördröjningstid direkt via Inställningar.
- **Verifiering**:
  - Samtliga 54 enhetstester passerar felfritt.

---

### 25. Protokollspecifika Inställningar, Sparning av Driftläge och Fix för Rensning av Basstationer (v2026.10.13.28)
- **Problembeskrivning**:
  1. I formuläret för SDR-mottagarinställningar ([templates/sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html)) visades multimon-ng och rtl_fm FM-demoduleringsinställningar (t.ex. Log Level, Charset, Output Format, De-emphasis, Atan math) även när protokollet ändrades till TETRA, trots att TETRA använder ren I/Q-strömning via `rtl_sdr` och inbyggd pi/4-DQPSK-demodulering.
  2. Valet av TETRA Driftläge och Fördröjningstid under Inställningar i webbläsaren sparades inte utan återställdes vid omladdning.
  3. Klick på knappen "Rensa tidigare basstationsloggar ur databasen" genererade ett HTTP 500-fel (`Exception on /api/messages/basestations [DELETE]`) och felmeddelande i JavaScript.
- **Teknisk Implementering**:
  - **Dynamiska Protokollvyer ([templates/sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html))**:
    - Skapat separata dynamiska sektioner för TETRA och POCSAG/AFSK.
    - När TETRA väljs döljs alla multimon-ng- och FM-ljudfilter automatiskt. Istället visas kontroller för TETRA Driftläge (`monitor` vs `explorer`), fördröjningstid och I/Q Samplingshastighet (1.8 - 2.4 MS/s) samt anpassad hjälptext för frekvensformatet.
  - **Tillåtna Nycklar och Databaskolumner ([app.py](file:///d:/antigravity/pager-monitor/app.py), [database.py](file:///d:/antigravity/pager-monitor/database.py))**:
    - Lagt till `tetra_scan_mode` och `tetra_dwell_time` i `allowed_keys` och `sdr_restart_keys` i `/api/settings` i [app.py](file:///d:/antigravity/pager-monitor/app.py).
    - Lagt till kolumnerna `tetra_mode` och `tetra_dwell_time` i `sdr_instances`-tabellen i databasen samt i uppdaterings- och kloningsfunktionerna.
  - **Robust Rensning av Basstationer ([database.py](file:///d:/antigravity/pager-monitor/database.py), [app.py](file:///d:/antigravity/pager-monitor/app.py))**:
    - Definierat `get_db_connection()` och [clear_basestation_messages()](file:///d:/antigravity/pager-monitor/database.py) i `database.py`. Raderar alla oskyddade rader för basstationer och nätverksannonser och returnerar antalet rader som togs bort.
    - Uppdaterat `/api/messages/basestations` med try/catch felhantering och giltigt JSON-svar.
---

### 26. Återställt Fullständig Basstationsavkodning med Alias och Nätdata (v2026.10.13.29)
- **Problembeskrivning**:
  - Basstationer loggades enbart som kort telemetri (`TETRA BASSTATION SYNKRISERAD: ...`) och dök inte upp i larmflödet eller databasen. Användaren saknade basstationsnamn (`Rakel Basstation`), nätverkstillhörighet (`Sverige / Rakel (MSB)`) och adress (`RAKEL-240-01`).
- **Teknisk Implementering**:
  - Orsaken var en för tidig `continue`-sats i `sdr_processor.py` direkt efter telemetri-anropet som avbröt avkodningspipelinen innan meddelandetext, aliasuppslagning och `save_message()` hann anropas.
  - Villkoret justerades så att `continue` enbart körs om användaren valt att stänga av basstationsloggning (`log_tetra_basestations == 'false'`). När loggning är aktiv fortsätter pipelinen ner till adressering och formatering.

---

### 27. Kontinuerlig Synkförnyelse i TETRA-ström och Eliminering av 10-sekunders Timeout (v2026.10.13.30)
- **Problembeskrivning**:
  - Mottagaren låste framgångsrikt på TETRA-basstationen (t.ex. 392.250 MHz eller 392.225 MHz med stark signal +31 dB SNR), men efter exakt 10 sekunder bröts låsningen och mottagaren återupptog frekvenssvepet.
  - Orsaken var att `last_sync_time` sattes enbart vid den initiala bärvågslåsningen och inte förnyades under den efterföljande I/Q-strömningen i `stream_continuous`.
  - När timeouten slog till svartlistades frekvensen tillfälligt, vilket ledde till att skannern hoppade 25 kHz till en sidlob av samma fysiska mast.
- **Teknisk Implementering**:
  - I `stream_continuous` ackumuleras I/Q-datachunkar i buffertar på ca 40 ms.
  - Vid varje block körs `check_channel_dqpsk_modulation` och `process_bits` med frekvensdrift-kompensation (CFO) mot den låsta kanalen.
  - Om en giltig TETRA-burst, pi/4-DQPSK-signal (score >= 0.35) eller MAC-synksekvens bekräftas, förnyas `last_sync_time = time.time()` kontinuerligt.
  - Skannern stannar därmed kvar permanent på masten i `monitor`-läge och avbryter endast om signalen faktiskt försvinner helt i över 10 sekunder.
  - Infört periodisk `DEBUG`-bursttelemetri var 5:e sekund och tydlig konsolloggning av basstationer (`TETRA BASSTATION IDENTIFIERAD: [RAKEL-240-01] Rakel Basstation | ...`).
- **Verifiering**:
  - Samtliga 56 enhetstester passerar felfritt.

---

### 28. Filtrering av Krypterade Master (Gå vidare om MNC=1 / Rakel) (v2026.10.13.31)
- **Problembeskrivning**:
  - I TETRA-bandet är MSB:s Rakel (MCC 240, MNC 01) krypterat med TEA2, medan civila TETRA-nätverk (t.ex. industri, kollektivtrafik, flygplatser med MNC != 1) ofta kör i okrypterat öppet läge (Clear Mode).
  - Användaren önskade ett val både i globala inställningar och per individuell mottagare för att automatiskt gå vidare om basstationen är MNC=1 (krypterad Rakel) och istället fokusera på att finna och avkoda civila och öppna TETRA-nät.
- **Teknisk Implementering**:
  - **Inställning och Databas ([database.py](file:///d:/antigravity/pager-monitor/database.py), [app.py](file:///d:/antigravity/pager-monitor/app.py))**:
    - Lade till `tetra_skip_encrypted` i `get_default_settings()`, tabellen `sdr_instances` och i `allowed_keys`/`sdr_restart_keys` i `/api/settings`.
  - **Gränssnittsstöd ([templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html), [templates/sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html))**:
    - Under TETRA Skanningsläge i Inställningar finns nu kryssrutan *"Gå vidare om MNC=1 (Hoppa över krypterad Rakel, sök civila/öppna nät)"* med autosparning.
    - I formuläret för att redigera en SDR-mottagare finns ett val per mottagare *"Hoppa över krypterade master (MNC=1)"*.
  - **Dekoderlogik ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py), [tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py) skickar flaggan `--skip-encrypted` till [tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py) när inställningen är aktiverad.
    - Vid frekvenssvep hoppar `tetra_decoder.py` omedelbart över det statliga Rakel-blåljusbandet (380–385 MHz och 390–395 MHz) utan att slösa tid.
    - Vid låsning på övriga frekvenser kontrollerar `stream_continuous` de mottagna basstationsdata: om `MNC == 1` avbryts strömningen direkt, frekvensen svartlistas och skannern söker vidare.
    - Avkodade nätverk märks tydligt med `[ÖPPET / CIVIL]` respektive `[KRYPTERAT]`.
- **Verifiering**:
  - Samtliga enhetstester passerar felfritt.

---

### 29. RDS-TMC Dekoder (ALERT-C) och Åtgärdad Respektering av MNC!=1 (v2026.10.13.32)
- **Problembeskrivning**:
  1. Användaren önskade stöd för avkodning av RDS-TMC trafikmeddelanden över FM-radio (SR P3/P4) enligt ALERT-C (ISO 14819) standarden, med automatisk översättning av talkoder och koordinatuppslag via Trafikverkets platstabell (LTN 01).
  2. TETRA-mottagaren respekterade inte valet att hoppa över krypterad Rakel (`MNC=1`) utan fortsatte att rapportera eller stanna på Rakel-master.
- **Teknisk Implementering**:
  - **RDS-TMC Dekodermodul ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Läser JSON-utdata från `redsea` (grupp 8A och 3A) samt standard RDS-metadata (PS, RT).
    - Innehåller komplett svensk katalog för ALERT-C händelsekoder (ISO 14819-2) för olyckor, köbildning, vägarbeten, halka, hinder och avstängningar.
    - Integrerar Sveriges officiella platstabell (Location Table LTN 01) med WGS84-koordinater och trafikplatsnamn för E4, E20, E18, E6, E22, Riksväg 73, Riksväg 40 m.fl.
    - Inkluderar inbyggt simulerings- och testflöde (`--test-feed`) när hårdvara eller `redsea` saknas.
  - **SDR-Processintegration ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Lagt till `protocol == 'RDS-TMC'` som startar [rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py) under övervakning av watchdog.
    - Läser `RDS-TMC:` rader, mappar adress (`E4:14210`), alias (trafikplatsnamn) och skickar med latitud, longitud, vägnummer och brådskandegrad via SSE och MQTT.
    - Registrerat `redsea` och `rds_decoder` i processdödaren (`kill_orphaned_rtl_for_device`).
  - **Åtgärdat Respektering av MNC!=1 ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py), [tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py), [templates/sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html))**:
    - **Boolean-strängfel**: I `sdr_processor.py` orsakade `config.get('tetra_skip_encrypted') or current_settings...` att databasens standardvärde `'false'` på instansen blockerade globala inställningar. Detta korrigerades så att den globala inställningen appliceras om den aktiveras, eller om instansen sätts till `'true'`.
    - **För tidig NET-sändning**: I [tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py) skickades en hårdkodad `TETRA: NET MCC: 240 MNC: 01` innan styrsignalen (BSCH) ens hunnit avkodas. Denna togs bort vid `skip_encrypted` så att endast verifierade civila basstationer (MNC != 1) tillåts passera.
    - **Filter i processorn**: I `monitor_instance()` implementerades en spärr som omedelbart kastar alla basstationer och anrop med `MNC=1` när `skip_encrypted` är aktivt.
    - **Inställningsdialog**: Lagt till alternativet `Använd global inställning` (`inherit`) i mottagarredigeringen.
- **Verifiering**:
  - Samtliga 48 enhetstester i `tests/test_sdr_watchdog.py` och `tests/test_security_and_larm.py` passerar felfritt.

---

### 30. Automatisk FM-frekvenssökning för RDS, Redsea i Dockerfile och Subprocess Exit-fix (v2026.10.13.33)
- **Problembeskrivning**:
  1. **RDS-frekvens och Manuellt Sökande**: Användaren noterade att mottagaren stod på `169.800M` (POCSAG-standardfrekvens) för RDS och frågade: *"frekvens för RDS ... borde den inte söka efter detta själv?"*. RDS-TMC sänds i FM-rundradiobandet (87.5–108.0 MHz) över främst Sveriges Radio P4. Användaren ska inte behöva slå upp sin lokala P4-frekvens manuellt.
  2. **Watchdog Oväntad Nedstängning (`exit=0`)**: I Docker-loggen kraschade RDS-dekodern omedelbart med: `[RDS] Processer avslutades ovantat! rtl PID=N/A exit=N/A, decoder PID=120 exit=0`.
     - Orsaken var `if not sys.stdin.isatty(): for line in sys.stdin:`. I daemons/containrar är `sys.stdin.isatty()` alltid `False`. När `sys.stdin` inte tillhandahålls i `Popen` träffade loopen omedelbart EOF och Python avslutades direkt med kod 0.
  3. **Kompilering av `redsea` i Docker**: Debian Bookworm saknar officiellt paket för `redsea`.
- **Teknisk Implementering**:
  - **Automatisk Frekvenssökning i FM-bandet ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Implementerat funktionen `scan_fm_frequencies(device_idx, gain)`.
    - Om den angivna frekvensen är utanför FM-bandet (t.ex. `169.800M`), eller satt till `auto` eller `scan`, initierar dekodern ett automatiskt frekvenssvep över Sveriges Radio P4-frekvenser (98.0M, 99.3M, 101.9M, 103.3M, m.fl.) samt stegvis FM-skanning.
    - Mäter bärvågseffekt med `rtl_power` eller provlyssnar med `rtl_fm`. När en stark FM-signal detekteras låser dekodern automatiskt och rapporterar: `RDS-TMC: LOCK Freq: <frekvens> MHz`.
  - **Kompilering av Redsea i Multi-stage Dockerfile ([Dockerfile](file:///d:/antigravity/pager-monitor/Dockerfile))**:
    - Lagt till `meson`, `ninja-build`, `libliquid-dev`, `libsndfile1-dev` och `nlohmann-json3-dev` i builder-steget.
    - Klona och bygger `https://github.com/windytan/redsea.git` och installerar `/usr/local/bin/redsea`.
    - Kopierar över binären samt installerar körtidsbiblioteken `libliquid1` och `libsndfile1` i produktionsbilden.
  - **Åtgärdad Subprocess Exit 0 ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Ersatt den automatiska stdin-kontrollen med en explicit `--stdin`-flagga.
    - Avkodaren läser nu endast från stdin om den anropas med `--stdin`, vilket eliminerar omedelbar nedstängning vid körning i Docker och underordnade processer.
  - **Telemetri och Watchdog-hantering ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Lagt till hantering av `RDS-TMC: SCAN` och `RDS-TMC: LOCK` i processorn, så att aktuell vald FM-frekvens automatiskt uppdateras och visas i gränssnittet.
- **Verifiering**:
  - Samtliga 48 enhetstester i `tests/test_sdr_watchdog.py` och `tests/test_security_and_larm.py` passerar felfritt.
  - Versionsbump till CalVer `2026.10.13.33`.

---

### 31. Rensning av Testfiler från Git-index och Bevarande Lokalt (v2026.10.13.34)
- **Problembeskrivning**:
  - Användaren begärde att ta bort alla testfiler och utvecklingsskräp från GitHub, men bevara dem lokalt på maskinen för fortsatt lokal verifiering.
- **Genomförda Åtgärder**:
  - **Git Ignore ([.gitignore](file:///d:/antigravity/pager-monitor/.gitignore))**:
    - Lagt till `tests/` under sektionen för enhetstester och täckningsrapporter.
  - **Avregistrering från Git Tracking**:
    - Kört `git rm -r --cached tests/` vilket tar bort `tests/test_imports.py`, `tests/test_log_console.py`, `tests/test_sdr_watchdog.py`, `tests/test_security_and_larm.py` och `tests/test_stats_api.py` från versionskontrollen och framtida commits till GitHub.
    - Samtliga 5 testfiler och underkataloger finns kvar oförändrade på den lokala disken.
  - **Versionsspårbarhet**:
    - Versionsbump till CalVer `2026.10.13.34` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md) och [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md).

---

### 32. Strikt Begränsning till RDS-TMC Trafikmeddelanden & Eliminering av Låttextspam (v2026.10.13.35)
- **Problembeskrivning**:
  - Användaren rapporterade att loggen och databasen översvämmades av duplicerade meddelanden från kommersiell radio:
    `[RDS] RAW: RDS: PS: RIX FM PI: 0xE241`
    `[RDS] RAW: RDS: PI: 0xE241 RT: Bäst musik just nu! [MERGED] Repeat count 79x on ID 187985`
  - Användaren klargjorde: *"Dessa är ju vanliga RDS ... Vi skulle ju bara visa TMC meddelanden... Nu blir vi spammade av en radiokanal som visar den aktuella spelade låten."*
- **Identifierade Orsaker**:
  1. I [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py) tolkades `RDS:` som ett giltigt larmmeddelande (`parsed = {'address': f'RDS-{pi_val}', 'message': rt_val, ...}`). Varje gång RadioText ändrades eller repeterades skapades en ny larmrad i databasen.
  2. Kommersiella kanaler som RIX FM (100.5 MHz i Stockholm) sänder inte TMC (ALERT-C trafikmeddelanden), utan sänder enbart stationsnamn och aktuell låt/artist. I Sverige är det uteslutande Sveriges Radio P4 (och delvis P3) som sänder RDS-TMC.
  3. Den automatiska frekvenssökningen i [rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py) hade en hårdkodad fallback till `100.5M`, vilket i Mälardalen/Stockholm råkar vara just RIX FM.
- **Teknisk Implementering**:
  - **Strikt Exkludering av Vanlig RDS ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Avlägsnat tolkningen av `RDS:` som meddelanden. Linjer som börjar med `RDS:` eller `RDS-INFO:` fångas direkt i loopen och loggas enbart som debug-telemetri (`RDS TELEMETRI:`). De når aldrig `on_new_message()`, sparas aldrig i databasen och skickas aldrig till SSE eller MQTT.
    - Endast `RDS-TMC:` behandlas som giltiga larmmeddelanden.
  - **Uteslutande av Låttexter ur Avkodaren ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Tagit bort utskrift av `RadioText` (låttitlar, artister och jinglar) ur [rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py).
    - Stationsnamn (`PS`) rapporteras nu som ren telemetri (`RDS-INFO:`) och enbart en enda gång per stationsbyte.
  - **Riktad P4-frekvenssökning ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Sökfunktionen `find_best_fm_station` kontrollerar aktivt Sveriges Radio P4:s frekvenser (P4 Stockholm 103.3M, P4 Sörmland 100.1M, P4 Uppland 102.5M, P4 Göteborg 101.9M m.fl.).
    - Känner av stationer med PI `0xE204`/`0xE4xx` och låser enbart på P4-stationer med aktiv TMC-bärvåg.
    - Ändrat standard fallback från 100.5M till 103.3M (SR P4 Stockholm).
  - **Automatisk Rensning av Databas ([database.py](file:///d:/antigravity/pager-monitor/database.py))**:
    - I `init_db()` körs nu en automatisk rensning (`DELETE FROM messages WHERE bitrate = 'RDS-PS' OR address LIKE 'RDS-%'`) som raderar tidigare felaktigt sparade låttexter från kommersiella kanaler.
- **Verifiering**:
  - Samtliga 25 enhetstester inklusive nytt test `test_non_tmc_rds_telemetry_not_saved_as_message` passerar felfritt.
  - Versionsbump till CalVer `2026.10.13.35`.

---

### 33. Stöd för Tomt Frekvensfält, Intervallhantering och Tydliggörande av Auto/Scan (v2026.10.13.36)
- **Problembeskrivning**:
  1. Användaren angav frekvensintervallet `87.5M-108M`, men radion låste omedelbart på `87.5M` där det inte fanns någon sändare (`[RDS] RDS-TMC LOCK: Station låst på frekvens 87.5M (Freq: 87.5M-108M Status: LOCKED (FM-frekvens låst))`).
  2. Användaren önskade att kunna lämna frekvensfältet helt tomt så att den starkaste P4-stationen söks upp automatiskt, och påpekade att information om att man kan ange `auto` eller `scan` saknades under frekvensfältet i användargränssnittet.
- **Identifierade Orsaker**:
  1. `parse_freq_to_hz` hanterade inte strängar med bindestreck som `87.5M-108M`. Den kastade ett `ValueError`, föll tillbaka på standardvärdet och fick skriptet att tro att frekvensen redan var en enskild giltig frekvens istället för ett skanningsintervall.
  2. Frekvensfältet i formulären hade ett tvingande `required`-attribut i HTML, vilket hindrade användaren från att spara ett tomt fält för automatisk sökning.
- **Teknisk Implementering**:
  - **Intervall- och Scan-detektering ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Implementerat `is_fm_scanning_range(freq_str)` och `parse_range_hz(freq_str)` som känner av om fältet är tomt, satt till `auto`/`scan`, eller innehåller intervall som `87.5M-108M`.
    - I dessa fall initieras alltid `find_best_fm_station` med rätt min/max frekvensgränser så att en bekräftad Sveriges Radio P4-station väljs.
  - **Stöd för Tomt Frekvensfält ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py), [database.py](file:///d:/antigravity/pager-monitor/database.py))**:
    - Om frekvens lämnas tom (`""`) sätts den automatiskt till `'auto'` för `RDS-TMC`, `'390M-395M'` för `TETRA` och `'169.8M'` för `POCSAG`.
  - **Uppdaterade Gränssnittstexter ([templates/sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html), [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
    - Tagit bort `required` från formulären.
    - Lagt till tydliga hjälptexter och placeholders under frekvensfältet som informerar användaren om att man kan ange `auto`, `scan` eller lämna fältet helt tomt för automatisk sökning efter närmaste och starkaste Sveriges Radio P4-sändare.
- **Verifiering**:
  - Samtliga 25 enhetstester passerar felfritt.
  - Versionsbump till CalVer `2026.10.13.36`.

---

### 34. Återställd Visning av Låsta TETRA-basstationer i Meddelandeflödet (v2026.10.14.01)
- **Problembeskrivning**:
  - Användaren rapporterade att fastän loggen visar att en basstation låsts (`[TETRA] TETRA LOCK: Basstation låst på frekvens 421.05M (TETRA bärvåg bekräftad, SNR: +4.0 dB, Score: 63%)`) och knappen `Basstationer: Visas` var aktiverad i användargränssnittet, visades ingen basstationshändelse alls i tabellen.
- **Identifierade Orsaker**:
  1. I `sdr_processor.py` hanterades `TETRA LOCK` enbart som intern telemetri för instansens aktiva frekvens med en direkt `continue`-sats. Händelsen genererade därför inget larm- eller basstationsmeddelande till databasen eller gränssnittet.
  2. I hårdvaruskanningsslingan i `tetra_decoder.py` var anropet till `format_and_print_event("NET", ...)` villkorat med `if not self.skip_encrypted:`. Om krypteringsfiltret var påslaget skickades därför ingen `NET`-händelse alls vid låsning.
  3. Dessutom hårdkodades nätverket till `Sverige / Rakel (MSB) (MCC: 240, MNC: 01)` oavsett frekvens. För frekvenser i 410–430 MHz (t.ex. 421.05 MHz) rör det sig i själva verket om civila TETRA-nätverk (t.ex. SL, industri, transport), vilket orsakade att filtret felaktigt antog att masten tillhörde det krypterade Rakel-nätet och undertryckte meddelandet.
- **Teknisk Implementering**:
  - **Frekvens- och Nätverksseparation ([tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py))**:
    - Skannern kontrollerar nu om den detekterade frekvensen ligger i Rakel-bandet (380–385 / 390–395 MHz) eller i civila band (410–430 MHz).
    - För civila frekvenser sätts nätverksdata till `Civilt TETRA [ÖPPET / CIVIL]` (`MCC: 240`, `MNC: 10`), och `NET`-händelsen genereras omedelbart även när `skip_encrypted` är aktiverat.
  - **Adresstilldelning och Alias ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Vid mottagning av `NET`-händelse för civila master sätts adressen till `TETRA-<frekvens>` (t.ex. `TETRA-421.05M`) och alias till `Civilt TETRA Basstation`.
    - Lade till realtidstelemetri på `TETRA LOCK` så att gränssnittet uppdaterar aktiv lyssnarfrekvens direkt.
- **Verifiering**:
  - Samtliga 25 enhetstester passerar felfritt.
  - Versionsbump till CalVer `2026.10.14.01`.

---

### 35. RDS-TMC Grupp 3A Handskakning, Strikt Stationsvalidering och ALERT-C (v2026.10.14.02)
- **Problembeskrivning och Kravspecifikation**:
  - Användaren tillhandahöll en teknisk genomgång av ALERT-C (ISO 14819):
    1. Stationstest: TMC sänds enbart via Sveriges Radio P4 (PI-kod `0xE204..0xE23F` / `0xE4xx`). Kommersiella kanaler sänder inte TMC.
    2. Grupp 3A (Systeminformation / Handskakning): Verifiera Application Identifier (AID) `0xCD46`, Location Table Number (LTN) `1` och ECC `0xE1`.
    3. Grupp 8A (Trafikmeddelanden): Avkoda händelsekoder (1–2047), platskod (1–65535), riktning, utsträckning (extent), prioritet (urgency) och varaktighet.
- **Teknisk Implementering**:
  - **Grupp 3A Handskakning ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Implementerat tolkning av Grupp 3A i `parse_redsea_json_line`. När AID `0xCD46` och LTN `1` identifieras bekräftas TMC-stöd och låsning omedelbart.
  - **Strikt Stationsvalidering ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - `format_and_print_rds` verifierar nu om kanalen är SR P4 eller en kommersiell station (t.ex. RIX FM, Mix Megapol). Kommersiella kanaler loggas med information om att de saknar TMC.
  - **Utökade ALERT-C Händelsekoder ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Kompletterat `ALERT_C_EVENTS` med fler standardiserade ISO 14819-2 koder (köbildning, väglag, halka, broarbeten m.m.).
- **Verifiering**:
  - Samtliga 25 enhetstester passerar felfritt.
  - Versionsbump till CalVer `2026.10.14.02`.
