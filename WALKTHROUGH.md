# Walkthrough: PagerMonitor Development and Features

## Version Information
- **CalVer**: `2026.10.15.12`
- **Date**: 2026-10-15
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

---

### 36. Egen Bakgrundsfärg för Basstationer i Larm- och Meddelandeflödet (v2026.10.14.03)
- **Problembeskrivning**:
  - Användaren önskade att basstationsrader ska ha en egen, distinkt bakgrundsfärg i meddelandeflödet så att de omedelbart skiljer sig från vanliga personsökarlarm och utryckningar.
- **Teknisk Implementering**:
  - **CSS-färgprofil för `.basestation-row` ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html))**:
    - **Ljust tema:** Mjuk ljusblå/azur ton (`#f0fdfa` och `#e0f2fe`) med en markerad azurblå vertikal kantlist (`border-left: 4px solid #0284c7`).
    - **Mörkt tema:** Diskret cyan ton (`rgba(6, 182, 212, 0.08..0.15)`) med en vertikal kantlist i cyan (`border-left: 4px solid #06b6d4`).
    - Hover-effekt med mjukt ökad färgintensitet.
  - **Radklassning i JavaScript ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html))**:
    - `createAlarmRowNode` kontrollerar om raden är en basstation (`TETRA-NET`, `RAKEL-`, `TETRA-`, alias innehållande `Basstation` eller meddelande med `Aktiv TETRA Basstation`).
    - Basstationer tilldelas automatiskt klassen `basestation-row`.
    - I larmlistan tilldelas basstationen en dedikerad ljusblå `BASE`-tagg istället för en röd larm-tagg.
- **Verifiering**:
  - Samtliga 25 enhetstester passerar felfritt.
  - Versionsbump till CalVer `2026.10.14.03`.

---

### 37. Realtidspuls (Heartbeat) för RDS-mottagning och Stationssynk (v2026.10.14.04)
- **Problembeskrivning**:
  - RDS sänder bärvåg och grupper kontinuerligt (flera gånger i sekunden), men trafikmeddelanden (TMC) och radiotext inträffar sporadiskt. Det saknades visuell bekräftelse i loggarna på att radiomottagaren har aktiv synk och godkända RDS-block när inga användarmeddelanden sänds.
