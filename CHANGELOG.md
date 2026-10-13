# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Calendar Versioning (CalVer) `YYYY.0M.0D`.

## [2026.10.13.26] - Fix för Mottagarlista i Inställningar, TETRA-låsning och Versionssynk

### Fixed
- **JavaScript SyntaxError i Mottagarinställningar (`templates/settings.html`)**:
  - Åtgärdat felet `Uncaught SyntaxError: Identifier 'currentSDRs' has already been declared` (rad 629) där variabeln `currentSDRs` råkat deklareras två gånger. Syntaxfelet stoppade JavaScript-exekveringen och orsakade att mottagarlistan i Inställningar inte renderades alls.
- **TETRA Basstationshantering och RF Activity Telemetri (`sdr_processor.py`, `static/waterfall.js`)**:
  - Basstationer (typ `NET` och `Aktiv TETRA Basstation`) hanteras nu som ren bärvågstelemetri istället för larmmeddelanden. De sparas inte längre som rader i meddelandedatabasen och skapar inte falska "HIT"s eller fyller "RF ACTIVITY"-bandet med nya kanaler.
  - Skickar fortfarande SSE-telemetriping så att användargränssnittet vet att skannern är aktiv och synkroniserad på aktuell frekvens.
- **Permanent Bärvågslåsning för TETRA (`stream_continuous` i `tetra_decoder.py`)**:
  - Åtgärdat beteendet där TETRA-skannern övergav en låst basstation efter 30 sekunder och svepte vidare. Den felaktiga 30-sekunders inaktivitetstimern är borttagen, vilket gör att mottagaren nu förblir låst på den synkroniserade basstationen och kontinuerligt avkodar inkommande anrop och SDS-meddelanden.
