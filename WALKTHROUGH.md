# Walkthrough: PagerMonitor Development and Features

## Version Information
- **CalVer**: `2026.10.12.15`
- **Date**: 2026-10-12
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