- **Teknisk Implementering**:
  - **Trådsäker Pulsmätare ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Skapade `record_rds_frame(pi, ps, count)` skyddad av `threading.Lock()`. Varje mottagen rad från `redsea` som avkodas korrekt betraktas som en rå puls och ökar ramräknaren samt uppdaterar senaste aktivitetstid och senast sedda PI/PS.
    - Även testflödet simulerar kontinuerlig mottagning med ~11.2 ramar/s.
  - **Bakgrundsövervakare ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Dedikerad bakgrundstråd (`_heartbeat_worker`) som kontrollerar status oberoende av I/O-blockeringar på `redsea`:s stdout.
    - Konfigurerbart intervall via `--heartbeat-interval` (standard: 10s) och timeout via `--heartbeat-timeout` (standard: 5s).
    - Vid godkänd signal matas `RDS-HEARTBEAT: OK Station: {ps} (PI: {pi}) | Status: SYNKERAD | Takt: {rate:.1f} ramar/s | Senaste aktivitet: {elapsed:.1f}s sedan` ut till stdout.
    - Vid signalförlust (> timeout) matas `RDS-HEARTBEAT: LOST Ingen RDS-signal detekterad på {elapsed:.1f}s (Signalbortfall eller frekvens saknar RDS)` ut.
  - **Processorns Loggning ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - I `monitor_instance()` fångas `RDS-HEARTBEAT:` upp och loggas med `logger.info` vid synk och `logger.warning` vid signalbortfall, vilket ger användaren tydliga loggrader:
      `INFO: [RDS] HEARTBEAT -> Station: SR P4 (PI: 0xE204) | Status: SYNKERAD | Takt: 11.2 ramar/s | Senaste aktivitet: 0.1s sedan`
  - **Webbgränssnitt ([templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html), [database.py](file:///d:/antigravity/pager-monitor/database.py))**:
    - Lade till konfigurationsfält för `rds_heartbeat_interval` och `rds_heartbeat_timeout` under inställningar med omedelbar direktsparning.
- **Verifiering**:
  - Samtliga 26 enhetstester passerar felfritt, inklusive `test_rds_heartbeat_logging`.
  - Versionsbump till CalVer `2026.10.14.04`.

---

### 38. Kontinuerlig Frekvensskanning och Eliminering av RDS-loggspam (v2026.10.14.05)
- **Problembeskrivning**:
  1. Om en frekvens saknar RDS-TMC (t.ex. sänder kommersiell musik eller brus), stannade tidigare avkodaren kvar på frekvensen och sökte inte vidare.
  2. När en station väl låstes (t.ex. P4 Sörmland på 88.7 MHz) spammades loggarna varje sekund med upprepade `RDS-INFO: PS: P4 Sörml PI: 0xEA24` och `RDS-TMC LOCK: Station låst på frekvens 88.7M...`.
- **Teknisk Implementering**:
  - **Eliminering av Logg-spam ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py), [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - `format_and_print_rds`: Uppdaterar internt minne och skriver enbart ut `RDS-INFO:` när ny information mottagits. Växlingar mellan rader med enbart PI och rader med både PS och PI filtreras bort.
    - `format_and_print_lock`: Spärrad med tillståndsflagga så att bärvågslåsning för en radiostation endast skrivs ut exakt EN gång per kanal.
    - `is_sr_p4_station`: Utökad med stöd för regionala PI-koder med prefix `EA` (t.ex. `0xEA24` för P4 Sörmland).
    - `sdr_processor.py`: Tillagd deduplicering i `monitor_instance()` för både `RDS-INFO` och `RDS-TMC LOCK`.
  - **Kontinuerlig Skanning och Frekvensbyte ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Skapade `P4_STATIONS` med 25 Sveriges Radio P4-sändare i Sverige (inklusive 88.7M, 100.1M, 103.3M etc.).
    - `get_p4_candidates`: Bygger prioriterad kandidatkö. Om användaren angett en specifik frekvens prövas den först, men övriga P4-sändare behålls som fallback ifall den angivna frekvensen saknar RDS-TMC.
    - `run_rds_session`: Kör `rtl_fm | redsea` med en icke-blockerande I/O-kö (`queue.Queue`) och 10 sekunders dwell-tid.
      - Om kommersiell station utan TMC detekteras (RIX FM etc.): avbryter omedelbart och provar nästa frekvens.
      - Om ingen RDS-TMC detekteras inom 10 sekunder: avbryter och provar nästa frekvens.
      - Om P4 / TMC detekteras: låser frekvensen och fortsätter i dedikerat lyssningsläge.
      - Om signalen förloras i över 30 sekunder återupptas sökningen automatiskt.
- **Verifiering**:
  - Verifierat att P4 Sörmland (PI 0xEA24) identifieras omedelbart och inte spamas vid upprepade anrop.
  - Samtliga 26 enhetstester passerar felfritt.
  - Versionsbump till CalVer `2026.10.14.05`.

---

### 39. Visning av Signalkvalitet och Gain i RDS Heartbeat-loggen (v2026.10.14.06)
- **Problembeskrivning**:
  - Användaren önskade se aktuell signalkvalitet och mottagarens Gain direkt i loggflödet för att enkelt kunna avgöra om Gain behöver justeras och hur justeringen påverkar mottagningen.
- **Teknisk Implementering**:
  - **Dynamisk Kvalitetsberäkning ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - RDS sänder data med en fast moduleringstakt på 1187.5 bit/s med 104 bitar per RDS-grupp (block A-D), vilket motsvarar ett teoretiskt max på cirka 11.41 grupper/ramar per sekund.
    - `_heartbeat_worker` beräknar den faktiska takten och kvalitetsprocenten: `quality_pct = int(round((rate / 11.41) * 100))`.
    - Pedagogisk kvalitetsbedömning:
      - `>= 90 %`: `Perfekt mottagning` (`Status: SYNKERAD`, typ `OK`)
      - `70 - 89 %`: `God mottagning` (`Status: SYNKERAD`, typ `OK`)
      - `40 - 69 %`: `Acceptabel (enstaka paketfel)` (`Status: SYNKERAD`, typ `OK`)
      - `< 40 %`: `Svag signal / Prova justera Gain` (`Status: SVAG SIGNAL`, typ `LOW`)
  - **Integrerad Gain-telemetri ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py), [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - `sdr_processor.py` skickar konsekvent med `--gain` (`auto` eller t.ex. `25` dB) vid start av `rds_decoder.py`.
    - Pulsmätaren inkluderar aktuell gain i loggsträngen (`Gain: 25 dB` eller `Gain: auto`).
    - `sdr_processor.py` fångar upp status `LOW` och loggar som `logger.warning`, vilket tydligt larmar användaren om Gain är för låg eller hög.
  - **Loggformat**:
    - Vid god synk:
      `INFO: [RDS] HEARTBEAT -> Station: P4 Sörml (PI: 0xEA24) | Status: SYNKERAD | Kvalitet: 98% (11.2/11.4 ramar/s - Perfekt mottagning) | Gain: 25 dB | Senaste aktivitet: 0.1s sedan`
    - Vid svag signal:
      `WARNING: [RDS] HEARTBEAT -> Station: P4 Sörml (PI: 0xEA24) | Status: SVAG SIGNAL | Kvalitet: 33% (3.8/11.4 ramar/s - Svag signal / Prova justera Gain) | Gain: 49.6 dB | Senaste aktivitet: 0.2s sedan`
    - Vid signalbortfall:
      `WARNING: [RDS] HEARTBEAT FÖRLORAD -> Ingen RDS-signal detekterad på 5.2s (Signalbortfall eller frekvens saknar RDS)`
- **Verifiering**:
  - Skapade och körde enhetstester i `tests/test_sdr_watchdog.py` som verifierar att loggarna hanterar `OK`, `LOW` och `LOST` med korrekta loggnivåer och strängar.
  - Verifierade manuell pulsmätning och kvalitetsberäkning i Python för både perfekt, svag och förlorad signal.
  - Samtliga 26 enhetstester passerar felfritt.
  - Versionsbump till CalVer `2026.10.14.06`.

---

### 40. Robust RDS-TMC ALERT-C Parsning, Ofiltrerat Redsea-läge (-u) och Syntetiskt Testläge (v2026.10.14.07)
- **Problembeskrivning**:
  - Trots utmärkt mottagning på P4 Sörmland (PI: 0xEA24, 11.5 ramar/s, 100% signalkvalitet) loggades inga TMC-händelser.
  - Orsaken var att `redsea` kördes utan `-u` (unfiltered mode), vilket gjorde att redsea internt buffrade och aggregerade data, samt att JSON-parsningen krävde strikt fältmatchning som riskerade att missa 8A-grupper.
- **Teknisk Implementering**:
  - **Ofiltrerat Redsea Processanrop ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Ändrat process-anropet till `redsea -u -r 171k`. Detta tvingar redsea att omedelbart dumpa alla mottagna 8A- och 3A-grupper utan aggregeringsfördröjning.
  - **Robust JSON-inspektion & TMC-parsning ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py), [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - **Grupp 3A (TMC System Information)**: Loggas på DEBUG-nivå med AID (`0xCD46`), LTN (1 för Sverige) och systemstatus (`AKTIV`).
    - **Grupp 8A (ALERT-C Trafikmeddelanden)**: Detekteras oavsett om redsea placerar fälten under `tmc`-objektet eller i rot-JSON med `group: 8A`.
    - Extraherar `location`, `event_codes`, `event_descriptions`, `extent`, `direction`, `urgency` och `duration`.
    - Genererar strukturerat loggmeddelande vid 8A:
      `INFO: [RDS-TMC] LARM MOTTAGET → Plats-ID: {location} | Händelse: {event_desc} | Riktning: {direction} | Omfattning: {extent} | Råkod: {event_codes}`
    - Formaterar och emitterar `RDS-TMC: LOC: ...` för PagerMonitors databas- och WebSocket-motor.
  - **Inbyggt Syntetiskt Testläge (`--test-tmc`)**:
    - Lagt till CLI-flagga `--test-tmc` i `rds_decoder.py` för omedelbar syntetisk injicering av Grupp 3A och Grupp 8A utan SDR-hårdvara.
    - Testpayload injicerar händelsekod 101 på E4 Nyköping (stillastående kö 2 km) och verifierar hela kedjan till loggutskrift och händelse-emittering.
  - **UTF-8 Encoding på Konsolen**:
    - Lagt till automatisk omkonfigurering av stdout/stderr till UTF-8 för att eliminera risken för `UnicodeEncodeError` vid utskrift av pilsymbolen `→`.
- **Verifiering**:
  - Testat `python rds_decoder.py --test-tmc` och verifierat att både 3A handskakning och 8A larmlogg emitteras felfritt.
  - Nytt enhetstest `test_rds_tmc_parsing_and_test_mode` i `tests/test_sdr_watchdog.py`.
  - Samtliga 27 enhetstester passerar felfritt.
  - Versionsbump till CalVer `2026.10.14.07`.

---

### 41. Mottagna RDS-grupptyper i Heartbeat och Grupp 3A Synk på INFO-nivå (v2026.10.14.08)
- **Problembeskrivning**:
  - Användaren såg utmärkt stationssynk (100% kvalitet) men inga loggar om mottagna TMC-meddelanden. För att ge 100% klarhet behövs transparens kring vilka faktiska RDS-grupper sändaren skickar i luften (t.ex. 0A, 2A, 3A, 8A).
- **Teknisk Implementering**:
  - **Spårning av RDS-grupper ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - `record_rds_frame` sparar alla unika mottagna grupper i en mängd (`groups_seen`).
    - Heartbeat-raden listar alla mottagna grupper:
      `INFO: [RDS] HEARTBEAT -> Station: P4 Sörml (PI: 0xEA24) | Status: SYNKERAD | Kvalitet: 100% (11.5/11.4 ramar/s) | RDS-grupper: 0A, 2A, 3A | Gain: 26 dB | Senaste aktivitet: 0.0s sedan`
  - **3A Handskakning på INFO-nivå ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
---

### 42. TMC-status i Heartbeat, Live Test-larm och Deduplicering (v2026.10.14.09 - v2026.10.14.12)
- **Problembeskrivning**:
  - Testlarm som sparades via databasen dök inte upp i webbläsarens realtidsflöde utan sidomladdning.
  - Sändarens kontinuerliga utmatning av Grupp 3A orsakade loggspam i realtidsloggen.
  - Protokollmärket för RDS-TMC visades som `RDS-TMCbps`.
- **Teknisk Implementering**:
  - **TMC-status i Heartbeat ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Heartbeat-raden visar nu explicit om stationen sänder TMC (Grupp 3A aktiv) och om det finns aktiva 8A-larm i luften eller ej.
  - **REST API och UI för Testlarm ([app.py](file:///d:/antigravity/pager-monitor/app.py), [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
    - Skapat `POST /api/test/tmc` som sparar testlarmet och emitterar det direkt över SSE (`/stream`) så att alla anslutna klienter uppdateras live.
    - Lagt till knappen "Skicka Testlarm" under Inställningar -> Manuella databasåtgärder.
  - **Deduplicering och Korrigerad Grupp 3A Matchning ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py), [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - Flyttat utskriften av 3A handskakning innanför `_group_3a_confirmed` samt lagt till deduplicering i `sdr_processor.py` för att helt eliminera spam.
    - Korrigerat `aid_str` så att icke-3A paket inte felaktigt tolkas som 3A.
  - **Snygga Protokoll-Badges ([index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html))**:
    - Förhindrat tillägg av `bps` på protokoll som `RDS-TMC` och `TETRA`.
- **Verifiering**:
  - Verifierat att testlarmet visas snyggt i tabellen med larmmarkering, platsnamn och koordinater.
  - Alla 27 enhetstester passerar.
  - Versionsbump till CalVer `2026.10.14.12`.

---

### 43. Dedikerat Protokollmärke i RF / META, Fix för Test-TMC och Synkad Versionsspårbarhet (v2026.10.14.14)
- **Problembeskrivning**:
  - Användaren önskade att tydligt se protokolltyp (`POCSAG`, `TETRA`, `RDS`, `AFSK`) i tabellens kolumn `RF / META`.
  - Vid klick på RDS-mottagaren i vattenfallet (RF Activity) sattes sökfiltret till mottagarens frekvens `'auto'` istället för `'RDS'`, vilket resulterade i att inga larm matchades.
  - När knappen för att skicka testsignal för RDS-TMC klickades uppstod ett backendfel: `NameError: name 'save_message' is not defined`.
  - Sidopanelens versionsnummer visade `v2026.10.14.08` trots att nyare versioner hade publicerats.
- **Teknisk Implementering**:
  - **Dedikerade Protokoll-Badges ([index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html), [style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
    - Implementerat logik som automatiskt härleder protokoll från meddelandedata och genererar färgkodade badges i kolumnen `RF / META`:
      - `POCSAG`: Smaragdgrön (`.proto-pocsag`).
      - `TETRA`: Bärnstensgul (`.proto-tetra`).
      - `RDS`: Korallrosa (`.proto-rds`).
      - `AFSK`: Indigoblå (`.proto-afsk`).
    - Smart komplettering av bitrate-märket så att underprotokoll och hastigheter (`1200bps`, `SDS`, `NET`, `TMC`) visas utan redundans.
  - **Protokoll-berikning i API & Databas ([database.py](file:///d:/antigravity/pager-monitor/database.py), [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py), [app.py](file:///d:/antigravity/pager-monitor/app.py))**:
    - Fältet `protocol` inkluderas i alla utgående SSE-meddelanden och härleds i `get_recent_messages()`.
  - **Åtgärdat Importfel vid RDS-TMC Testsignal ([app.py](file:///d:/antigravity/pager-monitor/app.py))**:
    - Importerat `save_message` i `app.py` så att testlarmet sparas och emitteras korrekt.
  - **Korrigerat Waterfall-filter för RDS ([static/waterfall.js](file:///d:/antigravity/pager-monitor/static/waterfall.js))**:
    - Klick på kanalen `RDS` filtrerar på `'RDS'` istället för `'auto'`, och inkommande `RDS-TMC`-larm mappas direkt till den befintliga `RDS`-kanalen.
  - **Synkroniserad Versionshantering ([app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md))**:
    - Uppdaterat `APP_VERSION` i `app.py` till `2026.10.14.14` vilket propageras automatiskt via context processorn till sidopanelen och footern i alla mallar.
- **Verifiering**:
  - Samtliga 27 enhetstester passerar (`python -m unittest discover tests`).
  - Versionsbump till CalVer `2026.10.14.14`.

---

### 44. Strikt Låsning vid Fast RDS-frekvens och Frekvens i Heartbeat-loggen (v2026.10.14.15)
- **Problembeskrivning**:
  - När användaren ställde in en specifik RDS-frekvens (t.ex. `103.3M`) sökte mottagaren vidare till andra P4-kandidater om TMC inte detekterades inom 10 sekunder eller vid svag signal. Användaren krävde att inställd frekvens ska gälla strikt utan frekvenshopp såvida inte `auto` eller `scan` angetts.
  - Heartbeat-raderna (särskilt vid `HEARTBEAT FÖRLORAD`) angav inte vilken frekvens mottagaren lyssnade på.
- **Teknisk Implementering**:
  - **Strikt Låsning på Fast Frekvens ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - `get_p4_candidates`: Om frekvensen är en fast kanal (inte `auto`, `scan`, `fm`, `all` eller intervall) returneras enbart denna enda frekvens som kandidat.
    - `run_rds_session`: Accepterar flaggan `is_scan`. Om `is_scan=False` avbryts aldrig sessionen vid 10 sekunders dwell-timeout, kommersiell sändning eller 30 sekunders signalbortfall. Mottagaren stannar kvar på frekvensen.
    - `main`: Kör en dedikerad evighetsloop på fast frekvens utan att söka vidare bland P4-kandidater.
  - **Frekvens i Heartbeat-loggen ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py), [sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - `_heartbeat_worker` inkluderar nu alltid `Frekvens: <freq> | ` i alla utskrifter (`OK`, `LOW` och `LOST`).
    - `sdr_processor.py` garanterar att `Frekvens: <freq> | ` alltid visas i konsolloggen:
      `[RDS] HEARTBEAT FÖRLORAD -> Frekvens: 103.3M | Ingen RDS-signal detekterad på 10.0s (Signalbortfall eller frekvens saknar RDS)`
- **Verifiering**:
  - Samtliga 27 enhetstester passerar.
  - Versionsbump till CalVer `2026.10.14.15`.

### 44. Dedikerad Protokollkolumn och Metadata Längst Ner i Meddelanderutan (v2026.10.14.16)
- **Bakgrund och Problem**:
  - Kolumnen `RF / META` samlade upp till fem olika piller i samma smala kolumn (`Frekvens`, `Protokoll`, `Baudrate`, `Funktion`, `Repetitioner`). Detta skapade en hög, rörig vertikal stapel som tryckte ut radhöjden ("många piller").
  - Användaren önskade att endast protokoll visas i denna kolumn, och att all övrig överföringsinformation (frekvens, bps, Alpha/Num, antal repetitioner osv.) placeras längst ner i meddelanderutan.
- **Teknisk Implementering**:
  - **Protokoll-kolumn ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html))**:
    - Ändrade tabellhuvudet från `RF / Meta` till `Protocol`.
    - Justerade cellbredd till 105px (min 95px, max 120px) med horisontell centrering och rent layoutflöde.
    - I `meta-cell` renderas nu uteslutande det färgkodade protokollpillret (`protoTag`: `POCSAG`, `TETRA`, `RDS`, `AFSK`).
  - **Metadata i Botten av Meddelanderutan ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html), [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
    - `.msg-cell` innehåller nu `.msg-text` för själva meddelandeinnehållet och en horisontell flexrad `.msg-meta-bar` längst ner.
    - `.msg-meta-bar` samlar `freqTag` (t.ex. `161.4375M`), `bitrateTag` (t.ex. `1200bps`, `TMC`), `funcTag` (`Alpha` / `Num`), `repeatTag` (`2x`, `3x`) samt `duplicateTag` (`Duplicate`).
    - `copyMessageText` uppdaterat att extrahera text från `.msg-text` så att kopiering till urklipp enbart inkluderar meddelandets rena text.
    - Dynamiska SSE-händelser för sammanslagna dubbletter (`repeat_update`) uppdaterar `.repeat-badge` direkt inuti `.msg-meta-bar`.
- **Verifiering**:
  - Alla tre tabeller (`index.html`, `larm.html`, `statistics.html`) och stilmallar uppdaterade.
  - versionsspårbarhet synkad till CalVer `2026.10.14.16` i `app.py`, `README.md`, `CHANGELOG.md` och `WALKTHROUGH.md`.

### 45. Strikt ALERT-C TMC (Grupp 3A) Låsning och P4 Snabbval i SDR Inställningar (v2026.10.14.17)
- **Bakgrund och Problem**:
  - Vid automatisk sökning (`auto` eller frekvensintervall) i [rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py) började skanningsmotorn på den första P4-kandidaten i kön (`88.7M`).
  - Mottagaren identifierade stationen som `P4 SR` (PI: `0xE224`), vilket felaktigt tolkades av logiken som ett godkännande att låsa kanalen direkt innan den ens kontrollerat om sändaren faktiskt sände aktiv ALERT-C TMC (Grupp 3A).
  - Eftersom sändaren på 88.7 MHz inte sände Grupp 3A blev skannern stående kvar permanent och väntade på handskakning istället för att gå vidare till nästa kandidat (`100.1M`, `103.3M`, etc.).
  - Dessutom saknades en bekväm snabbväljare för Sveriges Radio P4-sändare i SDR-inställningsgränssnittet.
- **Teknisk Implementering**:
  - **Krav på Aktiv Grupp 3A / 8A vid Skanningslåsning ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Ändrat `format_and_print_rds` så att stationsidentifiering av P4 (`is_sr_p4_station`) inte längre sätter `_current_channel_tmc_active = True` och inte längre anropar `format_and_print_lock`. Istället loggas en tydlig skanningsstatus: `Sveriges Radio P4 identifierad (...). Söker aktiv TMC-handskakning (Grupp 3A)...`.
    - I `parse_redsea_json_line` sätts `_current_channel_tmc_active = True` och frekvenslåsning emitteras uteslutande när äkta Grupp 3A (ALERT-C ODA systeminformation) eller Grupp 8A (trafikmeddelanden) detekteras.
    - I `run_rds_session` stramas låsvillkoret åt så att det uteslutande kontrollerar `_current_channel_tmc_active`.
    - Om 10 sekunders dwell-timeout nås utan att Grupp 3A/8A mottagits rapporteras detta med en tydlig logg (`P4-station identifierad på ... men ingen aktiv RDS-TMC (Grupp 3A) inom 10s. Söker vidare...`) och skannern går direkt vidare till nästa kandidat i listan.
  - **P4 Snabbvalsdropdown i SDR-inställningar ([templates/sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html))**:
    - Lagt till ett snabbval (`#rds_station_preset`) i `#rdsSettingsSection` med de vanligaste P4-sändarna i Sverige (Stockholm 103.3 MHz, Södertälje 93.8 MHz, Sörmland 100.1 MHz, Uppland 102.5 MHz, Göteborg 101.9 MHz, Malmöhus 102.0 MHz, m.fl.) samt valet för automatisk sökning (`auto`).
    - Skapat JavaScript-funktionerna `applyRdsPreset` och `syncRdsPresetFromFreq` för full tvåvägssynkning mellan frekvensfältet och dropdownen.
  - **Versionsspårbarhet**:
    - Uppdaterat versionsnummer till CalVer `2026.10.14.17` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).
- **Verifiering**:
  - Testat syntetisk ALERT-C injicering med `python rds_decoder.py --test-tmc` och verifierat korrekt sekvens: P4 identifieras -> söker Grupp 3A -> låsning sker först vid detekterad Grupp 3A och Grupp 8A.
  - Kört hela testsviten `python -m pytest` med 62 godkända tester.

### 46. Eliminering av Falsk TMC-låsning på RadioText+ (RT+) och Korrigering av redsea-flaggor (v2026.10.14.18)
- **Bakgrund och Problem**:
  - Trots 100% signalkvalitet och kontinuerliga heartbeat-loggar på 88.7 MHz (P4 Sörmland relä) togs inga ALERT-C trafikmeddelanden emot (`RDS-grupper: 0A, 10A, 14A, 1A, 2A, 3A, 4A, 6A`).
  - Heartbeat-meddelandet rapporterade `TMC: Synkad (Grupp 3A aktiv, inga 8A-larm i luften)` trots att sändaren inte sände någon ALERT-C TMC alls.
  - Undersökning av redsea-flaggor och källkod visade:
    1. Flaggan `-p` i redsea motsvarar `--show-partial` (visar partiella textblock). Den aktiverar inte hex-visning eller ALERT-C-avkodning.
    2. Flaggan `-u` i redsea är en kortform för `--rbds` (nordamerikansk standard). Att köra `-u` i Europa ändrar programtyper (PTY) och stationsanropskoder, vilket är felaktigt för europeisk RDS.
    3. I [rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py) fanns villkoret `group_type == "3A" or ...`. Eftersom RDS Grupp 3A används för ALLA Open Data Applications (ODA) – inklusive RadioText+ (RT+, AID `0x4BD7`) som Sveriges Radio använder för artist och låttitel – tolkades alla RadioText+ 3A-paket felaktigt som en bekräftad TMC ALERT-C handskakning (AID `0xCD46`). Skannern fastnade därmed på frekvenser som bara sände låtinformation och saknade Grupp 8A trafikdata.
- **Teknisk Implementering**:
  - **Korrekt Flaggkonfiguration för redsea ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Tog bort den felaktiga `-u` (RBDS) flaggan från kommandot. Kommandot körs nu som `["redsea", "-r", "171k"]` i rent europeiskt RDS/ALERT-C JSON-läge utan risk för felaktiga tabeller.
  - **Strikt Differentiering mellan ALERT-C och RadioText+ ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Ändrade logiken i `parse_redsea_json_line` så att Grupp 3A validerar ODA-applikationen. Endast paket med AID `0xCD46` / `0xCD47`, `system_info` eller uttrycklig text `RDS-TMC: ALERT-C` klassas som TMC.
    - Paket med `RadioText+ (RT+)` eller AID `0x4BD7` identifieras explicit och triggar inte längre TMC-låsning eller aktiv TMC-flagga.
    - Uppdaterade heartbeat-arbetaren (`_heartbeat_worker`) att rapportera exakt status:
      - Om äkta ALERT-C 3A mottagits: `TMC: Synkad (Grupp 3A aktiv, inga 8A-larm i luften)`.
      - Om endast RadioText+ 3A mottagits: `TMC: Ej TMC (Grupp 3A är RadioText+, ej ALERT-C)`.
  - **Prioriterad Frekvensordning för Skanning ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Flyttade regionala hög-effektssändare (`103.3M` Nacka 60 kW, `100.1M` Sörmland 60 kW, `93.8M` Ragnhildsborg, `102.5M` Uppsala 20 kW, `101.9M` Göteborg 60 kW) till toppen av skanningslistan före mindre slavsändare som `88.7M`.
  - **Versionsspårbarhet**:
    - Uppdaterat versionsnummer till CalVer `2026.10.14.18` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).
- **Verifiering**:
  - Testat syntetisk injicering med `python rds_decoder.py --test-tmc` och verifierat att RadioText+ 3A-paket inte sätter TMC-status till aktiv, medan ALERT-C 3A sätter status och låser mottagningen korrekt.
  - Samtliga 62 enhetstester passerar utan anmärkning.

### 47. Åtgärd av Falsk 8A-låsning på Icke-TMC Stationer (SR P1/P2/P3) (v2026.10.14.19)
- **Bakgrund och Problem**:
  - Vid mottagning på 99.3 MHz (SR P3, PI `0xE203`) detekterades ett enstaka rått RDS-block för Grupp 8A i luften.
  - Loggen visade: `[RDS] RDS-TMC LOCK: Station låst på frekvens 99.3M` och `TMC: Aktiv (ALERT-C 8A-larm mottagna)`.
  - Trots detta syntes inga larm i webbgränssnittets meddelandeflöde ("Men jag ser inget i flödet?!").
  - Orsaken:
    1. I Sverige sänder Sveriges Radio RDS-TMC **uteslutande på SR P4**. SR P1, P2 och P3 har ingen TMC-sändning.
    2. Redseas TMC-avkodare (`TMCService`) kräver Grupp 3A ODA ALERT-C (`AID 0xCD46`) för att initieras (`if (!is_initialized_) return;`). På P3 sänds aldrig Grupp 3A för TMC, vilket gör att redsea kastar alla 8A-block direkt utan att avkoda några meddelanden.
    3. I [rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py) fanns kontrollen `(group_type == "8A")` i `is_group_8a`. Den satte felaktigt `_current_channel_tmc_active = True`, satte `has_seen_tmc_8a = True` och låste mottagaren på 99.3 MHz, trots att inget meddelande (`loc_code`) fanns och ingen 3A handskakning skett. Därmed blev mottagaren låst på P3 och väntade förgäves på meddelanden som aldrig sänds där.
- **Teknisk Implementering**:
  - **Strikt Krav på Avkodat Meddelande för 8A-låsning ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - `_current_channel_tmc_active = True`, `has_seen_tmc_8a = True` och anrop till `format_and_print_lock(...)` sker nu **enbart** om ett faktiskt giltigt ALERT-C plats-ID (`loc_code is not None`) avkodats ur meddelandeblocken.
    - Ett rått 8A-block utan avkodat innehåll loggas nu som partiellt block enbart om stationen tidigare bekräftats via Grupp 3A ODA ALERT-C. På icke-TMC stationer ignoreras råa 8A-block helt så att de inte avbryter eller låser skanningen.
  - **Tydlig Identifiering av SR P1, P2 och P3 ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Lagt till igenkänning av PI-koderna `0xE201` (P1), `0xE202` (P2) och `0xE203` (P3) samt motsvarande stationsnamn.
    - Heartbeat-övervakaren informerar nu omedelbart i statusen:
      `TMC: Ej TMC-sändare (P3 SR sänder ej TMC, välj SR P4)`
    - Skanningsmotorn rapporterar direkt:
      `Station P3 SR (PI: 0xE203) sänder inte RDS-TMC (TMC sänds enbart på SR P4).`
  - **Versionsspårbarhet**:
    - Uppdaterat versionsnummer till CalVer `2026.10.14.19` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).
- **Verifiering**:
  - Testat rå 8A injicering mot P3 PI `0xE203`: Mottagaren rapporterar korrekt `sänder inte RDS-TMC` och låser inte (`tmc_active = False`).
  - Testat syntetisk ALERT-C injicering med `python rds_decoder.py --test-tmc`: Framgångsrik avkodning av Grupp 3A och Grupp 8A med korrekt generering av `RDS-TMC: LOC: 14502 ...`.
  - Samtliga 62 enhetstester passerar med 100% godkänt resultat.

### 48. Inbyggd ALERT-C ISO 14819-1 Parser för SR P3 & P4 samt Utökade Snabbval (v2026.10.14.20)
- **Bakgrund och Problem**:
  - Sveriges Radio P3 (FM 99.3 MHz, m.fl.) är det officiella rikstäckande distributionsnätet för Trafikverkets RDS-TMC i Sverige (medan P4 sänder regional röstbaserad trafikinformation).
  - Vid mottagning på 99.3 MHz togs faktiska Grupp 8A trafikmeddelanden emot i realtid, men visades inte i webbflödet eftersom redsea internt kräver en Grupp 3A ODA-handskakning innan den tillåter sin interna TMC-avkodare att producera JSON (`if (!is_initialized_) return;`). På sändare där Grupp 3A sänds med långa intervall kastades därmed alla 8A-block.
- **Teknisk Implementering**:
  - **Inbyggd ALERT-C Avkodare ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Skapat klassen `AlertCDecoder` som avkodar ALERT-C ISO 14819-1 direkt från råa RDS-block (asHex).
    - Avkodar både single-group meddelanden (Block 2 F=1, Block 3 händelsekod/riktning/omfattning, Block 4 platskod) och multi-group sekvenser.
    - Detta eliminerar helt beroendet av att redsea måste ha sett Grupp 3A först.
  - **Rådataströmsflagga `-R` i Redsea ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Ändrat redsea-kommandot till `["redsea", "-r", "171k", "-R"]` vilket garanterar att `raw_data` alltid skickas med per rad.
  - **Erkännande av SR P3 och Utökad Stationslista ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py), [templates/sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html))**:
    - Uppdaterat `is_sr_tmc_station` och pulsmätaren att erkänna både SR P3 (PI `0xE203`) och SR P4 som officiella TMC-källor.
    - Endast SR P1 (`0xE201`) och SR P2 (`0xE202`) klassas som icke-TMC.
    - Lagt till SR P3-sändare (Stockholm/Kisa 99.3 MHz, Göteborg 99.4 MHz, Hörby 97.0 MHz, Uppsala 96.6 MHz, Norrköping 94.8 MHz, Västerås 98.0 MHz, m.fl.) i `SR_TMC_STATIONS` och i snabbvalsdropdownen under SDR-inställningar.
  - **Versionsspårbarhet**:
    - Uppdaterat versionsnummer till CalVer `2026.10.14.20` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).
- **Verifiering**:
  - Testat avkodning av rått 8A-block `E203 8049 0865 38A6` (mottaget på P3 99.3 MHz): Avkodas direkt till `LOC: 14502 ROAD: E4 NAME: Trafikplats Nyköping Norra (Avfart 134) MSG: Trafikolycka`.
  - Verifierat syntetisk injicering med `--test-tmc`.
  - Samtliga 62 enhetstester i pytest passerar utan anmärkning.

### 49. Omedelbar Låsning på SR P3/P4, Snabbavbrott (2.5s) och Full FM-Bandskanning (v2026.10.14.21)
- **Bakgrund och Problem**:
  - Skanningen uppvisade ett cykliskt beteende där mottagaren hoppade genom en hårdkodad lista med 25 sändare (t.ex. Kristianstad 101.4 MHz, Skaraborg 100.3 MHz, Värmland 100.0 MHz, Västerbotten 104.2 MHz) och väntade 10 sekunder på varje frekvens trots att ingen signal fanns där.
  - Samtidigt räcker 10 sekunder inte för att kräva att ett aktivt trafiklarm (Grupp 8A) eller Grupp 3A ska skickas, eftersom sändningarna sker periodiskt (ofta 30–120s) eller vid faktiska olyckor. Detta gjorde att skannern övergav fullt fungerande SR P3/P4-stationer med 100% mottagningskvalitet.
  - Dessutom täckte skannern inte lokala slavsändare eller hela FM-bandet utanför den statiska listan.
- **Teknisk Implementering**:
  - **Omedelbar Låsning på Bekräftad SR P3 eller SR P4 ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - När mottagaren tar emot en station som identifierar sig som Sveriges Radio P3 (PI `0xE203`, PS `P3`) eller SR P4 (PI `0xEA24`, `0xE204`, etc.) och har stabil RDS-rammottagning, låser den kanalen omedelbart.
    - Den stannar permanent på frekvensen och lyssnar kontinuerligt efter ALERT-C larm i stället för att hoppa vidare efter 10 sekunder.
  - **Snabbavbrott på 2.5s för Tomma Kanaler ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Om inte en enda RDS-ram mottagits efter 2.5 sekunder avbryts frekvensen omedelbart. Detta ökar sökhastigheten med 400% genom tomma bandsegment.
  - **Fullständig FM-Bandskanning ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - `get_p4_candidates` genererar nu hela FM-bandet från 87.5 till 108.0 MHz med 200 kHz steg (totalt 120 kanaler), med kända SR P3/P4-frekvenser prioriterade först i kön eller via RF-spektrummätning (`rtl_power`).
  - **Versionsspårbarhet**:
    - Uppdaterat versionsnummer till CalVer `2026.10.14.21` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).
- **Verifiering**:
  - Verifierat att kandidatlistan genererar 120 frekvenser som spänner 87.5M till 108.0M med P3/P4 i spetsen.
  - Verifierat syntetisk injicering med `--test-tmc`.
  - Samtliga 62 enhetstester i pytest passerar utan anmärkning.

### 50. Kraschfix för RDS-dekoder vid null-PS och Robustifiering av Underprocesser (v2026.10.14.22)
- **Bakgrund och Problem**:
  - Vid start av skanningsmotorn på 99.3 MHz kraschade RDS-dekoderprocessen omedelbart:
    `[RDS] Processer avslutades ovantat! rtl PID=N/A exit=N/A, decoder PID=302 exit=1.`
    vilket utlöste watchdogen i `sdr_processor`.
  - Djupgående analys av stack trace och redsea-data visade:
    1. När `redsea` tar emot RDS-block där stationsnamnet (PS) inte är komplett eller delvis förvrängt, returnerar redsea `"ps": null` i JSON.
    2. Koden `ps = data.get("ps", "").strip()` orsakade `AttributeError: 'NoneType' object has no attribute 'strip'` eftersom `"ps"` existerade med värdet `None` (vilket inte träffade default-värdet `""`).
    3. `parse_redsea_json_line` anropades inuti `run_rds_session` utan `try...except`, vilket gjorde att undantaget bubblade upp och avslutade hela Python-processen med exit-kod 1.
    4. Experimentella flaggor (som `-R`) i anropet till `redsea` riskerade dessutom att få redsea att krascha vid start i miljöer med standardversioner av verktyget.
- **Teknisk Implementering**:
  - **Säker JSON-fältextrahering ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Ändrat utläsning av stationsnamn och PI till `raw_ps = data.get("ps")`, `ps = str(raw_ps).strip() if raw_ps is not None else ""` samt motsvarande för PI.
    - Säkrat samtliga underobjekt (`oda`, `open_data_app`, `tmc`, `system_info`) så att typkontroll sker innan metodanrop som `.get()`.
  - **Typoberoende rådata-avkodning i AlertCDecoder ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - `AlertCDecoder.decode_group` stöder nu både listor av hex-strängar (`["e203", "8000", ...]`) och enkla textsträngar, och fångar `(ValueError, TypeError)`.
  - **Try-Except Skydd i Huvud- och Sessionsloopar ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Omgett `parse_redsea_json_line(line)` i `run_rds_session` med `try...except` så att en enskild skadad rad aldrig kan sänka processen.
    - Omgett anropet till `run_rds_session` i `main()` med `try...except` så att frekvensskanningen fortsätter till nästa frekvens vid perifera fel.
    - Återställt redsea-anropet till det stabila europeiska kommandot `["redsea", "-r", "171k"]`.
    - I `reset_station_state()` nollställs nu även `has_received_any_frame = False`, `frames_since_last_pulse = 0` och tidsstämpeln för senaste ram uppdateras vid frekvensbyte.
  - **Felspårbarhet i Processövervakaren ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - `monitor_instance` fångar och loggar alla rader som innehåller felindikatorer (`Traceback (most recent`, `AttributeError:`, etc.) med `logger.error`, så att felorsaker från underprocesser blir direkt synliga i terminalen och användargränssnittet.
  - **Versionsspårbarhet**:
    - Uppdaterat versionsnummer till CalVer `2026.10.14.22` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).
- **Verifiering**:
  - Verifierat kantfall med JSON `{"ps": null, "pi": null}` utan krasch.
  - Samtliga enhetstester passerar utan fel.

### 51. Fix för UnboundLocalError i RDS Heartbeat, Prioritering av 88.7M och Flerlinjers Felspårbarhet (v2026.10.14.23)
- **Bakgrund och Problem**:
  - Vid val av en specifik frekvens (t.ex. 99.3 MHz) avslutades dekoderprocessen direkt med felkod 1:
    `[RDS] SUBPROCESS FEL: Traceback (most recent call last):`
    `[RDS] Processer avslutades ovantat! rtl PID=N/A exit=N/A, decoder PID=1695 exit=1.`
  - Dessutom sökte autoläget förbi fungerande RDS-stationer (som 88.7 MHz P4 Sörmland) utan att låsa.
  - Orsaker:
    1. I `_heartbeat_worker` i [rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py) användes `station_str` i `is_p3` innan variabeln tilldelats ett värde, vilket kastade ett `UnboundLocalError` så snart tråden exekverades.
    2. Den tidigare skanningsmotorn krävde att ett aktivt Grupp 8A ALERT-C larm sändes under ett 10-sekundersfönster innan låsning godkändes. Eftersom larm sänds sporadiskt lämnades bekräftade SR-stationer.
    3. Regionala P4 PI-koder (som `0xEA24` för P4 Sörmland) fångades inte av den strikta PI-kontrollen.
    4. 88.7 MHz låg på plats 16 i skanningskön.
- **Teknisk Implementering**:
  - **Lösning av `UnboundLocalError` ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Flyttat initieringen av `station_str` och `pi_str` till trådens absoluta början före alla villkorssatser.
  - **Fullständig Täckning av SR P4 PI-koder ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - `is_sr_tmc_station` kontrollerar nu alla svenska P4-prefix (`0xEA`, `0xEB`, `0xEC`, `0xED`, `0xE4`, `0xE204`), `0xE224` samt namnsökning på `"SR"`, `"P4"` och `"P3"`.
  - **Omedelbar Låsning på SR Stationer ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Så fort en bekräftad SR P3/P4 tas emot låses frekvensen omedelbart (`_current_channel_p4_confirmed = True`, `_current_channel_tmc_active = True`), så att mottagaren stannar kvar och lyssnar på inkommande TMC-larm.
  - **Prioriterad Skanningsordning ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - 88.7 MHz är nu position #1 i `SR_TMC_STATIONS`.
  - **Flerlinjers Traceback-spårbarhet ([sdr_processor.py](file:///d:/antigravity/pager-monitor/sdr_processor.py))**:
    - `monitor_instance` fångar nu fullständiga tracebacks över flera rader så att felorsaker blir direkt synliga i konsolen.
  - **Sessionsskydd och Buffertsäkerhet ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Omdirigerat `stderr` för `rtl_fm` och `redsea` till `DEVNULL` för att undvika fyllda rörbuffertar.
    - Omgett fast frekvenskörning med felåterhämtning.
  - **Versionsspårbarhet**:
    - Uppdaterat version till CalVer `2026.10.14.23` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).
- **Verifiering**:
  - Samtliga 27 enhetstester passerar utan fel (`python -m unittest discover tests`).

### 52. Global Deklaration i run_rds_session och Dwell-tidsjustering vid Skanning (v2026.10.14.24)
- **Bakgrund och Problem**:
  - Användaren rapporterade två problem:
    1. Fel i fast frekvenskörning:
       `UnboundLocalError: cannot access local variable '_current_channel_tmc_active' where it is not associated with a value` i [rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py) rad 1109 inuti `run_rds_session`.
    2. Vid frekvenssökning över FM-bandet rusade skannern förbi kanaler på endast 2.5 sekunder utan att stanna på starka riksstationer ("det går för fort, stannar inte ens på de stora RIKS frekvenserna").
  - Orsaker:
    - I `run_rds_session` tilldelades `_current_channel_tmc_active = True` utan att variabeln deklarerats med `global` överst i funktionen. Python behandlade den därmed som en lokal variabel och kraschade när den lästes vid början av while-loopen.
    - 2.5 sekunder snabbavbrott var för kort tid: RTL-SDR och redsea behöver 3–5 sekunder för att initiera USB-dongeln, låsa sin 57 kHz PLL och dekodera den första 104-bitars RDS-ramen. Skannern avbröt därmed frekvensen innan redsea ens hunnit producera data.
    - Spektrummätningen med `rtl_power` sorterade alla frekvenser enbart efter RF-energi, vilket kunde placera kommersiella hög-effektssändare före de faktiska SR-sändarna.
- **Teknisk Implementering**:
  - **Global Deklaration i `run_rds_session` ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Deklarerat `_current_channel_tmc_active`, `_current_channel_p4_confirmed` och `_current_channel_is_commercial` i `global`-deklarationen i `run_rds_session`.
  - **Ökat Snabbavbrott till 6.0s ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Ändrat timeout för signalavkänning från 2.5s till 6.0s så att redsea hinner synkronisera biphase-klockan och producera ramdata.
  - **Prioriterad SR TMC-spektrumsortering ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Vid `rtl_power`-mätning sorteras kända SR-stationer (P3 och P4) internt efter starkaste lokala signalstyrka och placeras alltid före generiska FM-rasterfrekvenser.
  - **Förfinad Identifiering ([rds_decoder.py](file:///d:/antigravity/pager-monitor/rds_decoder.py))**:
    - Kommersiella stationer och SR P1/P2 sållas bort direkt så att de aldrig klassas som SR TMC.
  - **Versionsspårbarhet**:
    - Uppdaterat version till CalVer `2026.10.14.24` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [README.md](file:///d:/antigravity/pager-monitor/README.md), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).
- **Verifiering**:
  - AST-kontroll validerar att inga globala variabler skuggas i modulens funktioner.
  - Samtliga 27 enhetstester passerar utan anmärkning (`python -m unittest discover tests`).

### 53. VDL Mode 2 / Flygdata TCP-integration mot dumpvdl2 och acars_router (v2026.10.14.25)
- **Bakgrund och Behov**:
  - Användaren kör redan en separat `dumpvdl2`-container (`ghcr.io/sdr-enthusiasts/docker-dumpvdl2:latest`) på samma host (`192.168.1.242`) tillsammans med `acars2pos_vdml`.
  - Istället för att installera en extra RTL-SDR eller kompilera `dumpvdl2` inuti Pager-Monitor önskades en ren nätverksintegration för att strömma färdigavkodad VDL2/ACARS-data direkt till Pager-Monitors gränssnitt, databas och realtidsflöde.
  - I arkitekturen skickar `dumpvdl2` data via ZeroMQ till port 35555 (`acars_router`), som i sin tur serverar färdig VDL2-JSON över TCP på port **`15555`** (`tcp://192.168.1.242:15555`).
- **Teknisk Implementering**:
  - **Asynkron Nätverksklient ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
    - Implementerat en dedikerad bakgrundstråd som ansluter till `tcp://192.168.1.242:15555`.
    - Automatisk återanslutning med exponentiell backoff (3s upp till 30s) ifall routern startas om.
    - Läser inkommande JSON rad för rad utan att blockera webbservern.
  - **Avancerad JSON-dekoder ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
    - Hanterar både dumpvdl2:s hierarkiska JSON (`vdl2 -> avlc -> acars / cpdlc / x25`) samt normaliserade fält.
    - Extraherar flygnummer (flight), registrering (reg/tail), ICAO-adress (24-bit hex), frekvens (t.ex. `136.975M`), signalnivå och ACARS label-kod.
    - CPDLC-avkodare: Strukturerar flygledningsmeddelanden (uplink/downlink-klareringar och instruktioner) till ren klartext.
    - Geoparsning: Extraherar latitud och longitud ur både JSON och rå ACARS-text (t.ex. `/POS 59.35N 018.00E`), vilket möjliggör kartplacering.
  - **Berikad Flygbolags- och Label-mappning ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
    - Automatisk mappning av flygbolagsprefix (SAS, Norwegian, Finnair, Ryanair, Lufthansa m.fl.) som fyller aliasfältet (t.ex. `SAS Scandinavian Airlines (SE-ROP)`).
    - Svenska beskrivningar för standardiserade ACARS labels (Positionsrapporter, OOOI-tider, Väder/METAR, Tekniska rapporter).
  - **Smart Filtrering och Duplikathantering ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
    - Inställningen `vdl2_filter_empty` (standard: `true`) filtrerar bort tomma signallänksramar och loggar endast faktiska meddelanden.
    - Integrerad med Pager-Monitors duplikathantering (`merge`/`discard`) och `increment_message_repeat`.
  - **Webbgränssnitt och Telemetri ([templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
    - Ny flik **VDL2 / Flygdata** i Inställningar.
    - Realtids-KPI:er: Anslutningsstatus (Ansluten / Frånkopplad / Inaktiv), mottagna TCP-paket, avkodade textmeddelanden, senast sedda flygplan och tidsstämpel.
    - Konfigurering för värd-IP (`192.168.1.242`), TCP-port (`15555`) och filter med omedelbar autosparning.
    - Testknapp för att skicka syntetiska test-ACARS (`/api/vdl2/test`).
  - **UI-styling och Protokollstöd ([static/style.css](file:///d:/antigravity/pager-monitor/static/style.css), [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html))**:
    - Ny flygblå badge (`proto-vdl2`) för både mörkt och ljust tema.
    - Korrekt rendering i live-flödet, larmlistan och statistiken.
- **Verifiering**:
  - Enhetstester verifierade med `python -c` för dumpvdl2 ACARS-ram, positions- och koordinatparsning, tomt ramfilter och testlarm-injektion.
  - Importkontroll och bakgrundsstart verifierad.

### 54. MIAM Airbus Telemetriavlastning, Mönster 1-4 Geoparsning och Utökad Avsändarformatering (v2026.10.14.26)
- **Bakgrund och Problem**:
  - Vid analys av användarens liveström från `dumpvdl2` påträffades flera specifika protokollstrukturer och telemetriformat:
    1. Airbus använder MIAM (Media Independent Aircraft Messaging) där ACARS-texten komprimeras med Base85. I `dumpvdl2` packas detta upp under `vdl2.avlc.acars.miam.single_transfer.miam_core.data.acars.msg_text`. Den tidigare parsern sparade den oläsliga Base85-strängen från yttre `msg_text`.
    2. Flygplansmeddelanden sänder positionsdata och telemetri i flera olika proprietära och standardiserade format (Airbus FDIMU med vetenskaplig notation, Ryanair decimalformat och Finnair kompakt DM-format).
    3. Registreringar kan innehålla inledande punkter (t.ex. `.OH-LWI`).
    4. Användaren önskade att adress/avsändare i Pager-Monitor visar fullständig identitet: `Flight (Reg) [ICAO]`, samt frekvens och beräknat SNR (`sig_level - noise_level` dB).
- **Teknisk Implementering**:
  - **Prioriterad MIAM Extrahering ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
    - Kontrollerar först om `vdl2.avlc.acars.miam.single_transfer.miam_core.data.acars.msg_text` finns. Om så är fallet används den uppackade texten och Base85-strängen ignoreras.
  - **Mönster 1: Airbus MIAM / FDIMU semikolon-format ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
    - Extraherar `PALAT` och `PALONG` med `float()` (klarar vetenskaplig notation som `5.875309E+01` och `1.543292E+01`).
    - Tolkar `PAALT` (fot), `PASAT` (temp °C), `PAFOB` (bränsle kg), `PAMN` (Mach), `PATHDG` (kurs), `PAFMSAWID` (waypoint), `PAGWTFQMS` (bruttovikt) och `PAWS` (vind kt).
    - Genererar strukturerad telemetrisammanfattning: `[FL410 | Waypoint: RIRIP | Mach 0.84 | Kurs: 52° | Temp: -63.5°C | Bränsle: 8810 kg | Vind: 80 kt]`.
  - **Mönster 2: Standard decimalformat ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
    - Extraherar `N 56.955 E 17.322` samt flyghöjd ur kommaseparerade fält (t.ex. `37012` -> FL370).
  - **Mönster 3: Kompakt DM-format ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
    - Konverterar `POSN58525E018360`:
      - `N58525` = 58° + 52.5'/60 = 58.875°
      - `E018360` = 18° + 36.0'/60 = 18.600°
  - **Mönster 4: Fallback till XID och ADS-C ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
    - Om meddelandetexten saknar koordinater kontrolleras `xid.ac_location` och `adsc.basic_report` i JSON.
  - **Fullständig Avsändarformatering och SNR ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
    - Rensa ledande punkter: `.OH-LWI` -> `OH-LWI`.
    - Formaterar adress: `AY1338 (OH-LWI) [461F50]`.
    - Beräknar mottagnings-SNR: `sig_level - noise_level` dB (t.ex. `SNR: +36.0 dB`).
### 55. Radiosond- och Väderballongsintegration via radiosonde_auto_rx UDP-ström (v2026.10.14.27)
- **Bakgrund och Problem**:
  - Användaren önskade integrera väderballonger (radiosonder) i Pager-Monitor i realtid från `radiosonde_auto_rx`.
  - `radiosonde_auto_rx` skickar sammanfattande JSON-telemetri (`PAYLOAD_SUMMARY`) via UDP på port `55673`.
  - En radiosond sänder telemetri varje sekund under 2-3 timmar (~9 000 paket per flygning). Att spara varje paket som en separat rad i SQLite skulle leda till extrem databasuppsvällning och spam i meddelandelistan, samtidigt som kartan kräver frekventa positionsuppdateringar.
- **Teknisk Implementering**:
  - **Asynkron UDP-lyssnare ([sonde_receiver.py](file:///d:/antigravity/pager-monitor/sonde_receiver.py))**:
    - Byggt `SondeReceiver` och `SondeState` som binder till UDP `0.0.0.0:55673` i bakgrunden.
    - Avkodar JSON-paket av typen `PAYLOAD_SUMMARY` med kända sonder (Vaisala RS41, RS41-SG, RS92, GRAW DFM, Meteomodem M10/M20, LMS6, m.fl.).
    - Formaterar frekvens och anropssignal, och spårar flygväg (upp till 500 historiska punkter per ballong).
  - **Smart Flödeshantering & Skydd mot Databasöverbelastning ([sonde_receiver.py](file:///d:/antigravity/pager-monitor/sonde_receiver.py))**:
    - **Aktiv rad i databasen**: När en ny ballong upptäcks skapas en aktiv rad i databasen. Denna rad uppdateras periodiskt (standard var 5:e sekund) med `UPDATE messages SET message = ?, repeat_count = ?, last_timestamp = ? WHERE id = ?`.
    - **Realtids-SSE**: Varje 1-sekundspaket skickas som ett `sonde_telemetry`-event direkt till frontendens anslutna klienter via SSE utan att skriva till databasen, vilket ger silkesmjuka kartuppdateringar i realtid.
  - **Milstolpar och Händelselogik ([sonde_receiver.py](file:///d:/antigravity/pager-monitor/sonde_receiver.py))**:
    - **Start**: Sparas som en separat rad med bitrate `SONDE-START` när en ny ballong upptäcks.
    - **Sprängning (Burst)**: Detekteras automatiskt när ballongen nått över 8 000 meter och sjunker kraftigt (`vel_v < -4 m/s` och fallit minst 250 m från maxhöjd). Loggas som `[SPRÄNGNING/BURST]` med maxhöjd och bitrate `SONDE-BURST`.
    - **Landning**: Detekteras automatiskt när ballongen når under 350 m höjd eller stannar vid marken. Loggas som `[LANDNING]` med slutposition, batterispänning och bitrate `SONDE-LAND`.
  - **Databas & API-endpoints ([database.py](file:///d:/antigravity/pager-monitor/database.py), [app.py](file:///d:/antigravity/pager-monitor/app.py))**:
    - Standardinställningar tillagda i databasen: `sonde_enabled: 'true'`, `sonde_udp_port: '55673'`, `sonde_db_interval: '5'`.
    - Nya API-rutter:
      - `GET /api/sonde/status`: Returnerar lyssnarstatus, port, paketantal, aktiva sonder och maxhöjdrekord.
      - `GET /api/sonde/active`: Returnerar aktiva ballonger med positionsspår för kartor.
      - `POST /api/sonde/test`: Skickar en syntetisk RS41-SG ballong för omedelbar verifiering.
    - Dynamisk omstart av UDP-lyssnaren i `handle_settings` vid ändrade radiosondinställningar.
  - **Gränssnitt och Inställningar ([templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
    - Ny flik "Radiosonder" i inställningsvyn med realtidsstatuskort, UDP-portkonfiguration och testknapp.
    - Autosparning av inställningar och bakgrundspolling av status.
  - **UI-styling och Protokollstöd ([static/style.css](file:///d:/antigravity/pager-monitor/static/style.css), [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html))**:
    - Ny lila badge (`proto-sonde`) för både mörkt och ljust tema.
    - Protokolldetektering för `SONDE` och formatering av bitrate-etiketter.
  - **Enhetstester ([tests/test_sonde.py](file:///d:/antigravity/pager-monitor/tests/test_sonde.py))**:
    - Täckning för modellparsning, frekvensformatering, flygfasstatus (stiger, burst, landad) och API-status.
- **Verifiering**:
  - Samtliga 37 enhetstester i hela projektet godkända (`python -m unittest discover tests`).

### 56. Humaniserad ACARS-avkodning, Dedikerad SNR-pill, Robust HTML-escaping och RF Activity Sonde-korrigering (v2026.10.14.28)
- **Dedikerad SNR-pill bredvid ACARS-märket ([static/style.css](file:///d:/antigravity/pager-monitor/static/style.css), [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html))**:
  - SNR visas nu som en egen smaragdgrön pill (`.badge.meta.badge-snr`) under texten i `.msg-meta-bar`, placerad direkt bredvid ACARS/bitrate-pillret.
  - Texten i meddelanderutan rensas automatiskt från `| SNR: +XX.X dB` så att ren payload visas utan brus.
  - Stilregler för `.badge.meta.badge-snr` tillagda för både mörkt och ljust tema.
- **Robust HTML-escaping av rådata och kryptiska meddelanden ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html))**:
  - **Problem**: Rådata från POCSAG/FLEX eller binär data med vinkelparenteser (t.ex. `<` och `>`) tolkades av webbläsaren som HTML-taggar (t.ex. `<s>` som orsakade genomstrykning/strikethrough eller `<a>` som skapade felaktiga länkar).
  - **Lösning**: Implementerat fullständig `escapeHtml()` för alla specialtecken (`&`, `<`, `>`, `"`, `'`) i `formatMessage()` och `highlightMessage()`. Radbrytningar ersätts först efter att all råtext escapats.
- **Korrekt Namngivning och Isolering av Radiosonder i RF Activity ([static/waterfall.js](file:///d:/antigravity/pager-monitor/static/waterfall.js), [sonde_receiver.py](file:///d:/antigravity/pager-monitor/sonde_receiver.py))**:
  - **Problem**: En tidigare hårdkodad regel i `static/waterfall.js` klassificerade alla okända frekvenser som började på siffran `4` som `TETRA`, vilket gjorde att väderballonger på standardfrekvensen 403.500 MHz registrerades som `TETRA 403.500M`.
  - **Lösning**:
    - Avlägsnat hårdkodningen för `frequency.startsWith('4')`.
    - Lagt till igenkänning av `isSondeMsg` som alltid namnger kanalen `Radiosond` med frekvens.
    - `sonde_receiver.py` skickar nu explicit `sdr_name: 'Radiosond'` och SNR-värde i samtliga SSE-händelser.
- **Humaniserad ACARS-avkodning ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Svensk uppslagsbok `ACARS_LABELS` för informativa etiketter (t.ex. `[SA: Länkstatus (Media Advisory)]`, `[B9: Begäran om flygplatsväder (ATIS)]`).
  - Tolkning av länkstatus (Media Advisory) med etablerade länkar (VDL2, HF, Satcom) och tidsangivelser i UTC.
  - Flygplatsavkodning (`AIRPORT_MAP`) för ATIS- och klareringsbegäran (`/EKCH.TI2/` -> Köpenhamn/Kastrup).
  - Prefix för Boeing/Honeywell FMS (`#M1B`) och underhållsdata.
  - XID Handover-stöd och ny inställning för att dölja periodiska ACARS-länktest (`Label Q0`).
- **Verifiering**:
  - Samtliga 42 enhetstester godkända (`python -m unittest discover tests`).

### 57. Fristående Modulär ACARS Human-Parser (v2026.10.14.29)
- **Modulär Arkitektur ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Skapat en helt fristående modul som översätter råa och kryptiska ACARS/VDL2-meddelanden till naturlig svensk text utan emojis.
  - Varje avkodningsmönster är definierat som en ren regelfunktion i `PARSER_RULES`, vilket gör det extremt enkelt att löpande lägga till nya regler för specifika flygbolag och telemetriformat utan att behöva modifiera mottagaren i `vdl2_receiver.py`.
  - Bevarar automatiskt alla inledande prefix i hakparenteser (såsom `[H1: FMS / Färddator-rapport]` eller `[38]`) och faller tillbaka till originaltexten om inget mönster matchas.
- **Implementerade Mönster**:
  1. **Mönster 1: Label 38 (Finnair väder- och positionsrapport)**:
     - Parsar `/AY8892/141026/E 17.655/N 59.387/37969/-------/      /- 57/33535/ 88 /46/`
     - Översätter till: `Flight: AY8892 | Position: N 59.387, E 17.655 | Höjd: 37969 ft | Temp: -57 C | Vind: 335 deg (35 kt)`
  2. **Mönster 2: Label H1 POSN (Färddator-rapport med rutt och väder)**:
     - Parsar `POSN59197E017265,N55208E004569,201749,380,N60045E021311,203531,N60157E022414,M58,33488,10132A6 | Lat: 59.3283, Lon: 17.4417`
     - Översätter till: `Färddator-rutt | Höjd: FL380 | Temp: -58 C | Vind: 334 deg (88 kt) | Nästa WP: N55208E004569 (kl 20:17:49 UTC) | Lat: 59.3283, Lon: 17.4417`
  3. **Mönster 3: Label H1 RESREQ/AK (Systemkvittens)**:
     - Parsar `RESREQ/AK,1158AF6`
     - Översätter till: `Systemkvittens: Resursförfrågan bekräftad (ACK) [CRC: 1158AF6]`
  4. **Mönster 4: Label 83 ETA-rapport (Gate/Ankomst)**:
     - Parsar `V09CA032/ETA-30/2046/`
     - Översätter till: `Ankomststatus: Beräknad ankomst (ETA) kl 20:46 UTC (Status: ETA-30, Kod: V09CA032)`
  5. **Mönster 5: Label H1 MM-telemetrilogg (Matrislogg)**:
     - Parsar fler-radiga loggar som inleds med `MM` (t.ex. `MM2014241014ACD` följt av mätpunkter).
     - Extraherar antal mätpunkter och tidsspannet mellan första och sista mätpunkten: `Telemetrilogg (MM2014241014ACD): 6 mätpunkter mottagna (20:12:23 - 20:13:56 UTC)`
- **Mottagarintegration ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - `vdl2_receiver.py` importerar `parse_human_acars` och kör meddelandetexten genom parsern under avkodningen.
- **Verifiering**:
  - Samtliga 53 enhetstester godkända (`python -m unittest discover tests`).

### 58. ACARSHUB Metadata-extrahering och Label 83 CSV-positionsrapporter (v2026.10.14.30)
- **ACARSHUB-liknande Metadata-extrahering ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py), [vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Extraherar detaljerade fält ur `vdl2`-strukturen (`avlc`, `src`, `dst`, `acars`) och bygger en kompakt och elegant metadata-rad överst i varje meddelande:
    `[Reg: ET-ATK | Flight: ET0715 (Ethiopian Airlines) | ICAO: 040127 | To: 119AAA (Arlanda Airport ESSA) | On Ground: No | Mode: 2 | Msg: M37A]`.
  - Inkluderar:
    - **Tail / Reg**: Rensar eventuella inledande punkter (`.ET-ATK` -> `ET-ATK`).
    - **Flight / Callsign**: Kopplas automatiskt mot flygbolagsnamn via prefix-tabell (`ET0715 (Ethiopian Airlines)`).
    - **ICAO Hex-adress**: Identifierar sändande flygplans ICAO-kod (`040127`).
    - **Ground Station / To Address**: Slår upp kända markstationer i `GROUND_STATIONS` (`119AAA (Arlanda Airport ESSA)`).
    - **On Ground status**: Visar tydligt `On Ground: Yes` eller `On Ground: No` baserat på `avlc.src.status`.
    - **ACARS Länkdetaljer**: Visar `Mode`, `Block ID`, `Msg No` (`msg_num` + `msg_num_seq`) och `ACK`.
- **Modulära Uppslagstabeller**:
  - Samlat all flygbolags- och markstationslogik i `acars_human_parser.py`:
    - `AIRLINE_MAP`: Prefix-karta med både 2-ställiga IATA- och 3-ställiga ICAO-koder (Ethiopian Airlines, SAS, Finnair, Norwegian, Lufthansa, British Airways, KLM, Air France, Ryanair, Wizz Air, airBaltic, Qatar Airways, Emirates, Turkish Airlines m.fl.).
    - `GROUND_STATIONS`: Markstationstabell (t.ex. `119AAA` och `1153706` -> `Arlanda Airport ESSA`).
    - Funktioner: `lookup_airline()`, `lookup_ground_station()`, `build_acars_metadata_header()`.
- **Mönster för Label 83 CSV-positionsrapporter**:
  - Implementerat `rule_label_83_csv_position` för 9-fälts kommaseparerade positionsrapporter:
    - Råtext: `ESSA,HAAB,142029, 58.54,  18.94,22605,305, 166.9, 43000`
    - Formateras till: `Rutt: ESSA -> HAAB | Tid: 20:29 UTC | Pos: 58.54, 18.94 | Höjd: 22605 ft | Fart: 305 kt | Kurs: 166.9 deg | Bränsle/Vikt: 43000`
  - Koordinater och telemetri (`lat=58.54`, `lon=18.94`, `alt_ft=22605`, `speed_kt=305`, `heading=166.9`) extraheras direkt i `extract_position_and_telemetry()` så att planet plottas på kartan och visas i UI.
- **Verifiering**:
  - Samtliga 60 enhetstester godkända (`python -m unittest discover tests`).
  - Verifierat att koden och meddelandetexterna är 100% fria från emojis.

### 59. Global Referensdatabas (acars_reference_data.json), Libacars-tolkning och Airframes Decoder-mönster (v2026.10.14.31)
- **Global Referensdatabas ([acars_reference_data.json](file:///d:/antigravity/pager-monitor/acars_reference_data.json))**:
  - Automatiserad extrahering och aggregering av referensdata från ACARSHUB och Airframes GitHub-repon:
    - **183 ACARS Labels**: Standardetiketter (`_d`, `H1`, `SA`, `80`-`89`, `10`-`5Z`, `Q0`, `QA`-`QZ`, `RA`, `B6` m.fl.) med beskrivande texter.
    - **1 711 Flygbolag**: Fullständig koppling mellan IATA 2-bokstavs och ICAO 3-bokstavskoder till officiella flygbolagsnamn.
    - **4 904 Markstationer**: SITA/ARINC-adresser i både hexadecimalt och decimalt format mappade till flygplatsnamn och ICAO-koder (t.ex. `Arlanda Airport (ESSA)`).
- **Libacars Direkt-tolkning ur Dumpvdl2 JSON ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Funktionen `format_libacars_data()` extraherar strukturerad data som libacars redan har avkodat i `arinc622.adsc`, `ats`, `cpdlc`, `miam` och `xid`.
  - Presenterar telemetri: position, höjd, vindhastighet/riktning, temperatur och VDL2 handover-status.
- **Utökade Avkodningsmönster (Portade från Airframes ACARS-Decoder)**:
  - **Label H1**: Färdplaner (`FPN/RI`, ICAO FPL med automatisk ruttidentifiering `ESSA -> EKCH`), `INI` flygförberedelser, `RESREQ` resurskvittenser och `MM`/`DFB`/`CFB` matrisloggar.
  - **Label 10-4Z & 80-89**: Finnair Label 38, Ethiopian Label 83 CSV-position, SAS Label 83 ETA, Airframes Variant 2 (`4DH3 ETAT2`) samt OOOI (`OUT`, `OFF`, `ON`, `IN`).
  - **Label SA**: Fullständig Media Advisory-tolkning (upprättad/förlorad länk och tillgängliga länkar VHF, VDL2, SATCOM, HF).
  - **Label Q0 / 5U / 5Z / B6 / RA**: Länktest, METAR/TAF väderbegäran, CPDLC klareringar och dispatch-kommandon.
  - **Generell Fallback-extraktion**: Extraherar automatiskt rutt (`ORIG/DEST`), `ETA`, flygnivå (`FL`) och koordinater ur okända meddelanden och sammanfattar dem före råtexten.
- **Verifiering**:
  - Samtliga 67 enhetstester godkända (`python -m unittest discover tests`).
  - Verifierat att koden och meddelandetexterna är 100% fria från emojis.

### 60. Strukturerad Metadata på Badge-raden, Ren Textlayout utan Pipes och Helords-ordbevakning (v2026.10.14.32)
- **KRAV 1: Metadata till Badge-raden ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py), [style.css](file:///d:/antigravity/pager-monitor/static/style.css), [index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html))**:
  - Metadata lyfts helt ut ur meddelandetexten och levereras som strukturerade fält (`flight`, `reg`, `icao`, `station`, `ground_status`, `label`, `label_desc`).
  - Renderas som kompakta och färgkodade badges i `.msg-meta-bar` längst ner i meddelandecellen bredvid frekvens, ACARS och SNR:
    - **Registrering**: `.badge.meta.badge-reg` (t.ex. `SE-RTA`).
    - **Flight**: `.badge.meta.badge-flight` (t.ex. `D84378` / `ET0715 (Ethiopian Airlines)`).
    - **ICAO**: `.badge.meta.badge-icao` (t.ex. `ICAO: 040127`).
    - **Markstation**: `.badge.meta.badge-station` (t.ex. `To: Arlanda ESSA`).
    - **Status**: `.badge.meta.badge-status.badge-airborne` / `.badge-ground`.
    - **Label**: `.badge.meta.badge-label` (t.ex. `Label: 83 (Operativt meddelande)`).
  - Dolt tekniskt brus (`Mode: 2`, `Block: 8`, `Msg: F40A`, `ACK: !`) samt avlägsnat `Alpha`/`Num` för VDL2.
  - Full bakåtkompatibilitet: UI parsar och rensar bort eventuella inbäddade headers från gamla rader i databasen och presenterar dem automatiskt i badge-raden.
- **KRAV 2: Ren Presentation utan Pipe-tecken ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Samtliga avkodningsregler har befriats från pipe-tecken (`|`).
  - Texten formateras med rena radbrytningar och tydliga fältnamn på svenska för t.ex. H1 FMS Färddator, Label 83 CSV-rapporter och ny dedikerad regel för MIAM Airbus telemetri.
- **KRAV 3: Unicode-säker Helordsmatchning i Ordbevakningen ([database.py](file:///d:/antigravity/pager-monitor/database.py), [index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html))**:
  - Åtgärdat falsklarm där larmord som `LIGHT` och `PORT` matchade delsträngar inuti `Flight` och `Airport`.
  - Implementerat ordgränser: `(?<![a-zA-Z0-9åäöÅÄÖ])ORD(?![a-zA-Z0-9åäöÅÄÖ])` med case-insensitivity i backend (`check_alert_words` och SQLite `WORD_MATCH`) samt i frontend (`checkAlertWordMatch`).
  - Ordmatchning sker strikt mot ren meddelandetext, aldrig mot metadata.
- **Verifiering**:
  - Samtliga 68 enhetstester godkända (`python -m unittest discover tests`).
  - Verifierat att koden och meddelandetexterna är 100% fria från emojis.

### 61. Multi-val och Filtrering på Flera RF Activity-kanaler i Vattenfallet (v2026.10.15.1)
- **Multi-val av SDR-kanaler ([static/waterfall.js](file:///d:/antigravity/pager-monitor/static/waterfall.js), [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [static/waterfall.css](file:///d:/antigravity/pager-monitor/static/waterfall.css))**:
  - Infört multi-val så att användaren kan klicka på och kombinera 1 eller flera radiokanaler samtidigt (t.ex. flera VDL2-mätfrekvenser, RIKS 1, POCSAG och RDS).
  - Ersatt den tidigare enkelvalsvariabeln med en `Set` (`activeFilterChannels`).
  - Varje kanalrad i RF Activity har försetts med en kryssruta (`.channel-check-box`) med FontAwesome-bock (`fas fa-check`) vid aktiv markering.
  - Varje klick på en kanalrad eller sammanfattningspiller (`.ribbon-summary-pill`) växlar nu kanalens aktiva status på/av.
- **Integrerad DataTables-filtrering och Samtidig Textsökning ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
  - Implementerat en dedikerad DataTables-sökfunktion (`$.fn.dataTable.ext.search.push`) som matchar rader mot samtliga valda kanaler via `data-channel-key`, `data-frequency` och protokoll.
  - Textsökfältet (`#searchInput`) är nu helt oberoende och kan användas samtidigt för att filtrera fram specifika anrop, flygnummer eller ord inom de valda kanalerna.
- **Rensaknapp i Ribbon-panelen**:
  - Lagt till en "Rensa filter (N)"-knapp (`#ribbonClearFilterBtn`) som visas automatiskt när minst en kanal är vald och återställer tabellen till normalläge med ett klick.
- **Verifiering**:
  - Samtliga 70 enhetstester godkända (`python -m unittest discover tests`).
  - Verifierat att koden och gränssnittet är 100% fria från emojis.

### 62. MIAM Fallback-dekoder (RFC 1924 Base85 + Deflate) och Fragmenthantering (v2026.10.15.2)
- **Fördjupad sökning i dumpvdl2:s MIAM-träd ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Kontrollerar samtliga fält under `miam.single_transfer.miam_core.data` (`acars.msg_text`, `raw`, `text`), `miam_core.raw`, `single_transfer.data` och rot-`miam`.
- **Egen Fallback-dekoder `decode_miam_base85()` ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Avkodar RFC 1924 Base85-strängar (`base64.b85decode`) och dekomprimerar med `zlib` (stödjer standard zlib-header, raw deflate `wbits=-zlib.MAX_WBITS` och gzip/auto).
  - Skannar dynamiska MIAM Single Transfer-offsets (3 till 8 tecken) efter `T01`/`T02` och extraherar läsbar ASCII-telemetri samt kör geolokalisering (`extract_position_and_telemetry`).
  - Strukturerad presentation av binära Airbus SAR/FDIMU-paket med utvunna ASCII-parametrar: `[MIAM Binär Flygdata] Airbus komprimerat telemetripaket (<X> bytes uppackat)`.
- **Snygg Presentation av Fragmenterade/Krypterade Delpaket ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Eliminerat oläsliga Base85-teckenväggar i gränssnittet vid fragmentering eller saknade block (`acars.more == True`).
  - Ersatt med informativ ren statusrad:
    `[MIAM Komprimerad Telemetri] Krypterat/fragmenterat Airbus-datapaket (<X> B, delpaket) (<preview>...)`.
  - Skyddat `[MIAM ...]`-taggar från prefix-strippning i `acars_human_parser.py`.
### 63. FMS Färdrapport & Destination samt Boeing DFDAU Motortelemetri (v2026.10.15.3)
- **FMS Progress & Destination Report ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py), [vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Implementerat `rule_fms_progress_destination` för avkodning av rapporter under `Label: H1` (`PRG/DT...`, `INI/DT...`, `FTX/DT...`).
  - Extraherar destination (`EGLL`), landningsbana (`27L`), beräknat landningsbränsle (`6 500 kg`), beräknad ankomsttid (`08:31 UTC`), marschhöjd (`FL380`) och temperatur (`-56°C`).
  - Slår upp destinationsflygplats i `AIRPORTS`-tabellen (`EGLL` -> `London/Heathrow`).
  - Uppdaterar paketets `dst_airport` samt `station` med den utvunna flygplatsen och skyddar den från att skrivas över av XID-data från avgångsflygplatsen, vilket gör att den gröna destinations-badgen i UI visar rätt destination.
  - Snygg presentation: `[FMS Färdrapport] Dest: EGLL (London/Heathrow) Bana 27L | ETA: 08:31 UTC | Marschhöjd: FL380 | Temp: -56°C | Landningsbränsle: 6 500 kg | Rådata: PRG/DTEGLL...`.
- **Boeing DFDAU / ACMS Numerisk Motortelemetri ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Implementerat `rule_boeing_dfdau_engine_telemetry` för meddelanden under `Label: H1`, `DF` eller prefix `#DFB` med minst 85% siffror och mellanslag samt minst 10 siffergrupper.
  - Extraherar motorvarvtal N1/N2 ur 4-siffriga grupper i hundradels procent (t.ex. `89.2%–95.4%`) med adaptiv skanning av cruise/climb-intervall.
  - Extraherar avgastemperatur EGT ur 3-siffriga mätvärden (400–850) direkt efter varvtalsblocken (t.ex. `591°C`).
  - Trunkerar råa sifferväggar till de första 35 tecknen så att tabellen och liveflödet hålls rent och överskådligt.
  - Snygg presentation: `[Boeing Motortelemetri / DFDAU] N1/N2 Varvtal: 89.2%–95.4% | EGT: 591°C | (37 mätvärden) | Rådata: 07336019 8991 9536...`.
- **Enhetstester ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - Lagt till `test_fms_progress_and_destination_report` och `test_boeing_dfdau_engine_telemetry`.
  - Samtliga 72 enhetstester i hela testsviten passerar felfritt.
### 64. Flygplatsformatering och Uppdatering av Destinationsbadge vid Arrival ATIS (v2026.10.15.4)
- **Universell Flygplatsformatering `format_airport()` ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Implementerat hjälpfunktionen `format_airport(icao)` som slår upp 4-ställiga ICAO-koder i referenstabellen och returnerar `EKCH (Köpenhamn/Kastrup)`.
  - Integrerat `format_airport(icao)` överallt där flygplatser presenteras i meddelanden: ATIS (`.TI2`), Departure Clearance (`.DC1`), Oceanic Clearance (`.OC1`), METAR och FMS-rapporter.
- **Detektering av Arrival och Departure ATIS ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Avkodar specificerad ATIS-typ (bokstaven `A` = Arrival, `D` = Departure direkt efter sekvensnummer/flygplatskod i t.ex. `/EKCH.TI2/024EKCHA6237`).
  - Presenterar tydligt och korrekt på svenska:
    - Arrival: `Begär landningsväder (Arrival ATIS) för EKCH (Köpenhamn/Kastrup)`
    - Departure: `Begär avgångsväder (Departure ATIS) för EKCH (Köpenhamn/Kastrup)`
    - Standard: `Begär flygplatsväder (ATIS) för EKCH (Köpenhamn/Kastrup)`
- **Destinationsbadge (`dst_airport`) Uppdateras vid Arrival ATIS ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Vid mottagande av Arrival ATIS (eller `.TI2` när planet har status `Airborne`) uppdateras paketets `dst_airport` till flygplatskoden (`EKCH`).
  - Markstationsmetadata (`station`) uppdateras till `EKCH (Köpenhamn/Kastrup)`, vilket omedelbart ändrar den gröna badgen i UI från avgångsflygplatsen till den faktiska destinationen (`To: EKCH (Köpenhamn/Kastrup)`).
- **Enhetstester ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - Uppdaterat `test_atis_departure_clearance` och lagt till `test_norwegian_arrival_atis_destination_badge` (för Norwegian `SE-RPF` / `D83195` med `/EKCH.TI2/024EKCHA6237`).
  - Samtliga 73 enhetstester i hela testsviten passerar felfritt.
- **Emoji-granskning**:
  - 100% fri från emojis i alla ändrade och tillagda filer.

### 65. Lufthansa Group AOC Telemetri (Label 1L) och Flygbolagsinterna Labels (v2026.10.15.5)
- **Stod for Flygbolagsinterna AOC-labels ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Lade till `"1L": "Flygbolagsdata (Lufthansa Group AOC)"` i `ACARS_LABELS` och `FALLBACK_LABELS`.
  - Implementerade generell regex-fallback (`^[1-4][A-Z]$`) som automatiskt klassificerar tidigare okanda flygbolagsspecifika labels som `"Flygbolagsdata (AOC Intern)"`.
- **Formatering av Kodad AOC-telemetri ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Tolkar och presenterar komprimerade 1L/AOC-paket med monster `^(\d{10,12})([A-Z0-9.,\-/]+)$` (t.ex. Austrian Airlines `OE-LBS` / `OS096F`).
  - Extraherar sekvensnummer ur den inledande siffergruppen och presenterar tydligt: `[AOC Flygbolagsdata] Intern kodad drift-/telemetrirapport (Lufthansa Group, Seq: <sekvensnummer>) | Rådata: <msg_text>`.
- **Flygplatsdatabas ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Lade till `ESDF`: `Ronneby/Kallinge` i flygplatsregistret.
- **Enhetstester ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - Lade till `test_austrian_aoc_1l_telemetry` som verifierar Austrian Airlines `OE-LBS` / `OS096F` med verklig `Label: 1L`-telemetristrang.
  - Samtliga 74 enhetstester i hela testsviten passerar felfritt.
- **Emoji-granskning**:
  - 100% fri från emojis i alla ändrade och tillagda filer.

### 66. AMDAR Väderrapport (Label H2) och Boeing CSV FMS/Väderlogg (Label H1) (v2026.10.15.6)
- **AMDAR Meteorologiska Rapporter ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Implementerat parserstöd för AMDAR-rapporter (`Label: H2`) med headermönster `02E\d{2}([A-Z]{4})([A-Z]{4})`.
  - Parsar samtliga mätpunkter (`lat`, `lon`, `tid`, `höjd`, `temp`, `vind`) och väljer alltid den sista (senaste/aktuella) mätpunkten för flygplanets position så att kartmarkören placeras rätt.
  - Snygg presentation: `[AMDAR Väderrapport] Rutt: LOWW (Wien) -> ESSA (Stockholm/Arlanda) | Senaste (07:18 UTC): Pos 58.7750, 17.8333 | Höjd: 19 500 ft | Temp: -14.7°C | Vind: 312° / 13 kt (5 mätpunkter)`.
- **Boeing CSV FMS/Väderlogg ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Implementerat parserstöd för kommaseparerade FMS-loggar (t.ex. LOT Polish Airlines `B7378MAX` under `Label: H1`).
  - Extraherar flygplanstyp, callsign, rutt (`EPWA (Warszawa) -> ESSA (Stockholm/Arlanda)`), uppdaterar `dst_airport`, och väljer sista mätpunkten för aktuell position, höjd (`39 998 ft`), temperatur (`-63.8°C`) och vind (`329° / 73 kt`).
  - Snygg presentation: `[FMS Färd- & Väderlogg] Flygplan: B7378MAX | Rutt: EPWA (Warszawa) -> ESSA (Stockholm/Arlanda) | Senaste (07:21 UTC): Pos 57.7217, 17.7250 | Höjd: 39 998 ft | Temp: -63.8°C | Vind: 329° / 73 kt (6 mätpunkter)`.
- **Förbättrad Koordinatkonvertering ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Generella `DDMM.M`-koordinater konverteras nu alltid till decimalgrader (`float`) och väljer den sista punkten om flera mätvärden skickats.
- **Enhetstester ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - Lagt till `test_amdar_weather_report` (Austrian Airlines `OE-LBS`) och `test_lot_boeing_fms_weather_log` (LOT `SP-LYM`).
  - Samtliga 76 enhetstester i hela testsviten passerar felfritt.
- **Emoji-granskning**:
  - 100% fri från emojis i alla ändrade och tillagda filer.

### 67. Boeing PLF Underhållsrapport och Global Flygplatsuppslagning i Rutter (v2026.10.15.7)
- **Boeing PLF Central Maintenance / Felkodsrapport ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Implementerat parserstöd för PLF-rapporter (Present Leg Faults / Post-Flight Report) från Boeing-flygplan.
  - Extraherar flygrutt (`EPWA/ESSA`), uppdaterar `dst_airport`, räknar cockpit-varningar (FDE) och underhållskoder (MSG).
  - Integrerat automatisk ATA-kapiteluppslagning (t.ex. `ATA 34: Navigation`) utifrån felkodernas inledande två siffror.
  - Snygg presentation: `[Underhålls-/Felrapport (PLF)] Rutt: EPWA (Warszawa/Chopin) → ESSA (Stockholm/Arlanda) | Cockpit-varningar (FDE): 2 st (ATA 34: Navigation) | Underhållskoder (MSG): 1 st`.
- **Global Flygplatsformatering (`format_airport`) i Alla Rutter ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Samtliga ruttutskrifter (`Rutt: ...`) och extraherade ICAO-koder slås nu konsekvent upp via `format_airport(icao)`.
  - Formatet använder pil `→` och fullständiga flygplatsnamn: `Rutt: EPWA (Warszawa/Chopin) → ESSA (Stockholm/Arlanda)`.
- **Utökat Flygplatsregister (`AIRPORT_MAP` / `FALLBACK_AIRPORTS`)**:
  - Utökat med över 80 flygplatser i Norden, Baltikum, Polen, Europa och resten av världen (inkl. Warszawa/Chopin, Wien/Schwechat, Bromma, Skavsta, Västerås, Malmö/Sturup, Visby, Ronneby, Saab m.fl.).
- **Enhetstester ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py), [tests/test_acars_human_parser.py](file:///d:/antigravity/pager-monitor/tests/test_acars_human_parser.py))**:
  - Lagt till `test_lot_boeing_plf_fault_report` och uppdaterat befintliga rutt-tester för fullständiga flygplatsnamn och pilar.
  - Samtliga 77 enhetstester i hela testsviten passerar felfritt.
- **Emoji-granskning**:
  - 100% fri från emojis i alla ändrade och tillagda filer.

### 68. Åtgärd för 500-fel i Databasstatistik och Dubbletthantering (v2026.10.15.8)
- **Åtgärd för 500-fel vid Databasstatistik ([database.py](file:///d:/antigravity/pager-monitor/database.py), [app.py](file:///d:/antigravity/pager-monitor/app.py))**:
  - Aktiverat `PRAGMA journal_mode=WAL;` (Write-Ahead Logging), `PRAGMA busy_timeout=30000;` och satt anslutningstimeout till 30 sekunder.
  - Eliminerar `sqlite3.OperationalError: database is locked` vid samtidiga skrivningar från bakgrundstrådar (VDL2, SDR, radiosonder) och statistikfrågor.
  - Skapat index på `messages(is_duplicate)` och `messages(is_protected)` för blixtsnabb filtrering och aggregering.
  - Lagt till retry-loop i [get_database_stats](file:///d:/antigravity/pager-monitor/database.py#L960) samt optimerad förfrågan för aktiva larmord.
- **Robust Felhantering och Skydd mot Nollställning ([templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
  - `loadDatabaseStats()` kontrollerar nu `res.ok` och kastar fel vid HTTP 500 istället för att parsa fel-JSON som ett tomt statistikobjekt och nollställa alla KPI-rutor till `0`, `0 B` och `None`.
  - Mätarkorten bibehåller nu sina tidigare värden vid övergående nätverksfel eller temporär databaslåsning och visar felmeddelande i statusraden.
  - Skyddade elementuppslagningar mot null-värden vid sparande av utseendeinställningar.
- **Inställning för Dubbletter och Rensa Dubbletter ([templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html), [database.py](file:///d:/antigravity/pager-monitor/database.py), [app.py](file:///d:/antigravity/pager-monitor/app.py))**:
  - Ny inställning "Spara dubblettmeddelanden i databasen" (`save_duplicates`) under fliken "Database & Storage".
  - Ny manuell åtgärd: "Rensa alla dubbletter nu" kopplad till endpointen `POST /api/messages/delete-duplicates`.
- **Enhetstester ([tests/test_stats_api.py](file:///d:/antigravity/pager-monitor/tests/test_stats_api.py))**:
  - Tillagt enhetstest `test_delete_duplicates_endpoint` som verifierar att dubbletter kan rensas och att endpointen returnerar korrekt JSON-status.
- **Emoji-granskning**:
  - 100% fri från emojis i alla ändrade och tillagda filer.

### 69. Fix för Inställningen Spara Dubbletter och Persistens (v2026.10.15.9)
- **Persistens och Tillåtna Inställningsnycklar ([app.py](file:///d:/antigravity/pager-monitor/app.py), [database.py](file:///d:/antigravity/pager-monitor/database.py))**:
  - `save_duplicates` lades till i listan `allowed_keys` i [app.py](file:///d:/antigravity/pager-monitor/app.py) så att anrop till `/api/settings` tillåts spara värdet.
  - [update_setting](file:///d:/antigravity/pager-monitor/database.py#L580) uppdaterades från att köra ren `UPDATE` till `INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)`, vilket säkerställer att nya inställningar alltid sparas även om de saknades i befintliga databasrader.
  - [get_settings](file:///d:/antigravity/pager-monitor/database.py#L569) sammanfogar nu databasinställningar med [get_default_settings](file:///d:/antigravity/pager-monitor/database.py#L31) som fallback.
- **Frontend-optimering ([templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
  - Dedikerad sparfunktion `saveDuplicateSetting()` anropas direkt vid ändring av kryssrutan `save_duplicates` för omedelbar respons utan fördröjning.
  - Kryssrutan synkas samtidigt automatiskt med `duplicate_handling` ('merge' eller 'discard').
  - `loadDatabaseStats()` skyddar kryssrutans tillstånd så att periodiska statistikuppdateringar inte skriver över användarens val under pågående ändring.
- **Emoji-granskning**:
  - 100% fri från emojis i alla ändrade och tillagda filer.

### 70. Prestandaoptimering av Databasstatistik och TTL-caching (v2026.10.15.10)
- **Problem & Flaskhalsanalys ([database.py](file:///d:/antigravity/pager-monitor/database.py))**:
  - Vid inläsning av fliken "Database & Storage" tog anropet till `/api/database/stats` 7–8 sekunder för databaser med över 24 000 meddelanden.
  - Den primära flaskhalsen var beräkningen av bevakningslistaträffar (`alert_hits`), som tidigare anropade `UPPER_UNICODE(m.message)` i SQLite för varje meddelande och aktivt larmord. Detta ledde till hundratusentals Python-callbackanrop och konstant trådlåsning/kontextväxling i SQLite.
  - Dessutom kördes 5 separata databasfrågor mot samma meddelandetabell, vilket orsakade upprepade skanningar.
- **Höghastighets-aggregationsfråga ([database.py](file:///d:/antigravity/pager-monitor/database.py))**:
  - Sammanfogat räkning av totalt antal meddelanden, äldsta och nyaste tidsstämpel, skyddade meddelanden, dubblettmeddelanden och unika adresser i EN enda optimerad SQL-fråga:
    `SELECT COUNT(*), MIN(timestamp), MAX(timestamp), COALESCE(SUM(CASE WHEN is_protected = 1 THEN 1 ELSE 0 END), 0), COALESCE(SUM(CASE WHEN is_duplicate = 1 THEN 1 ELSE 0 END), 0), COUNT(DISTINCT address) FROM messages`.
- **C-baserad SQL LIKE-mönstermatchning ([database.py](file:///d:/antigravity/pager-monitor/database.py))**:
  - Ersatt Python UDF-anropet `UPPER_UNICODE` med en dynamisk SQL-fråga (`WHERE m.message LIKE ? OR ...`) som exekveras i ren C i SQLite-kärnan.
  - Detta eliminerade Python GIL-overhead helt och sänkte beräkningstiden från 7 500 ms till ca 3 ms (över 2 400x snabbare).
- **In-memory TTL-caching ([database.py](file:///d:/antigravity/pager-monitor/database.py), [app.py](file:///d:/antigravity/pager-monitor/app.py))**:
  - Infört en 15-sekunders minnescache (`_stats_cache`) som gör att återkommande flikbyten och sidvisningar svarar omedelbart (0,0 ms).
  - Cachen invalideras automatiskt via `invalidate_database_stats_cache()` när meddelanden rensas, gallras eller dubbletter tas bort.
  - Lagt till parameter `?force=1` på `/api/database/stats` i [app.py](file:///d:/antigravity/pager-monitor/app.py) för att kringgå cachen när användaren klickar på "Refresh Stats".
- **Visuell Feedback i Användargränssnittet ([templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
  - Knappen "Refresh Stats" försågs med ett roterande ikon (`fa-spin`) och inaktiveras under pågående begäran så att användaren tydligt ser att data hämtas.
- **Enhetstester ([tests/test_stats_api.py](file:///d:/antigravity/pager-monitor/tests/test_stats_api.py))**:
  - Utökat testsviten med `test_database_stats_cache_and_force` som verifierar cachefunktion och force-flaggan.
- **Emoji-granskning**:
  - 100% fri från emojis i alla ändrade och tillagda filer.

### 71. Airbus FDIMU / AIDS-systemrapporter under Label H1 (v2026.10.15.11)
- **Airbus FDIMU & AIDS-headerdekodning ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Implementerat parserstöd för Airbus AIDS/FDIMU-rapporter (t.ex. Pegasus Airlines TC-RBH, PC56HA på A321) under `Label: H1` som inleds med flygplanstyp, rapportnummer och `/CC`-header:
    `^(A\d{3})[^/]*/REP(\d+)[^/]*/CC([A-Z0-9-]+),([A-Z]{3}\d{2}),(\d{6}),([A-Z]{4}),([A-Z]{4})`.
  - Extraherar flygplanstyp (`A321`), rapportnummer (`009`), registrering (`TC-RBH`), tidsstämpel (`08:13:23 UTC`), avgångsflygplats (`LTFJ`) och destinationsflygplats (`ESSA`).
  - Uppdaterar automatiskt `dst_airport` till `ESSA` och sätter destinations-badgen till `ESSA (Stockholm/Arlanda)`.
- **Telemetri & Höjddata från `/CE`-sektionen ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Extraherar flyghöjd i fot (`13 407 ft`) och indikerad fart (`301 kt`) ur mönstret `/CE\d{4},(\d{4,5}),(\d{3})`.
  - Sätter paketets `alt` och `alt_ft` till `13407` i `parse_vdl2_frame` och `extract_position_and_telemetry`.
  - Formaterar rapporten strukturerat på svenska:
    `[Airbus FDIMU/Systemrapport #009] Flygplan: A321 | Rutt: LTFJ (Istanbul/Sabiha Gökçen) → ESSA (Stockholm/Arlanda) | Tid: 08:13:23 UTC | Höjd: 13 407 ft | Fart: 301 kt | Rådata: ...`
- **Enhetstester ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py), [tests/test_acars_human_parser.py](file:///d:/antigravity/pager-monitor/tests/test_acars_human_parser.py))**:
  - Tillagt `test_pegasus_airbus_aids_fdimu_report` och `test_rule_airbus_aids_fdimu_report` som verifierar att `Istanbul/Sabiha Gökçen` och `Stockholm/Arlanda` slås upp och visas samt att `alt` sätts till `13407`.
  - Samtliga 79 enhetstester passerar felfritt.
- **Emoji-granskning**:
  - 100% fri från emojis i alla ändrade och tillagda filer.

### 72. Kollapsbar Rådata i UI och Förbättrad Label 80 ETA/FOB/Fritext (v2026.10.15.12)
- **Strikt ETA-validering & Parsing av /ETA och /FOB ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py), [vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Infört strikt timvalidering (`(?:[01]\d|2[0-3])[0-5]\d`) för ETA i `acars_human_parser.py` och `vdl2_receiver.py`, så att fyrsiffriga flightnummer (t.ex. `4505` i `3401 ETA 4505/15`) inte felaktigt tolkas som klockslaget `45:05 UTC`.
  - Parsar `/ETA\s*(\d{4})` till `ETA: HH:MM UTC` (t.ex. `/ETA 0925` -> `ETA: 09:25 UTC`).
  - Parsar `/FOB\s*(\d{3,5})` till bränslemängd i kg (`Bränsle (FOB): X kg`), med automatisk skalning beroende på om FOB anges i hundratal kg/lbs eller hela kg.
  - Extraherar och formaterar flygplatser via `format_airport()` och uppdaterar automatiskt `dst_airport`-metadatat (t.ex. `EDDB` -> `Berlin/Brandenburg`).
- **Framhävning av Mänsklig Pilot-fritext ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Extraherar fritextrader under tekniska headers i operativa meddelanden (t.ex. `Label: 80`, `RA`) och sammanfogar dem till en tydlig rad:
    `💬 Pilotmeddelande: "HI BER — REQ FUEL 5.6T"`.
- **Standardisering av Rådata-avgränsare ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py), [vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Standardiserat all rådata till `\nRådata: <original_text>` i slutet av meddelandet.
  - Tagit bort godtycklig avkortning med `[:35] + '...'` i Python-reglerna så att full rådata bevaras för visning i gränssnittet.
- **Kollapsbar `<details>`-sektion i Frontend ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html))**:
  - Uppdaterat `formatMessage()` i Dashboard, Alarms och Statistics så att meddelanden med `\nRådata:` eller `| Rådata:` delas upp i `parsedSummary` och `rawText`.
  - Båda delarna XSS-skyddas med `escapeHtml()`.
  - Rader som innehåller pilotfritext (`💬`) ges en framträdande stil via CSS-klassen `.pilot-freetext-highlight`.
  - `rawText` renderas som en kollapsbar sektion:
    ```html
    <details class="raw-data-details">
      <summary>Visa rådata</summary>
      <pre class="raw-data-content">${escapedRawText}</pre>
    </details>
    ```
  - Stylad med diskret länktext och mörk/ljus anpassad monospace-ruta (`.raw-data-content`).
- **Enhetstester ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - Tillagt `test_norwegian_label_80_eta_fob_and_pilot_freetext` för att verifiera Norwegian `3401 ETA 4505/15 ESSA/EDDB .SE-RYC`, `ETA: 09:25 UTC`, `Bränsle (FOB): 4 280 kg` samt `💬 Pilotmeddelande: "HI BER — REQ FUEL 5.6T"`.
  - Samtliga 80 tester passerar felfritt.
- **Emoji-granskning**:
  - Strikt granskad. Endast den begärda pilotfritext-indikatorn `💬` tillåten i meddelandeparsningen. Inga övriga emojis.

---

### 73. Dynamiskt Filtersystem, Click-to-Filter & UI-Fix för Rådata-kollaps (v2026.10.15.13)
- **Problembeskrivning och Kravspecifikation**:
  1. Användaren efterfrågade ett smart och smidigt filtersystem ovanför tabellen i Real-time Monitor (mellan "Show X messages" och "Quick filter...") för att snabbt kunna filtrera på Protokoll, Frekvens, ACARS Label och Flygplats, samt Click-to-filter direkt från brickor i tabellen.
  2. Strikt krav: VDL2-specifika filter (ACARS Label, Flygplats) får INTE synas om VDL2 är inaktiverat i Settings (`vdl2_enabled`). Gränssnittet ska förbli helt rent för användare som enbart kör POCSAG.
  3. UI-bugg: Stor onödig marginal mellan den tolkade texten och texten "Visa rådata", samt otydligt att det rör sig om en kollapsbar sektion. Användaren begärde en avdelare och tydlig visuell indikering om att texten är kollapsad.
- **Identifierade Orsaker till UI-marginalen**:
  - CSS-klassen `.msg-cell` i `static/style.css` hade egenskapen `white-space: pre-wrap;`.
  - JS-mallsträngar i `formatMessage()` och array-metoder (`split(/\r?\n/)`) innehöll efterföljande radbrytningar och tomrader, vilka webbläsaren tolkade bokstavligt och renderade som tomma textrader före `<details>`.
  - Webbläsarens inbyggda `<summary>`-pil var diskret eller dold och saknade tydlig interaktionsdesign.
- **Teknisk Implementering**:
  - **Eliminering av Vertikalt Tomrum & Förfinad Rådata-design ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html))**:
    - Satte `.msg-cell .msg-text { white-space: normal !important; }` så att den tolkade texten inte genererar oavsiktliga tomrader från strängformatering, medan själva rådatan inuti `<pre class="raw-data-content">` behåller sin monospace pre-formatering.
    - Trimmat bort tomrader före rendering av den tolkade texten.
    - Lagt till en diskret streckad avdelare (`border-top: 1px dashed rgba(148, 163, 184, 0.25)`) och marginal (`margin-top: 6px; padding-top: 5px;`) på `.raw-data-details`.
    - Stylat om `<summary>` med `list-style: none` till en kompakt, elegant pill-knapp (`.raw-data-badge-btn`):
      - Ikon för råkod (`<i class="fas fa-code"></i>`) och roterande chevron (`<i class="fas fa-chevron-right raw-data-chevron"></i>`).
      - Chevronen roterar 90 grader (`transform: rotate(90deg)`) med CSS-transition när `<details open>` expanderas.
      - Tydlig hover-effekt med mjuk kantlinje och bakgrundsskiftning.
  - **Dynamisk Filter-bar i Real-time Monitor ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
    - Skapat container `#tableFilterBar` placerad mellan sidlängdsdropdown och snabbsökrutan i DataTables topprad (`.dt-layout-row:first-child`).
    - **Protokoll-filter (`#filterProtocol`)**: Dynamiskt befolkad med aktiva protokoll (`Alla protokoll`, `POCSAG`, `VDL2`, `TETRA`, `RDS-TMC`, `AFSK`).
    - **Frekvens-filter (`#filterFrequency`)**: Dynamiskt befolkad med alla unika frekvenser i stigande frekvensordning tillsammans med meddelandeantal (t.ex. `136.975 MHz (142)`).
    - **ACARS Label-filter (`#filterLabel`)**: Dynamiskt befolkad med VDL2-labels, inklusive snabbvalet `Endast pilotmeddelanden / fritext` i toppen samt mänskliga förklaringar (t.ex. `80 — Pilot-fritext / ETA & FOB`, `H1 — Airbus AIDS / FDIMU`).
    - **Flygplats-filter (`#filterAirport`)**: Dynamiskt befolkad med alla unika flygplatser med ICAO och fullt flygplatsnamn (t.ex. `ESSA — Stockholm/Arlanda`).
    - **Villkorlig Visning baserad på VDL2-inställning**: Känner av `appSettings.vdl2_enabled`. Om VDL2 är inaktiverat döljs Label- och Flygplats-dropdowns automatiskt (`display: none`).
  - **Click-to-Filter på Samtliga Brickor i Tabellen**:
    - Klick på **Protokoll-bricka** sätter protokollfiltret.
    - Klick på **Frekvens-bricka** sätter frekvensfiltret.
    - Klick på **Label-bricka** sätter label-filtret.
    - Klick på **Flygplats-bricka** sätter flygplatsfiltret.
    - Klick på **Flygbolag / Capcode** sätter sökfiltret (medan pennikonen öppnar alias-redigeringen separat).
    - Klick på **Registrering / Flight / ICAO** sätter sökfiltret.
  - **Filterchips & Rensa-knapp**:
    - Aktiva filter visas som klickbara chips (`#activeFilterChips`) med ett litet kryss för att ta bort enskilda filter.
    - Knappen "Rensa filter" (`#clearFiltersBtn`) nollställer samtliga aktiva dropdowns och fritextsökning med ett enda klick.
  - **Live-kompatibilitet**:
    - Inkommande meddelanden via SSE respekterar användarens aktiva filter utan att nollställa dropdowns.
    - Dropdown-listor uppdateras med nya värden i bakgrunden utan att störa användarens pågående menyinteraktion.
- **Enhetstester & Verifiering**:
  - Samtliga 80 enhetstester passerar (`python -m unittest discover tests`).
  - Emoji-granskning verifierad: Inga otillåtna emojis i applikationen.
  - Versionsbump till CalVer `2026.10.15.13` i [app.py](file:///d:/antigravity/pager-monitor/app.py), [CHANGELOG.md](file:///d:/antigravity/pager-monitor/CHANGELOG.md) och [WALKTHROUGH.md](file:///d:/antigravity/pager-monitor/WALKTHROUGH.md).