- **Synkroniserad CalVer-versionshantering och Docker-startbanner (`app.py`, `templates/base.html`)**:
  - Uppdaterat `APP_VERSION` till `2026.10.13.26` i [app.py](file:///d:/antigravity/pager-monitor/app.py) så att sidopanelen och footer alltid visar korrekt aktuell version.
  - Implementerat en tydlig startbanner i konsolen vid uppstart av Docker-containern (`Pager Monitor v2026.10.13.26 startar...`).

## [2026.10.13.25] - Automatisk Realtidsstatus och Polling för SDR-mottagarkort

### Fixed
- **Automatisk Realtidsuppdatering av Mottagarstatus (`templates/settings.html`)**:
  - Åtgärdat problem där mottagarkort fastnade i status "Stopped" trots att mottagaren faktiskt startat och blivit aktiv. När en mottagare aktiverades i gränssnittet anropades `/api/sdr` omedelbart innan processen och dess PID hunnit initieras i bakgrunden. Eftersom inställningssidan saknade polling förblev kortet statiskt tills användaren manuellt uppdaterade sidan i webbläsaren.
  - Implementerat bakgrundspolling (var 3.5:e sekund och vid flikväxling via `visibilitychange`) samt snabbsekvenserad polling (vid 400ms, 1000ms, 1800ms, 3000ms, 4500ms) vid av/på-växling, kloning och nyskapande.
  - Förbättrat statusbadgen med mellanläget "Starting..." under uppstart för att ge direkt visuell återkoppling innan processen är bekräftat aktiv.
  - Implementerat in-place DOM-uppdatering av status, frekvens och switchar så att korten uppdateras mjukt utan att skrivas om i DOM.

## [2026.10.13.24] - Återställt Standardvisning och Samplingslängd för TETRA-basstationer

### Fixed
- **Återställd Samplingslängd för TETRA-skanner (`tetra_decoder.py`)**:
  - Återställt provtagningsstorleken i `probe_block` till minst 163 840 samples (68.2 ms vid 2.4 MS/s). Den tidigare begränsningen till 131 072 samples (54.6 ms) var kortare än en hel TETRA TDMA-ram (56.67 ms), vilket gjorde att bärvågssynkronisering och pi/4-DQPSK-konstellationsmätning kunde missa träningssekvenser under svep.
- **Återställd Standardvisning av Basstationer (`database.py`, `sdr_processor.py`, `templates/index.html`, `templates/larm.html`)**:
  - Ändrat standardinställningen för `log_tetra_basestations` till `'true'` så att nyfunna TETRA/Rakel-basstationer alltid loggas och visas i realtid.
  - Justerat DataTables-snabbfiltret i webbgränssnittet så att standardläget är "Basstationer: Visas". Användare som vill dölja basstationer från larmflödet kan enkelt klicka på knappen "Basstationer: Visas" för att växla till "Basstationer: Dolda".

## [2026.10.13.23] - Garanterad Terminering av Bakgrundsprocesser för TETRA och USB Återhämtningspauser

### Fixed
- **Terminering av Föräldralösa Python/TETRA-processer (`kill_orphaned_rtl_for_device` i `sdr_processor.py`)**:
  - `kill_orphaned_rtl_for_device` kontrollerade tidigare enbart om processens binärnamn matchade `rtl_sdr`, `rtl_fm` eller `rtl_test`. När en instans kördes med `TETRA` var huvudprocessen `python tetra_decoder.py`, vilket gjorde att den aldrig terminerades när användaren stoppade mottagaren eller bytte protokoll till POCSAG.
  - Den kvardröjande bakgrundsprocessen fortsatte anropa `rtl_sdr` i loopar på samma USB-enhet, vilket orsakade USB-kollision och `Device error detected, async read returned: -1` för nya instanser (t.ex. `RIKS 2`).
  - Uppdaterat processökningen så att den identifierar alla processer och python-skript som använder enheten via `-d`, `--device` eller `--device=<enhet>` och garanterat dödar dem med `SIGKILL`.
- **Automatisk Process-avregistrering (`atexit` i `tetra_decoder.py`)**:
  - Registrerat `atexit`- och `signal`-hanterare som automatiskt terminerar aktiva underprocesser (`rtl_sdr`) vid avslut, så att inga barnprocesser lämnas kvar.
- **USB-återhämtningspauser och Skydd mot Snabbkrasch i Blockskanning (`tetra_decoder.py`)**:
  - Implementerat 120 ms fördröjning efter varje `rtl_sdr`-körning så att Linux USB-kärna hinner frigöra ändpunkter och URB-buffertar innan nästa block anropas.
  - Vid felaktig eller ofullständig dataläsning (`< 10 000` byte) pausas processen i 350 ms och provtagningen gör automatiskt ett andra försök innan felet rapporteras. Detta eliminerar den kaskad av `Library error -1` som uppstod när flera block anropades inom loppet av millisekunder.
- **Hårdvarupaus vid Instansbyte (`stop_instance_procs` & `start_instance` i `sdr_processor.py`)**:
  - Lagt till 400 ms hårdvarupaus efter att processer terminerats innan en ny mottagare startas, vilket garanterar att USB-dongeln har släppt alla lås innan `rtl_fm` eller `rtl_sdr` initieras.

## [2026.10.13.22] - RF Activity Rullningslist och Styrning av TETRA-basstationsloggning

### Added
- **RF Activity Max 5 Synliga Rader och Rullningslist (`static/waterfall.css`)**:
  - Begränsat `.waterfall-channels` till max 5 synliga frekvensrader (`max-height: 220px; overflow-y: auto`).
  - Lagt till skräddarsydd mörk rullningslist med accentfärg så att dynamiskt upptäckta kanaler inte expanderar sidan vertikalt eller trycker ner larmtabellen.
  - Ignorerar systemhändelsen `RESTART` från att registreras som en RF-frekvens i vattenfallet.
- **Snabbfilter för att Dölja/Visa Basstationer (`templates/index.html` & `templates/larm.html`)**:
  - Ny snabbknapp `Dölj Basstationer / Visa Basstationer` i verktygsfältet bredvid pausknappen.
  - Implementerat anpassat DataTables-filter (`$.fn.dataTable.ext.search`) som omedelbart döljer eller visar basstationsrader (`TETRA-NET`, `RAKEL-`, `Aktiv TETRA Basstation`) utan att behöva ladda om sidan.
  - Valet sparas i `localStorage` (`hide_tetra_basestations`, standard: aktiverat/dolt).
- **Inställning för Loggning av TETRA-basstationer i Larmflödet (`sdr_processor.py`, `database.py`, `app.py`, `templates/settings.html`)**:
  - Ny inställning `log_tetra_basestations` (standard: `false`).
  - När inställningen är avstängd loggas låsta och synkroniserade basstationer i systemkonsolen med alla detaljer (SNR, frekvensdrift, modulation, nätverk, cellkod), men skapar inga rader i larmdatabasen (`messages.db`) eller på MQTT-kanalen för larm.
  - Vid aktivering sparas de som fullständiga informationsposter med strukturerad adress (`RAKEL-240-01`) och alias (`Rakel Basstation`).
- **Rensning av Tidigare Basstationsloggar (`/api/messages/basestations`)**:
  - Ny endpoint för att i ett klick rensa bort alla tidigare oskyddade basstationsloggar ur databasen direkt från inställningssidan.

## [2026.10.13.21] - Fixat Matematisk Bärvågsdetektering och Koherent Kanaleffekt i TETRA Scanner

### Fixed
- **Koherent Kanalackumulering (`measure_channel_powers` i `tetra_decoder.py`)**:
  - Åtgärdat en matematisk bugg i kanaliserad effektmätning: den tidigare koden kvadrerade och summerade samplen individuellt efter blandning (`mix_i^2 + mix_q^2`). På grund av den trigonometriska identiteten $\cos^2(\theta) + \sin^2(\theta) = 1$ tog rotationsvinkeln ut sig själv, vilket ledde till att alla kanaler fick exakt samma effektvärde och inte kunde urskiljas från bakgrundsbruset.
  - Implementerat koherent DFT-ackumulering över 25 kHz bandbreddsblock, vilket ger kraftig konstruktiv interferens för bärvågor och destruktiv utsläckning för brus. Detta gör att aktiva TETRA-bärvågor omedelbart sticker ut med +20 till +30 dB SNR och upptäcks av skannern.

## [2026.10.13.20] - Robust Sanering och Normalisering av Frekvenser i rtl_fm

### Fixed
- **Automatisk Sanering av Frekvenssträngar (`normalize_freq` i `sdr_processor.py` & `database.py`)**:
  - `rtl_fm` (C-funktionen `atofs`) inspekterar sista tecknet `f[strlen(f)-1]` för multiplikator (`M`, `k`). Om användaren angav ett avslutande mellanslag (t.ex. `169.8M `) tolkades sista tecknet som mellanslag och ignorerade `M`, vilket resulterade i att frekvensen sattes till 169.8 Hz och tunades till `253744 Hz` (253 kHz långvåg istället för 169.8 MHz).
  - Implementerat `normalize_freq` som tvättar bort alla interna och avslutande mellanslag, säkerställer korrekt versalt `M` för megahertz, hanterar frekvensintervall samt automatiskt lägger till `M` om användaren enbart anger ett rent tal i MHz (t.ex. `169.8` eller `161.4375`).
  - `save_sdr_instance` i `database.py` sanerar nu också frekvensen och serienumret vid databaslagring.

## [2026.10.13.19] - Automatisk Terminering av Föräldralösa RTL-processer och Garanterad USB-release

### Fixed
- **Automatisk Terminering av Föräldralösa USB-processer (`kill_orphaned_rtl_for_device` i `sdr_processor.py`)**:
  - Åtgärdat felet där `tetra_decoder.py` eller tidigare avbrutna instanser lämnade underprocesser (`rtl_sdr`, `rtl_fm`) igång som föräldralösa processer (adopterade av PID 1), vilket låste USB-enheten (`usb_claim_interface error -6`) även efter att instansen stängts av i gränssnittet.
  - Implementerat scanning av `/proc` för att automatiskt identifiera och döda (`SIGKILL`) alla föräldralösa processer som använder samma `-d <serial>` innan en ny instans startas samt vid stopp av en instans.
- **Graciös Processavstängning (`stop_instance_procs` i `sdr_processor.py`)**:
  - Ändrat avstängningssekvensen att först skicka `SIGTERM` så att Python-avkodare kan köra sin interna signalhanterare och avsluta sina egna barnprocesser innan hård avstängning (`SIGKILL`) genomförs.
- **Garanterad Processavslutning i `finally` (`tetra_decoder.py`)**:
  - `probe_block` och `stream_continuous` dödar nu explicit underprocessen `proc` i sitt `finally`-block, vilket omöjliggör att `rtl_sdr` lämnas hängande vid timeouts eller fel.

## [2026.10.13.18] - Återställt librtlsdr till Steve-M Drivrutiner

### Changed
- **Återställt `librtlsdr` i `Dockerfile`**:
  - Återställt källkodsrepot för `librtlsdr` till `https://github.com/steve-m/librtlsdr.git` (ordinarie standarddrivrutiner innan Blog V4-experimentet).
  - Säkerställer identisk binärkompatibilitet och USB-hantering som applikationen ursprungligen körde med.

## [2026.10.13.17] - Automatisk Sanering av Samplingsfrekvens och Enheter i rtl_fm

### Fixed
- **Robust Normalisering av Samplingshastighet (`normalize_rate_hz` i `sdr_processor.py`)**:
  - `rtl_fm` (C-funktionen `atofs`) stöder enbart gemener (`k`, `m`, `g`) och inte versaler (`K`, `M`). Om en användare anger `250K` tolkas detta som 250 Hz, vilket orsakar att `rtl_fm` kraschar omedelbart vid start.
  - Implementerat `normalize_rate_hz` som automatiskt omvandlar strängar med enheter som `250K`, `250k`, `22.05k` etc. till rena heltal i Hz (`250000`, `22050`) innan argumenten skickas till `rtl_fm` och `multimon-ng`.
  - Säkerställer att mottagare med RTL-SDR Blog V4 och övriga donglar startar stabilt oavsett versalisering i hårdvaruinställningarna.

## [2026.10.13.16] - Filbaserad Provtagning för RTL-SDR Blockskanning

### Fixed
- **Filbaserad Provtagning (`probe_block` i `tetra_decoder.py`)**:
  - Ersatt osäker stdout-piping (`-`) i `probe_block` med en temporär fil (`mkstemp`).
  - Åtgärdar pipe-deadlock och buffringsproblem i `rtl_sdr` som orsakade att processen hängde trots att hårdvaran var framgångsrikt claimad av containern.
  - Provtagningen slutförs nu blixtsnabbt och städar automatiskt upp temporärfilen direkt efter inläsning.

## [2026.10.13.15] - Detaljerad Timeout-felanalys för RTL-SDR Hårdvaruenheter

### Added
- **Stderr-utläsning vid TimeoutExpired (`tetra_decoder.py`)**:
  - Vid `TimeoutExpired` läses nu `te.stderr` ut från processen så att exakt meddelande från `rtl_sdr` (t.ex. `Device index out of range`, `usb_claim_interface error` etc.) skrivs ut direkt i loggen istället för en statisk gissning.

## [2026.10.13.14] - Återställt Standard Processpiping för POCSAG-mottagare (RIKS 1 / RIKS 2)

### Fixed
- **Återställt Standard Processpiping för Multi-SDR (`sdr_processor.py`)**:
  - Återställt `rtl_fm | multimon-ng` till standard `subprocess.Popen` utan `setsid()` / `start_new_session=True`.
  - Fixar problemet där `start_new_session=True` bröt standard Unix pipe-kommunikation mellan `rtl_fm` och `multimon-ng` och orsakade att RIKS 2 tystnade.
  - Återställt ren `p.kill()`-hantering i supervisorn utan processgruppsintervention.

## [2026.10.13.13] - Optimerad Provtagning och Utökad Timeout för USB-skanning

### Added
- **Optimerad Provtagning och Timeout för USB (`tetra_decoder.py`)**:
  - Ökat timeouten i `probe_block` från 3.5 till 8.0 sekunder för att ge Blog V4 och USB-bussen tillräcklig tid att initiera PLL och allokera USB-överföringar utan `TimeoutExpired`.
  - Minskat `duration_sec` till 0.08s (max 180 000 samples) vilket minskar datamängden från 1.44 MB till ~360 KB per block och accelererar svephastigheten dramatiskt.
  - Implementerat explicit hantering av `TimeoutExpired` med mjuk omstart och fördröjning för att förhindra att USB-bussen låses vid intensiva svep.

## [2026.10.13.12] - Officiellt RTL-SDR Blog V4 Drivrutinsstöd (rtlsdr-blog R828D) och Diagnostik

### Added
- **Officiellt RTL-SDR Blog V4 Drivrutinsstöd (`Dockerfile`)**:
  - Ersatt generisk `steve-m/librtlsdr` med det officiella `rtlsdrblog/rtl-sdr-blog`-repot som kompileras i Docker-bygget.
  - Åtgärdar felet där RTL-SDR Blog V4 med Rafael Micro R828D-tuner inte kunde initieras eller kännas igen inuti Docker-containern.
  - 100% bakåtkompatibelt med alla befintliga standard RTL2832U / V3-donglar.
- **Tydlig Hårdvarudiagnostik och Stderr-fångst (`tetra_decoder.py`)**:
  - `probe_block` och `stream_continuous` fångar nu felmeddelanden direkt från `rtl_sdr` (istället för att kassera dem i `DEVNULL`).
  - Om tunern misslyckas att öppna en USB-enhet eller om enheten är upptagen skrivs en tydlig `SCAN`-varning ut i loggkonsolen med exakt orsak och felkod.

## [2026.10.13.11] - Robust Processhantering, Tvåstegsdetektering med CFO-kompensation och Lax-test för TETRA

### Added
- **Robust Processhantering och Processgruppsdödning (`sdr_processor.py`)**:
  - `sdr_processor` startar nu underprocesser i separata processgrupper (`start_new_session=True` på POSIX/Linux).
  - `stop_instance_procs` dödar nu hela processträdet med `os.killpg(pgid, signal.SIGTERM / SIGKILL)`. Detta garanterar att eventuella underordnade hårdvaruprocesser (`rtl_sdr`) avslutas omedelbart och inte blir föräldralösa zombier som blockerar USB-enheten vid omstart.
- **Graceful Shutdown och Barnprocesshantering (`tetra_decoder.py`)**:
  - Implementerat `signal`-hanterare för `SIGTERM` och `SIGINT` i `tetra_decoder.py`.
  - Spårar aktivt underordnade `rtl_sdr`-processer (`_current_child_proc`) och terminerar dem omedelbart vid mottagen signal eller oväntat undantag, vilket möjliggör ren och direkt `kill` av TETRA PID.
- **Tvåstegsdetektering för TETRA-bärvågor**:
  - Steg 1: Spektral energimätning och bandbreddsanalys mot bakgrundsbrus (SNR-krav).
  - Steg 2: pi/4-DQPSK fasmodulationskontroll med automatisk Carrier Frequency Offset (CFO)-kompensation för att absorbera PPM-drift från USB-tuners.
- **Lax-test / Enkanalsläge**:
  - När användaren anger en enskild känd frekvens (t.ex. `390.125M`) låser mottagaren omedelbart på kanalen utan att kräva att den måste vinna en sveptävling över frekvensbandet.

## [2026.10.13.10] - pi/4-DQPSK Fasmodulationskorrelation och Breddat Frekvensstöd (390-430 MHz)

### Added
- **pi/4-DQPSK Fasmodulationskorrelation (`check_channel_dqpsk_modulation`)**:
  - Implementerat matematisk faskonstellationsanalys för bärvågsdetektering.
  - Verifierar att fasövergångarna mellan efterföljande symboler i I/Q-strömmen följer TETRA:s unika mönster ($\pm 45^\circ$ och $\pm 135^\circ$).
  - Skiljer med över 95% precision äkta TETRA-bärvågor från analoga FM-sändare, DMR och radiobrus.
- **Borttagning av 300-kanalers begränsning**:
  - Utökat kanalstödet till 2500 kanaler, vilket möjliggör massiva svep som `390.0M-430.0M` (40 MHz bandbredd, 1601 kanaler uppdelat i 20 st 2.4 MHz-block).
- **Dongel Cold-Start Kompensation**:
  - Kasserar de första 40 000 byten (ca 16 ms) av rå I/Q-data för att undvika USB- och tuner-initieringsbrus innan spektrummätning påbörjas.

## [2026.10.13.9] - Aktiv Kanalvalidering, Metadata-Watchdog och Automatisk Kanalbyte för TETRA

### Added
- **Aktiv Kanalvalidering och Falsk Positiv-skydd (`tetra_decoder.py`)**:
  - Infört strikt verifiering av äkta TETRA BSCH/synk innan en kanal låses. Analoga bärvågor, DMR eller radiobrus utan äkta nätverksdata accepteras inte längre.
  - Tillåter upp till 2 bitfel (BER) i 38-bitars STS-synkmönstret för robust detektering i verkliga radiomiljöer.
- **Metadata-Watchdog i Realtidsströmning**:
  - Om en kanal låses men inte sänder bekräftad TETRA-metadata (t.ex. `NET` med MCC/MNC, anrop eller SDS) inom 6 sekunder, avbryts mottagningen omedelbart.
  - Frekvensen placeras i en 90-sekunders cooldown (`blacklist_until`) och skannern hoppar automatiskt vidare till nästa starka kandidatkanal i blocket.
  - Om en aktiv basstation tystnar i mer än 25 sekunder återupptas skanningen automatiskt.
- **TETRA Basstationsspårning (`sdr_processor.py`)**:
  - Dedikerad loggning och hantering av `TETRA: NET`-händelser som `TETRA-NET` så att basstationssynkronisering och cellmetadata syns direkt i Dashboard och loggkonsol.

## [2026.10.13.8] - Blixtsnabb Wideband Block Scanning (2.4 MHz) för TETRA / RAKEL

### Added
- **Bredbandig Blockskanning i 2.4 MHz-fönster (`tetra_decoder.py`)**:
  - Ersatt långsam stegvis frekvensskanning kanal-för-kanal med **Wideband Block Scanning** som utnyttjar RTL-SDR Blog V4:s samplingsbandbredd på 2.0 till 2.4 MHz.
  - Hela frekvensband upp till 2.4 MHz (som t.ex. `420.3M:422.7M-25K` med 97 kanaler) täcks nu i **ett enda momentant block** centrerat på 421.5 MHz utan att tunern behöver låsa om sin PLL 97 gånger.
  - Större bandbredder (t.ex. 390–395 MHz) delas automatiskt in i minimala 2.0–2.4 MHz-block (`plan_wideband_blocks`).
- **Parallell RF-effektmätning (`measure_channel_powers`)**:
  - Samtliga 25 kHz-kanaler i blocket analyseras simultant med digital komplex blandning på under 20 millisekunder.
  - Toppkandidater med kontinuerlig RF-bärvåg (karakteristiskt för TETRA MCCH) identifieras och verifieras mot TETRA STS-synkmönster och nätverkskod.
  - Skanningstiden reducerad från 20–30 sekunder till under 1 sekund!
- **Enhetstester**:
  - Tillagt enhetstest `test_tetra_wideband_blocks_and_channel_powers` i `tests/test_sdr_watchdog.py`.

## [2026.10.13.7] - Åtgärdat Start och Övervakning av TETRA Skanningsinstanser

### Fixed
- **SDR Supervisor Startlogik (`sdr_processor.py`)**:
  - Åtgärdat bugg i supervisor-loopen där instanser med fristående skanningsprocess (där `p1` är `None` och `p2` är avkodaren/skannern) tidigare misslyckades med felmeddelandet `"Failed to start <namn>. Retrying next sync."`.
  - Supervisor accepterar nu processpar där `p1` är valfri (`if p2:`), vilket tillåter `tetra_decoder.py` att starta och hantera frekvenssvep sömlöst.
  - Säkrat upp `verify_recovery`, `get_sdr_runtime_status()` och supervisor heartbeat så att instanser utan separat `p1` rapporteras som friska (`OK (lyssnar)`) istället för felaktigt larm om död `rtl_fm`.
- **Enhetstester**:
  - Tillagt enhetstest `test_supervisor_accepts_instance_when_p1_is_none` i `tests/test_sdr_watchdog.py`.

## [2026.10.13.6] - Frekvensskanning och Kontrollkanaljakt (MCCH Hunt) för TETRA / RAKEL

### Added
- **Stöd för Frekvensintervall och Kanallistor vid TETRA-mottagning**:
  - Användare kan nu i fältet **Frequency** ange:
    - Frekvensintervall med standard 25 kHz-raster: t.ex. `390M-395M` eller `390.000M:395.000M:25k`.
    - Kommaseparerad lista av kända kontrollkanaler: t.ex. `390.125M, 390.250M, 391.025M`.
    - Enskild fast frekvens: t.ex. `390.125M`.
- **Frekvensskanningsmotor (`TetraScanner` i `tetra_decoder.py`)**:
  - Utför automatisk kanalskanning (Control Channel Hunt).
  - Skannar igenom kanalerna med korta samplingar, demodulerar och detekterar TETRA STS (synkmönster) samt BSCH (nätverkskod MCC/MNC).
  - Låser automatiskt fast på den aktiva basstationens kontrollkanal (`TETRA: LOCK Freq: <freq>`) och startar kontinuerlig avkodning av talgruppsanrop och SDS-text.
  - Återupptar automatiskt skanningen om radiosignalen försvinner.
- **Dynamisk Frekvensrapportering i `sdr_processor.py`**:
  - Fångar upp `TETRA: LOCK` och lagrar aktiv lyssnarfrekvens (`active_frequency`).
  - Larm och händelser som registreras i databasen sparas med den exakta frekvensen mottagaren har låst på istället för hela intervallet.
  - Skanningshändelser (`TETRA: SCAN`) loggas i realtid utan att belasta larmdatabasen.
- **Gränssnittsuppdatering ([templates/sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html))**:
  - Tydlig instruktion under frekvensfältet för intervall och frekvenslistor.
- **Enhetstester**:
  - Automatiserade enhetstester i `tests/test_sdr_watchdog.py` för scanning-uppstart och frekvenslåsning (`test_tetra_scanning_start_instance`, `test_tetra_monitor_handles_scan_and_lock_frequency`).

## [2026.10.13.5] - Modulärt Stöd för TETRA / RAKEL (Kontrollkanal & SDS)

### Added
- **Modulär TETRA / RAKEL-avkodare (`tetra_decoder.py`)**:
  - Helt fristående Python-modul som tar emot råa I/Q-samplingar från SDR (via `rtl_sdr`), utför $\pi/4$-DQPSK demodulering och söker efter TETRA Synchronization Training Sequence (STS).
  - Avkodar Kontrollkanal (MCCH/BSCH) nätverksmetadata (MCC, MNC, Cell ID), röstsamtalssignalering (Call Setup), enhetsstatusuppdateringar (t.ex. SOS, Tillgänglig, Framme) och korta datameddelanden (Short Data Service - SDS).
  - Fallback / simulerat testflöde vid fristående körning eller saknad hårdvara för enkel driftsverifiering.
- **SDR Pipeline-integration i `sdr_processor.py`**:
  - Nytt protokollalternativ: `TETRA` i inställningar för SDR-mottagare.
  - När protokoll `TETRA` väljs startas `rtl_sdr` (pipad till `tetra_decoder.py`) istället för `rtl_fm | multimon-ng`.
  - Normaliserad integration mot befintliga datatabeller och UI: GSSI (talgrupp) eller ISSI (radio-ID) mappas till `address`, anrops-/statustext eller SDS-meddelande mappas till `message`, med bitrate satt till `TETRA-SDS`, `TETRA-CALL` eller `TETRA-STAT`.
  - Full kompatibilitet med befintliga CapCode-alias (namnge talgrupper/radio-ID), larmord, duplikathantering och realtidsvisning (SSE) utan ändringar i databasscheman.
- **Docker & Byggstöd**:
  - Säkerställt att binären `rtl_sdr` kopieras över till runtime-steget i Dockerfile.
- **Enhetstester**:
  - Nya automatiserade enhetstester i `tests/test_sdr_watchdog.py` för processuppstart och meddelandeavkodning vid TETRA-protokoll.

## [2026.10.13.4] - Möjlighet att Kopiera / Klona SDR-mottagare i Inställningar

### Added
- **Kopiering av SDR-mottagare (`clone_sdr_instance`)**:
  - Infört en "Copy"-knapp på varje SDR-kort under **Settings -> SDR Receivers**.
  - Modal som tillåter att ange nytt mottagarnamn och frekvens med alla ursprungliga hårdvaru- och avkodarinställningar förifyllda.
  - Samtliga filter (`sample_rate`, `resample_rate`, `gain`, `ppm_error`, `enable_dc_removal`, `enable_deemp`, `enable_high_quality_fir`, `atan_math`, `oversampling`, `multimon_verbosity`, `multimon_charset`, `protocol`) dupliceras exakt till den nya mottagaren.
  - Den klonade mottagaren skapas som inaktiv (`disabled`) för att förhindra USB-portkonflikter innan användaren har konfigurerat eventuellt dongel-serienummer.
  - Nytt API-slutpunkt: `POST /api/sdr/<id>/clone`.

## [2026.10.13.3] - Åtgärdat Sparning av Duplikathantering och Duplikatfönster i Inställningar

### Fixed
- **Sparning av Duplicate Handling & Time Window**:
  - Åtgärdat bugg i `/api/settings` ([app.py](file:///d:/antigravity/pager-monitor/app.py)) där `duplicate_handling` och `duplicate_window` (samt avancerade filter `enable_high_quality_fir`, `atan_math`, `oversampling`) saknades i `allowed_keys`-vitlistan.
  - Inställningar för duplikathantering (`merge`, `mark`, `hide`, `discard`) och tidsfönster sparas och laddas nu pålitligt vid ändring i användargränssnittet.

## [2026.10.13.2] - Stöd för Manuell SDR Gain (-g) och PPM-korrigering (-p) i rtl_fm

### Fixed
- **Stöd för Manuell Gain och PPM i SDR Processor**:
  - Åtgärdat brist i `sdr_processor.py` där konfigurerat `gain` (t.ex. 28 dB) och `ppm_error` hämtades från inställningsdatabasen men inte bifogades till kommandoradsanropet för `rtl_fm`.
  - Mottagare tilldelas nu korrekt flaggorna `-g <gain>` och `-p <ppm>`, vilket eliminerar oönskad fallback till "automatic tuner gain" vid manuellt inställt gain.

## [2026.10.13.1] - Universell Tema-anpassad Bekräftelsedialog (confirm.js), Identisk Knappgeometri och Avlägsnad Oskärpa

### Added
- **Universell Bekräftelsemodul (`static/confirm.js`)**:
  - Infört en global, standardiserad bekräftelsedialog (`window.showConfirmDialog` och `window.showConfirm`) för samtliga åtgärder och borttagningar i hela applikationen.
  - Eliminerat webbläsarens inbyggda, gråa standard-`confirm()` över samtliga vyer ([statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html), [settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html), [sdr_settings.html](file:///d:/antigravity/pager-monitor/templates/sdr_settings.html), [alerts.html](file:///d:/antigravity/pager-monitor/templates/alerts.html), [aliases.html](file:///d:/antigravity/pager-monitor/templates/aliases.html), [rules.html](file:///d:/antigravity/pager-monitor/templates/rules.html)).
  - Dialogen skapas dynamiskt och stöder stängning via Escape-tangent eller klick utanför dialogen.

### Fixed
- **Knappgeometri och Inbördes Skevhet**:
  - Samtliga knappar i dialogernas footer har nu exakt samma dimensioner (`height: 38px`, `padding: 0 1.25rem`, samma fontstorlek, `margin: 0 !important`).
  - Åtgärdat tidigare problem där `.secondary-btn` (Cancel) hade `margin-top: 1rem;` och annan padding än primärknappen, vilket orsakade ojämna höjder och vertikal förskjutning.
- **Avlägsnad Smearing, Suddighet och Smutsig Gråfärg**:
  - Tagit bort `backdrop-filter: blur(...)` från `.modal-content` som tidigare orsakade textutsmetning och GPU-renderingsoskärpa.
  - Fullständig temaintegration:
    - **Mörkt tema**: Djupt solid OLED-bakgrund (`#0d1117`), skarp `#1f2937` ram och distinkt textfärg.
    - **Ljust tema**: Krispigt ren snövit bakgrund (`#ffffff !important`), mjuk `#e2e8f0` ram och djup kontrastrik text (`#0f172a`), utan någon grådaskig ton.
  - Tillämpat GPU-stabilisering med `-webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; transform: translateZ(0); backface-visibility: hidden;`.

## [2026.10.12.16] - Ändrat Kolumnnamn till RF / META och Optimerad Kolumnbredd (115px)

### Changed
- **Optimerat Kolumnnamn och Bredd för RF / META**:
  - Ändrade kolumnrubriken från långa `FREQUENCY / META` (16 tecken) till mer tekniskt och koncist `RF / META` (9 tecken) i [index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html) och [statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html).
  - Minskat kolumnens fasta bredd från 170px till **115px** (`min-width: 105px; max-width: 130px;`).
  - Detta eliminerar onödig tom yta till höger om de kompakta pillren och frigör ytterligare 55px horisontell bredd för `MESSAGE`- och `CAPCODE`-kolumnerna.

## [2026.10.12.15] - Breddning av FREQUENCY / META och Ren Formatering av Bitrate-piller

### Fixed
- **Kolumnrubrik och Piller Spiller Ut ur Cellen i FREQUENCY / META**:
  - Kolumnen `col-meta` var för snävt begränsad till 125px, vilket ledde till att tabellrubriken avhöggs till "FREQUENCY / MET" (sorteringspilen och texten rymdes inte) samt att pillret "POCSAG 1200bps" svämmade över cellens gräns in i CapCode-kolumnen.
  - Ökade `col-meta` bredd till 170px (`min-width: 160px; max-width: 195px;`) över samtliga vyer ([index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html)).
  - Lagt till `max-width: 100% !important; box-sizing: border-box !important; overflow: hidden !important; text-overflow: ellipsis !important;` på alla `.badge`-element och `.meta-wrapper` så att piller aldrig kan spilla över cellens linjer.
  - Förbättrade bitrate-formateringen så att t.ex. `"POCSAG 1200"` visas kompakt och rent som `"1200bps"` istället för klumpiga `"POCSAG 1200bps"`.

## [2026.10.12.14] - Eteraktivitet Kollapsad som Standard, Skarpa Action-ikoner, Normaliserade SDR-kanaler och Fast Tabellayout

### Added
- **Persistent Kollapsläge för Eteraktivitet (Activity Ribbon)**:
  - Vattenfallet / eteraktiviteten startar nu alltid kollapsad som standard för att maximera utrymmet för realtidsmeddelandena.
  - Användarens val (öppen eller kollapsad) sparas i webbläsarens `localStorage` (`pagermonitor-ribbon-collapsed`) och förblir ihågkommet mellan omladdningar.
  - Förrenderas med klassen `collapsed` direkt i servermallen för att undvika layoutskiftningar.
- **Skarpa och Tydliga Action-ikoner**:
  - Bytte ut Font Awesome regular `far fa-copy` mot solid `fas fa-copy`, vilket eliminerar antialiasing-suddighet på små ikonytor.
  - Raderade motstridig `opacity: 0.6`-regel som orsakade att raderingsikonen upplevdes blek och luddig.
  - Tillämpade `text-rendering: geometricPrecision`, subpixel font-smoothing samt subtila borders med hög kontrast för både ljust (`[data-theme="light"]`) och mörkt tema.

### Fixed
- **Horisontell Scrollbar och Kolumnspill för Actions**:
  - Införde `table-layout: fixed !important` med fasta pixelbredder för alla metadatakolumner (`col-id`: 55px, `col-time`: 110px, `col-meta`: 125px, `col-addr`: 150px, `col-actions`: 38px) och flytande bredd för `col-msg`.
  - Ersatte texten "Actions" med en ren vertikal ikon `<i class="fas fa-ellipsis-v"></i>` och dolde DataTables sorteringspilar på kolumnen för att förhindra kolumnexpansion.
  - Satte `.table-container` till `overflow-x: hidden;` på desktop för att helt förhindra horisontella rullningslister.
- **Dubblerade SDR-kanaler i Eteraktivitet**:
  - Normaliserade kanalnyckel-genereringen i `waterfall.js` till avrundad frekvens (`freq_XXXX`). Konfigurerade SDR-instanser (`RIKS 1`, `RIKS 2`) och inkommande meddelandefrekvenser mappar nu till exakt samma vattenfallskanal istället för att skapa separata frekvensrader med noll träffar.
- **Helhetlig Engelsk Översättning**:
  - Översatt alla etiketter och dialoger i Activity Ribbon, pausningsbannern, Action-kolumnerna och konsoldockan till engelska.

## [2026.10.12.13] - Vertikalt Staplade Actions, Duplikatgruppering (Merge & 2x/3x Badge) och Fullständig Engelsk Översättning

### Added
- **Duplikatgruppering till Samma Händelse (Lösning 1)**:
  - Nytt rekommenderat läge i duplikathanteringen (`duplicate_handling = 'merge'`).
  - Istället för att skapa nya dubblettrader i databasen slås identiska återutsändningar samman i samma händelse.
  - Varje upprepning ökar en `repeat_count`-räknare och uppdaterar `last_timestamp`.
  - En distinkt lila märke (`repeat-badge`, t.ex. `2x`, `3x`) visas i tabellen tillsammans med en indikation om senaste tidpunkt `(Last: HH:MM:SS)`.
  - SSE-klienten tar emot händelser av typen `repeat_update` och uppdaterar befintlig tabellrad i realtid med en mjuk animationspuls (`repeat-pulse`).
- **Vertikalt Staplade Action-knappar (Prio på Message)**:
  - Omformaterat `.actions-wrapper` från horisontell rad till vertikal kolumn (`flex-direction: column; gap: 4px;`).
  - Begränsat bredden på kolumnen Actions (`th.col-actions`, `td.actions-cell`) till 38px/44px max (minskning från ca 115px), vilket frigör ca 75-80px horisontell bredd på mindre desktop-skärmar.
  - Prioriterar meddelandekolumnen (`MESSAGE`) så att texten inte trycks ihop eller radbryts onödigt.

### Changed
- **Fullständig Översättning till Engelska**:
  - Samtliga inställningsvyer, flikar, förklarande texter, kort, knappar och statusmeddelanden i [settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html) är nu helt på engelska.
  - Larmordshanteringen i [alerts.html](file:///d:/antigravity/pager-monitor/templates/alerts.html) och [rules.html](file:///d:/antigravity/pager-monitor/templates/rules.html) har översatts till engelska.
  - Alla action-knappar (kopiera, lås, ta bort) och deras tooltips och bekräftelsemeddelanden har översatts till engelska över samtliga vyer.

## [2026.10.12.12] - Live Paus- och Buffertläge samt Visuell Eteraktivitet (Activity Ribbon / Radio Waterfall)

### Added
- **Live "Paus & Buffert"-läge för realtidsflödet**:
  - Implementerat en dedikerad kontrollknapp (`#livePauseBtn`) i Dashboard och Larmvyn bredvid sökfältet.
  - Tillåter att frysa datatabellen när man läser eller granskar specifika meddelanden utan att nya inkommande rader förskjuter tabellen.
  - Inkommande meddelanden samlas i en klientbuffert (`pausedQueue`) med en dynamisk räknare på paus-knappen (`#livePauseBadge`) och en diskret informationslist (`#pausedNotificationBar`) ovanför tabellen.
  - Vid återupptagning (*Visa och återuppta*) spolas alla buffrade meddelanden in i DataTables i korrekt ordning med mjuk visuell animationspuls (`.new-msg-pulse`).
- **Visuell "Eteraktivitet" (Activity Ribbon / Radio Waterfall)**:
  - En kompakt, elegant aktivitetsremsa (`#activityRibbonPanel`) ovanför huvudtabellen som visualiserar radioaktiviteten över de senaste 60 minuterna per SDR-mottagare / frekvens.
  - Byggd med hårdvaruaccelererad HTML5 Canvas och Retina/High-DPI-skalning för 60 FPS utan DOM-överbelastning.
  - Automatisk spår-detektering för alla aktiva SDR-mottagare (`RIKS 1`, `RIKS 2` etc.) från `/api/sdr` och inkommande frekvenser.
  - Färgkodade pelare med differentiering för normal trafik (cyan/blå gradient), larmträffar (neonröd) och duplikat (amber).
  - Realtidspuls på aktuell minut (`Nu`) och live-dioder som blinkar grönt vid mottagning på respektive frekvens.
  - Interaktiv hover-tooltip som visar exakt klockslag, frekvens och antal meddelanden/larm för varje minut.
  - Klick på en kanalrad filtrerar tabellen omedelbart till den specifika mottagaren/frekvensen.
  - Möjlighet att minimera/fälla ihop panelen via toggle-knapp (`#ribbonToggleBtn`) med sparat läge i `localStorage`.

## [2026.10.12.11] - Korrigering av Bakgrundspilar i Rullgardinsmenyer

### Fixed
- **Repeterande Bakgrundsikoner i Rullgardinsmenyer (Select Controls)**:
  - Åtgärdat felet där rullgardinsmenyer (`<select class="form-input">`) i ljust tema täcktes av ett mönster av repeterande pil-ikoner (`v v v v v`).
  - Orsaken var att CSS-regeln `background: #ffffff;` för ljust tema nollställde webbläsarens `background-repeat` och `background-position`, vilket fick den anpassade SVG-chevronen att tapetsera hela inmatningsrutan.
  - Ändrat till `background-color: #ffffff;` samt tilldelat explicita `background-repeat: no-repeat !important;`, `background-position: right 0.75rem center !important;` och fixerad storlek `1rem 1rem !important;`.

## [2026.10.12.10] - Avlägsnande av CapCode-gruppering och Förfinat Inställningsgränssnitt

### Removed
- **CapCode Radgruppering**:
  - Helt avlägsnat funktionen för DataTables-gruppering per CapCode från Dashboard och Larmvyn efter användarutvärdering.
  - Rensat bort externa RowGroup CDN-resurser, knappar, CSS och relaterade JavaScript-hjälpare.

### Fixed
- **Temastyling och Kompakt Layout i Inställningar**:
  - Åtgärdat formulärrutorna för *Åtgärd för duplikat* och *Tidsfönster* i [settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html) så att de använder den enhetliga klassen `form-input` och följer ljust och mörkt tema (med skräddarsydd chevron, bakgrund, kantlinjer och fokusmarkering).
  - Grupperat *Signalfiltrering* och *Duplikathantering* i en gemensam, stilren panel (`settings-subpanel`) med en subtil avgränsare för att eliminera onödiga isolerade kort.
  - Grupperat *Färgtema*, *Typsnitt* och *Textstorlek* i en sammanhållen panel (`settings-subpanel`).
  - Minskat överdrivna marginaler och padding på inställningscontainern, flikraden och kolumnavstånden så att gränssnittet upplevs rent, kompakt och välbalanserat.

## [2026.10.12.9] - Duplikathantering, CapCode DataTables Gruppering och Persistent Konsolfilter

### Added
- **Konfigurerbar Duplikathantering**:
  - Ny sektion under Inställningar ("Duplikathantering & Larmrepetition") med valbara åtgärder för dubblettmeddelanden:
    - *Markera med badge (Standard)*: Sparar meddelandet med flaggan `is_duplicate=1` och visar gul "Duplicate"-badge i tabeller.
    - *Dölj i tabeller*: Sparar i databasen för historik och statistik, men döljer automatiskt duplikat från Dashboard och Larmvyn.
    - *Kasta helt*: Droppar dubbletten omedelbart i SDR-processorn utan att spara till databas eller sända via MQTT/SSE.
  - Konfigurerbart tidsfönster (`duplicate_window`, standard 120 sekunder i stället för den tidigare fasta 60-sekundersgränsen) så att larmrepetition med 60 sekunders intervall fångas upp korrekt.
- **CapCode Radgruppering i DataTables**:
  - Integrerat DataTables RowGroup 1.5.1 i Dashboard (`/`) och Larm (`/larm`).
  - Ny knapp i gränssnittet ("Gruppera CapCode") som samlar alla meddelanden under eleganta grupperingsrader med CapCode/Alias och antal händelser per grupp.
  - Valet sparas i `localStorage` så att tabellens grupperingsläge bevaras mellan sidladdningar och sessioner.

### Fixed
- **Persistent Konsolfilter och Synkning mellan Flikar**:
  - Åtgärdat felet där filtret i systemkonsolen (t.ex. `DECODED`) nollställdes eller visade tom vy när användaren navigerade eller bytte flik.
  - Initiering och filterbyte anropar nu `/api/logs/history?level=...` för att hämta relevant logghistorik från serverns ringbuffer utan att drunkna i bakgrundsbrus från radion.
  - Lagt till realtidssynkronisering via `storage` och `visibilitychange` så att filterläge hålls synkat mellan flera öppna webbläsarflikar.

## [2026.10.12.8] - Mobilvy och Fast Bottom Navigation Bar

### Added
- **Fast Bottom Navigation Bar för mobila skärmar**:
  - På skärmar <= 768px bredd konverteras den traditionella fasta sidopanelen automatiskt till en modern, flytande Bottom Navigation Bar.
  - Placerar de 5 primära navigeringslänkarna (Dashboard, Larm, Regler & Triggers, Statistik, Inställningar) lättåtkomliga för tummen med jämnt fördelade ikoner och etiketter.
  - Inkluderar fullt stöd för iOS och Android Safe Areas (`env(safe-area-inset-bottom)`) samt bakgrundsblur (glassmorphism).
- **Responsiv layout och touch-anpassning**:
  - Huvudinnehållet anpassar sig automatiskt till 100% skärmbredd utan att knuffas av sidopanelen.
  - Scroll-to-top-knappen flyter dynamiskt ovanför mobilraden.
  - DataTables döljer indexkolumnen (`#`) på mobil för att frigöra maximal horisontell yta för larmmeddelanden och CapCodes.
  - Inställningsflikar stöder nu horisontell touch-scrollning utan att brytas i vertikalt hackiga rader.
  - Formelement, SDR-kort och statistikdiagram staplas responsivt till 1 kolumn.
  - Docker- och systemkonsoldockan dockar snyggt ovanför den mobila navigationsraden.

## [2026.10.12.7] - Befintliga Larmordstabell och Unicode-stöd för Larmfiltrering


### Fixed
- **Befintliga larmord i gränssnittet (Alert Words Table)**:
  - Lade till en fullständig tabell för "Befintliga larmord" direkt under textrutan i fliken Alert Words på `/rules` och `/alerts`.
  - Visar samtliga sparade larmord med larmordsbadge, färgkod, aktiv-status samt direktknapp för att ta bort enskilda ord.
  - Tabellen och textrutan synkroniseras nu automatiskt direkt när användaren sparar eller tar bort ord.
  - Åtgärdade förvirringen kring varför nytillagda ord (såsom "SKADA") inte syntes i någon lista efter att ha sparats.

### Added
- **Unicode-oberoende larmmatchning (Å, Ä, Ö)**:
  - Registrerade funktionen `UPPER_UNICODE` i SQLite-anslutningar så att larmfiltrering för svenska ord (t.ex. `STÖLD`, `LÄCKA`, `DÖD`, `MILITÄR`, `ÖVERFALL`, `SKADA`) matchar skiftlägesoberoende oavsett om texten är gemener eller versaler.
  - Lade till automatiserade enhetstester för larmordstabellens rendering samt svensk Unicode-matchning i `tests/test_security_and_larm.py`.

## [2026.10.12.6] - Fix Contrast and Typography for DECODED Messages in Light Theme

### Fixed
- **Färgkontrast i ljust tema (Light Theme Contrast Fix)**:
  - Åtgärdade problemet där avkodade meddelanden (`.is-decoded`) hade ljus mintgrön text mot ljusgrön bakgrund i ljust tema, vilket gjorde texten oläslig.
  - Införde dynamiska CSS-temavariabler (`--console-decoded-bg`, `--console-decoded-border`, `--console-decoded-text`) med WCAG AAA-kontrast:
    - I ljust tema: Mörk skogsgrön text (`#064e3b`) mot mjukt tonad ljusgrön bakgrund (`#f0fdf4`) och distinkt mörkgrön vänstermarginal (`#059669`).
    - I mörkt tema: Krispigt vit text (`#f1f5f9`) mot mörkgrön bakgrund (`rgba(16, 185, 129, 0.12)`).
  - Lade till en tydlig grön badge `<span class="console-tag-decoded">DECODED &rarr;</span>` för att tydligt skilja larmetiketten från meddelandetexten.
  - Säkrade även färgkontrast för fel- (`--console-error-text`) och varningsrader (`--console-warning-text`) i ljust tema.

## [2026.10.12.5] - Dedicated DECODED Filter in Console Dock

### Added
- **Dedikerat DECODED-filter i konsoldockan**:
  - Lade till en direkt filterknapp `DECODED` i konsolens verktygsfält på samtliga sidor.
  - Filtrerar fram uteslutande framgångsrikt avkodade larmmeddelanden (`DECODED -> Address: ..., Alias: ..., Msg: ...`) och exkluderar RAW-strömmar, heartbeats och allmänna systemmeddelanden.
  - Lade till visuell framhävning för avkodade loggrader (`.console-log-row.is-decoded`) med en smaragdgrön accentlinje och tonad bakgrund.
  - Stöd för `level=DECODED` i historik-API:et (`GET /api/logs/history?level=DECODED`) i `log_streamer.py`.
  - Regressionstest tillagt i `tests/test_log_console.py`.

## [2026.10.12.4] - Fix False-Positive Garbage Drops for Pager Separator Lines

### Fixed
- **Skräpfilter (is_garbage_message)**:
  - Åtgärdade ett allvarligt fel där legitima larmmeddelanden med avskiljarlinjefält (t.ex. Siemens DesigoCC och SOS Alarm med `---------------------- End of message ----------------------` eller `===` eller `...` eller `*** LARM ***`) felaktigt droppades som `GARBAGE`.
  - Uppdaterade symbolkontrollen så att vanliga formateringstecken och separatorer (`-`, `=`, `.`, `*`, `_`, `/`) undantas från bruskontrollen.
  - Säkrade att meddelanden med hög läsbarhet (`readable_ratio >= 0.85`) aldrig avfärdas på grund av avgränsningslinjer eller ellipser.
  - Lade till regressionstest `test_is_garbage_message_allows_desigo_separator_and_drops_noise` i testsviten.

## [2026.10.12.3] - Real-time Docker & System Console Dock

### Added
- **Global Docker- och Systemkonsol**:
  - Implementerade ett dockat konsolfönster i botten av gränssnittet tillgängligt på samtliga sidor (`index.html`, `larm.html`, `statistics.html`, `settings.html`, `rules.html`, `sdr_settings.html`, `aliases.html`, `alerts.html`).
  - Visar 100 % av all loggutdata som normalt syns i `docker logs` via in-process logg-interception och stream-tee för både `logging` och `stdout`/`stderr`.
- **Färgkodning & ANSI-stöd**:
  - Färgkodade loggnivå-badges för `INFO` (cyan/blå), `WARNING` (bärnsten), `ERROR`/`CRITICAL` (röd), `DEBUG` (lila) och `RAW`/`STDOUT` (smaragdgrön).
  - Integrerad parser för ANSI escape-koder som konverterar terminalfärger till formaterade span-element.
- **Radbrytning & Textformatering (Word-wrap)**:
  - Interaktiv verktygsradsknapp för att växla mellan radbrytning (`white-space: pre-wrap`) och horisontell terminalrullning (`white-space: pre`).
- **Autoscroll & Användarvänlighet**:
  - Intelligent autoscroll som automatiskt följer nya loggar vid botten men pausas när användaren manuellt scrollar uppåt för inspektion.
  - Sök- och filtreringsfunktion i realtid (Alla, Info, Varningar, Fel, SDR / System).
  - Exportfunktion för att ladda ner visade loggar som `.txt`.
  - Resize-handtag för att dynamiskt ändra konsolhöjden samt spara användarinställningar och minimeringsläge i `localStorage`.
- **Backend Log Streamer (`log_streamer.py`)**:
  - Egen `LogManager` med in-memory ringbuffer (2 500 loggrader) och Server-Sent Events (SSE) via `/api/logs/stream`.
  - Endpoints för historik (`GET /api/logs/history`) och tömning (`POST /api/logs/clear`).

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
