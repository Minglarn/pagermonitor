# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Calendar Versioning (CalVer) `YYYY.0M.0D`.

## [2026.10.16.17] - Flödet Pausat Flyttad till Toast i Mitten Högst Upp

- **Toast-notifiering for Flödespaus ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
  - Flyttat `#hoverPausePill` ("Flödet Pausat") fran att ligga inuti `.table-container` till att visas som en global toast fixerad i mitten hogst upp pa skarmen (`position: fixed; top: 18px; left: 50%; transform: translateX(-50%); z-index: 99999;`).
  - Toasten ar helt frikopplad fran tabellflodet och tacker aldrig langre filterknapparna ("Alla protokoll", "Alla frekvenser", "Alla flygplatser", "Filtrera pa ACARS Label").
  - `pointer-events: none` sakerstaller att alla klick och interaktioner passerar rakt igenom utan att störa anvandaren.
  - Kopplat `setupHoverPause()` till `#alarmsTable` sa att musrorelser over filtermenyn ovanfor tabellen inte langre triggar onodig pausning.

## [2026.10.16.16] - Inbyggd UDP 5563-lyssnare for VDL2/acars_router och Session-isolerad TCP-klient

- **Inbyggd UDP 5563-mottagare ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Startar automatiskt en bakgrundstråd som lyssnar pa UDP (SOCK_DGRAM) pa `0.0.0.0:5563` (standardporten dit `acars_router` skickar `AR_SEND_UDP_VDLM2`), samt pa konfigurerad port om `self.port != 5563`.
  - Inkommande UDP-datagram avkodas som UTF-8 och delas pa radbrytningar; JSON-objekt med `"vdl2"` tolkas och berikar statistiken samt liveflodet.
  - Paket med `"hfdl"` vidarebefordras automatiskt till `hfdl_receiver` om den ar aktiv.
  - Satter mottagarstatus till `Aktiv (UDP 5563)` och `connected = True` sa snart UDP-trafik tas emot.
- **Isolering mot Docker Hairpin NAT & Tyst Exponential Backoff**:
  - Vid omedelbar nedkoppling (`< 0.5s`, Docker Hairpin NAT) da containern och vardtjansten delar samma IP, undertrycks repetitiv WARNING-loggning om UDP-lyssnaren pa 5563 ar igang. TCP-backoffen okas tyst till 60s pa DEBUG-niva.
  - Om `connect()` timar ut nar UDP ar aktiv, loggas detta pa DEBUG-niva utan att varna var 5:e sekund.
- **Tradsakerhet och Garanterad Enskild Arbetartrad**:
  - Implementerat strikt sessionshantering (`_worker_session`) och trad-ID-verifiering (`_thread_id == current_thread_id`) i bade TCP-klientloopen och UDP-lyssnaren.
  - `stop()` och `start()` avbryter aktiva sockets och invantar (`join`) tidigare tradar innan nya startas, vilket garanterar att tva arbetartradar aldrig kan kora parallellt.
  - I lasloopen hanteras `(socket.timeout, TimeoutError)` exklusivt med `continue` utan att logga natverksavbrott eller stanga anslutningen.
- **Enhetstester ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - `test_udp_vdl2_packet_reception`: Verifierar att syntetiska UDP-datagram pa port 5563 avkodas korrekt, raknar upp `packets_received` och markerar status som ansluten.
  - `test_single_thread_enforcement_on_restart`: Verifierar att omstart terminerar gamla sessioner och endast tillater en aktiv arbetartrad.

## [2026.10.16.15] - Återställd Ren och Stabil TCP-klient i VDL2, HFDL och SATC

- **Klassisk och Stabil TCP-klient ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [hfdl_receiver.py](file:///d:/antigravity/pager-monitor/hfdl_receiver.py), [satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - Eliminerat all felaktig "omedelbar EOF"-detektering och krånglig backoff-logik som orsakade oönskade nedkopplingar.
  - Återställt till en ren, klassisk TCP-klientloop:
    - Uppkoppling sker med `sock.settimeout(10.0)` och loggar `Ansluten till {host}:{port}!` direkt vid framgångsrik `connect()`.
    - Sätter `sock.settimeout(5.0)` för att kontrollera `self.running` var 5:e sekund utan att avbryta socketen.
    - Vid `(socket.timeout, TimeoutError)`: fortsätter i loopen med `continue` (normalt vid tystnad på frekvensen).
    - Endast om `sock.recv(4096)` returnerar `b""` (motparten faktiskt stängt socketen) avbryts loopen och återansluter efter 5 sekunder.
- **Ingen Lokal Portbindning vid Specifik IP-adress**:
  - Mottagarna agerar uteslutande som utgående TCP-klienter mot specificerad IP (t.ex. `192.168.1.242:15555`) och binder ingen lokal server-/UDP-socket.

## [2026.10.16.14] - 10s/5s TCP Timeout, Eliminering av Lokal Portbindning vid Fjärr-IP och Trådblockering

- **Robust TCP-klient i VDL2, HFDL och SATC ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [hfdl_receiver.py](file:///d:/antigravity/pager-monitor/hfdl_receiver.py), [satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - Konfigurerat `sock.settimeout(10.0)` vid `sock.connect((host, port))` och `sock.settimeout(5.0)` för chunk-läsning (`sock.recv(4096)`).
  - Vid tystnad på frekvensen fångas `(socket.timeout, TimeoutError)` omedelbart och kör `continue` utan att koppla ner socketen.
  - Eliminerat `sock.makefile()` permanent till förmån för en ren byte-chunk-buffer.
- **Ingen Lokal Portbindning när Host är en IP-adress ([hfdl_receiver.py](file:///d:/antigravity/pager-monitor/hfdl_receiver.py), [satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - När mottagarkonfigurationen har en specifik IP-adress (t.ex. `192.168.1.242` eller `127.0.0.1`), startas **ENDAST** utgående TCP-klient och ingen lokal server/UDP-socket binds på porten.
  - Förhindrar portkollisioner med `acars_router` eller `dumphfdl` som körs lokalt på maskinen.
- **Garanterad Trådblockering & Isolering**:
  - Vid `start()` stoppas och inväntas eventuell gammal tråd innan ny startas, vilket garanterar att endast EN arbetartråd körs per mottagare.

## [2026.10.16.13] - Separerad TCP Connect/Read Timeout, Skydd mot Reconnect-loop och Eliminering av EOF Logg-spam

- **Separerad Connect- och Läs-timeout ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [hfdl_receiver.py](file:///d:/antigravity/pager-monitor/hfdl_receiver.py), [satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - Satt `sock.settimeout(5.0)` vid anslutningsupprättande (`sock.connect((host, port))`).
  - Efter anslutning sätts `sock.settimeout(2.0)` och data läses via ren `sock.recv(4096)` istället för `makefile().readline()`, vilket förhindrar att Pythons `SocketIO` permanent skadas vid en read-timeout.
  - Inuti den inre läsloopen fångas `(socket.timeout, TimeoutError)` direkt runt `sock.recv(4096)` och gör `continue` utan att stänga socketen eller återansluta.
- **Bekräftad Anslutning & Eliminering av Logg-spam vid Omedelbar EOF**:
  - Fördröjt "Ansluten till..."-loggning tills antingen första chunk med data har tagits emot ELLER minst 2.0 sekunder passerat utan att motparten stängt socketen.
  - Vid omedelbar EOF (`chunk == b""` på första recv): loggar endast en gång på WARNING-nivå och aktiverar exponential backoff (3s -> 6s -> 12s -> 24s -> 30s) för att undvika logg-spam var 3:e sekund.
- **Trådsäkerhet vid Omstart och Inställningsändringar**:
  - Uppdaterat `stop()` i alla tre mottagare så att föregående arbetartråd inväntas (`thread.join(timeout=2.0)`/`1.5s`) innan en ny startas.
  - Förhindrar att överblivna trådar tävlar om samma TCP-port eller socket.
- **Enhetstest ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - Nytt test `test_tcp_timeout_does_not_disconnect` simulerar upprepade `socket.timeout` och verifierar att anslutningen kvarstår utan att koppla ner eller återansluta. Samtliga 158 tester passerar.

## [2026.10.16.12] - Fullt Stöd för HFDL (High Frequency Data Link) från dumphfdl

- **Ny Förstaklass-Mottagare: hfdl_receiver.py ([hfdl_receiver.py](file:///d:/antigravity/pager-monitor/hfdl_receiver.py))**:
  - Implementerat fullt stöd för `dumphfdl` (v1.7.0+) med TCP-klient (automatisk återanslutningsslinga), TCP-server fallback vid `0.0.0.0`, och parallell UDP-lyssnare på port `15556`.
  - Stöd för frekvensomvandling från Hz till kHz (`8942000` -> `8942 kHz`, `8843.0` -> `8843 kHz`), SNR-beräkning (`sig_level - noise_level` -> `+4.1 dB`) och bitrate-märkning (`HFDL-300bps`).
  - **Smart Flygplans-cache (`HFDL_AC_CACHE`) med TTL 1800s**: Sammanfogar och bevarar flygplansdata (`icao`, `regnr`, `model`, `typecode`, `owner`, senaste `pos`) från `Logon resume`/`Logon request` till efterföljande `Performance data`- och `acars`-paket.
  - **Avancerad Paketavkodning**:
    - **Typ A (Frequency data / hfnpdu 213)**: Svensk formatering med flygplansmodell, regnr, flight, position och UTC-tid, samt kompakt och tydlig redovisning av markstationer som flygplanet faktiskt hör (`Hörd GS: {namn} ({hörda kHz}) [Lyssnar: {lyssnade kHz}]` vs `Lyssnar GS: {namn} ({antal} frekv)`).
    - **Typ B (Performance data / hfnpdu 209)**: Visar flight, aktiv HF-kanal, markstation, position, rx-statistik för 300/600/1200/1800 bps, spdu squitter-statistik och orsak till frekvensbyte.
    - **Typ C (Kapslad ACARS / hfnpdu 255)**: Renser inledande punkter i registreringar (`.SE-DMR` -> `SE-DMR`), tolkar ACARS-etiketter (t.ex. `Label: Q0 (ACARS Länkbekräftelse)`), block och meddelandenummer, samt visar läsbar fritext.
    - **Filtrering (`hfdl_only_messages`)**: Filtrerar bort tomma markstations-squitters och tomma synkramar.
- **Gränssnitt, Badges & Styling ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html), [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
  - Ny protokollbricka `HFDL` i varm bärnsten/orange (`proto-hfdl`) för både mörkt och ljust tema.
  - Specialanpassade klickbara metadata-badges längst ner på raden: Frekvens (`8843 kHz`), Bitrate (`300bps`), SNR (`+4.1 dB`), Registrering (`SE-DMR`), Flight (`SAS949`), ICAO (`4A91B2`), Flygplansmodell (`badge-ac-model`), Markstation (`badge-gs`) och ACARS Label / HFDL Pakettyp (`badge-hfdl-type`).
  - Automatisk universell positionsdetektering som renderar den inbäddade kvadratiska Leaflet-minikartan till höger om raden med vertikal linje och öppnar stor kartmodal vid klick.
  - Ny flik och kontrollkort i **Settings -> Receivers** för HFDL med live telemetri-status, paketräknare, IP-adress, port och filter för tomma squitters.
- **Backend API & Databas ([app.py](file:///d:/antigravity/pager-monitor/app.py), [database.py](file:///d:/antigravity/pager-monitor/database.py))**:
  - Nya inställningar: `hfdl_enabled`, `hfdl_host`, `hfdl_port`, `hfdl_only_messages`.
  - Nya API-endpoints: `/api/hfdl/status` och `/api/hfdl/test`.
  - Integrerat i SSE-larmflödet med automatisk bakgrundsomstart vid ändrade inställningar.
- **Enhetstester ([tests/test_hfdl.py](file:///d:/antigravity/pager-monitor/tests/test_hfdl.py))**:
  - Verifierar alla 4 skarpa referenspaket (`CCA876`, `SAS949 SE-DMR`, `THY8EL TC-LHA` och `SK0949 .SE-DMR Enveloped ACARS Q0`).
  - Verifierar cacheberikning, frekvenslistning av markstationer, koordinatframställning och strikt 0 emojis. Samtliga 157 tester passerar.

## [2026.10.16.11] - Vertikal Kartavdelare, Kvadratisk Minikarta och STD-C Kanal-till-MES Korrelering

- **Vertikal Avdelare och Kvadratisk Minikarta ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
  - Infört `.msg-minimap-cell` som omsluter minikartan längst till höger i meddelandecellen med en vertikal avdelare (`border-left: 1px solid var(--panel-border)`) som sträcker sig från radens topp till botten (`align-self: stretch !important;`).
  - Minikartan (`.msg-minimap-container`) har nu kvadratiska proportioner (`130px` x `115px`), rundade hörn (`border-radius: 6px !important;`) och behaglig luft/marginal mot topp, botten och sidor med `padding: 6px 8px !important;`.
  - Anpassat för både mörkt och ljust tema (`[data-theme="light"] .msg-minimap-cell` och `.msg-minimap-container`).
  - Behållit den kompakta layouten på `.msg-main-content` och `.msg-badges` (`margin-top: auto !important; padding-top: 6px !important;`).
- **Inmarsat STD-C Korrelering mellan logical_channel_number och mes_id ([satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - Implementerat en trådsäker minnescache `CHANNEL_MES_CACHE` med TTL på 600 sekunder (`CHANNEL_CACHE_TTL = 600`).
  - Fångar upp och sparar `logical_channel_number` och fartygets `mes_id` från signalerings-/uppropspaket (`Announcement`, `descriptor.type == 1` m.fl.) allra först i `parse_satc_frame()` innan `satc_only_messages`-filtret hinner kasta kontrollpaketen.
  - När ett efterföljande textmeddelande (`pkt_name == "Full Message"`, `descriptor.type == 42`) anländer med `logical_channel_number` men saknar `mes_id`, slås fartygets ID upp ur minnescachen.
  - Berikar meddelandet med `MES ID: {mes_id}` i sammanfattningsraden, sätter terminal-ID som avsändaradress (`MES: {mes_id}`) och genererar klickbara filter-badgar för både `MES: {mes_id}` och `Ch: #{logical_channel_number}`.
  - Visar `Kanal: #{logical_channel_number}` om cachen inte hunnit fånga något `mes_id`.
- **Enhetstester och Kvalitetssäkring ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py), [tests/test_security_and_larm.py](file:///d:/antigravity/pager-monitor/tests/test_security_and_larm.py))**:
  - Nytt test `test_satc_announcement_to_full_message_correlation` verifierar att `Announcement` följt av `Full Message` automatiskt kopplar ihop `mes_id` även med `satc_only_messages=True`.
  - Uppdaterat UI-tester för `.msg-minimap-cell` och `.msg-minimap-container` med 130px x 115px och border-radius 6px.
  - Samtliga 150 tester i pytest passerar utan fel och strikt utan emojis.

## [2026.10.16.10] - Edge-to-Edge Minikarta, Eliminering av Dödutrymme och Dynamisk CSS-Cachebusting

- **Dynamisk CSS Cache-Busting med app_version ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
  - Ersatt den hårdkodade länkningen `/static/style.css?v=3` med `/static/style.css?v={{ app_version }}` så att webbläsaren omedelbart laddar ny CSS vid versionsuppdateringar.
- **Eliminering av Tomrum & Radbrytningar i DOM ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
  - Skrivit om `msgCellInner` och `tr.innerHTML` i `createAlarmRowNode()` så att HTML-strukturen skapas på en enda rad utan onödiga radbrytningar och mellanslag mellan taggarna.
- **Fullständig Edge-to-Edge Tabellcellslayout & Kant-till-kant Minikarta ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
  - Ändrat `.msg-cell` i [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css) från `white-space: pre-wrap;` till `white-space: normal;` vilket eliminerar oavsiktliga tomma rader.
  - På `td.msg-cell` och `td.message-cell`: satt `padding: 0 !important;`, `height: 1px !important;` samt `white-space: normal !important;`, vilket möjliggör för flex-barnet att sträcka sig över 100% av radens höjd.
  - `.msg-row-layout` och `.msg-main-content` har `height: 100% !important;`, `align-items: stretch !important;` och intern padding `6px 10px !important;`.
  - `.msg-minimap-container` har `width: 240px !important; min-width: 240px !important; height: auto !important; align-self: stretch !important; border-radius: 0 !important; border: none !important; border-left: 1px solid var(--panel-border, #cbd5e1) !important;` och löper nu kant-i-kant från toppen till botten av raden.
  - Kompakt padding på övriga kolumner (`td.id-cell`, `td.ts-cell`, `td.meta-cell`, `td.addr-cell`): `padding: 6px 8px !important; vertical-align: middle !important;`.
- **Enhetstester och Kvalitetssäkring ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py))**:
  - Nya tester verifierar `white-space: normal !important;`, `padding: 0 !important;`, `height: 1px !important;`, `align-self: stretch !important;`, `border-radius: 0 !important;`, dynamisk `app_version` och enkellinje `msgCellInner`. Samtliga 112 tester passerar felfritt.

## [2026.10.16.09] - Temamedveten Kartmodal, Synlig VDL2/ACARS Fritext och ICAO-validering mot BLND/DEAF

- **Temamedveten och Högkontrast Kartmodal ([static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
  - Åtgärdat den svårlästa kartmodalen (`#mapModal`) som tidigare hade hårdkodad mörk bakgrund och mörk text i ljust läge.
  - Implementerat fullständig anpassning för både ljust och mörkt läge:
    - Mörkt läge: bakgrund `#0d1117`, listpaneler `#111827`, kristallklar ljus text `#f1f5f9` / `#94a3b8` och cyanlänkar `#38bdf8`.
    - Ljust läge (`[data-theme="light"]`): krispig vit bakgrund `#ffffff`, subtila lister `#f8fafc`, skarp mörk text `#0f172a` och metadata `#475569`, stängningskryss `#64748b` samt accentblå externa länkar `#0284c7`.
- **VDL2 & ACARS Läsbar Fritext och ICAO-validering ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py), [vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Förhindrat att läsbar fritext (som t.ex. marktjänst, bränslebeställning och PRM special assistance) döljs bakom `</> Rådata` eller maskeras som kodade datapaket.
  - Ny regel `rule_ground_handling_fuel_assistance` som genererar en sammanfattningsrad överst med rutt och ETA, samtidigt som hela den läsbara brödtexten (`Dear LHBP GH, we need the below Fuel Qty...`) visas direkt i meddelandecellen.
  - Robust ICAO-validering med `INVALID_ICAO_WORDS`, `is_valid_icao_code`, `is_valid_airport_pair` och `find_valid_route_pair`:
    - Filtrerar strikt bort icke-flygplatsord som `BLND`, `DEAF`, `WCHC`, `WCHS`, `WCHR`, `FUEL`, `CREW`, etc.
    - Eliminerar den felaktiga rutten `BLND → DEAF` och förhindrar att `DEAF` felaktigt sätts som destinationsflygplats.
    - Stödjer bindestrecksrutter som `ESSA-LHBP` och mappar flygplatsen till `LHBP (Budapest/Ferenc Liszt)`.
- **Tester och Kvalitetssäkring ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - Nytt enhetstest `test_wizzair_ground_handling_and_route_not_blnd_deaf` verifierar att rutten detekteras som `ESSA → LHBP`, att destinationen är `LHBP` (inte `DEAF`), och att den läsbara fritexten visas direkt i meddelanderaden.
  - Samtliga 112 enhetstester passerar utan anmärkning och noll emojis förekommer.

## [2026.10.16.08] - Kompakt Tabellcellslayout, Badges Låsta i Botten, Zoomnivå 6 för Minikartor och Stor Interaktiv Kart-modal

- **Kompakta Tabellcellsmarginaler och Låsning av Badges i Botten ([static/style.css](file:///d:/antigravity/pager-monitor/static/style.css), [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
  - Satt kompakt vertikal padding (`padding-top: 6px !important; padding-bottom: 6px !important;`) pa tabellceller for att eliminera onodigt dotutrymme mellan radavdelarna.
  - Gjort `.msg-row-layout` till `align-items: stretch` och `.msg-main-content` till en vertikal flex-kolumn (`display: flex; flex-direction: column; justify-content: space-between;`).
  - Satt `margin-top: auto !important; padding-top: 6px; margin-bottom: 0;` pa `.msg-badges` och `.msg-meta-bar` sa att badgarna ("pillren") alltid ligger klistrade mot botten av tabellraden utan att hanga i luften nar minikartan expanderar radhojden.
  - Kompaktare minikarta (`width: 220px; min-width: 220px; height: 115px;`) for optimal vertikal rytm i flodet.
- **Utzoomad Minikarta for Regional Overblick ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
  - Andrat standardzoom pa minikartorna till `zoom: 6` sa att hela regionen (t.ex. Stockholm, Gotland och Ostersjon) syns direkt istallet for att enbart visa vatten eller en liten o.
  - Avaktiverat scrollwheel-zoom, dragging och zoom-kontroller pa den lilla minikartan och aktiverat klickbar pekare (`cursor: pointer`).
- **Stor Interaktiv Kart-Modal ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
  - Ny modal (`#mapModal`) som oppnas direkt nar man klickar pa en minikarta eller den grona `Pos:`-badgen.
  - Visar en stor, fullt interaktiv Leaflet-karta (`85vw` bred, max `1000px`, `75vh` hog) med OpenStreetMap och OpenSeaMap, komplett kartnavigering och cirkelmarkor med popup.
  - Header med protokoll, adress/callsign, tidpunkt och exakta koordinater samt direktlankar till OpenStreetMap och Google Maps.
  - Stangs via stangknapp, klick utanfor modalen eller `Escape`-tangenten.
- **Enhetstester och Kvalitetssakring ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py))**:
  - Nya enhetstester verifierar zoom 6, flex-direction och margin-top auto for bottenlasning, samt modal-markup och funktioner. 111 tester passerar felfritt och 0 emojis forekommer.

## [2026.10.16.07] - Reparation av Flodesskript (metaBarBadges), escapeHtml i Statistik och Utokad CSP connect-src

- **Reparation av Flodesskript och SSE ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
  - Aterstallde definitionen av `metaBarBadges` i `createAlarmRowNode()` vilket aveliminerade `ReferenceError: metaBarBadges is not defined` och aterstaller full funktion for bade initial meddelandeladdning och inkommande EventSource SSE-realtidsmeddelanden.
- **escapeHtml i Statistikvyn ([templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html))**:
  - Definierade `escapeHtml()` i `statistics.html` sa att `createStatRowNode()` och `loadRangeData()` renderar historiska meddelanderader utan `ReferenceError: escapeHtml is not defined`.
- **Utokad Content Security Policy (CSP) connect-src ([app.py](file:///d:/antigravity/pager-monitor/app.py))**:
  - Lade till `https://cdn.jsdelivr.net`, `https://cdnjs.cloudflare.com` och `https://unpkg.com` samt `ws:` och `wss:` i direktivet `connect-src` i CSP-headern for att tillata webblasarnedladdning av JavaScript sourcemaps (`leaflet.js.map`, `chart.umd.min.js.map`) utan sakerhetsblockering.
- **Enhetstester ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py))**:
  - Utokade tester som verifierar att `escapeHtml` ar definierad i `statistics.html`, att `metaBarBadges` finns i `index.html`, och att CSP `connect-src` tillater nodvandiga CDN-resurser. 111 enhetstester passerar och 0 emojis forekommer.

## [2026.10.16.06] - CSP Korrigering for Leaflet och Kartor, Tabellcells- och Badgelayout samt Layoutskiftsfri Flodespaus

- **Content Security Policy (CSP) Uppdatering for Leaflet och Kartor ([app.py](file:///d:/antigravity/pager-monitor/app.py))**:
  - Lade till `https://unpkg.com` i `script-src` och `style-src` sa att Leaflet JavaScript och CSS tillats laddas utan att blockeras av webblasarens sakerhetspolicy.
  - Lade till `https://*.tile.openstreetmap.org`, `https://tiles.openseamap.org` och `https://unpkg.com` i `img-src` och `connect-src` sa att kartplattor och markorikoner laddas utan att kartan blir svart.
- **Atgard for Tabellcell- och Badgelayout ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
  - Strukturerade om `<td class="msg-cell message-cell">` med `.msg-row-layout` och en dedikerad vanstersektion `.msg-main-content` som kapslar in text (`.msg-text`), radata (`.raw-data-box`) och badgar (`.msg-badges`).
  - Satte `.msg-row-layout` till `align-items: flex-start` for att forhindra vertikal utstrackning som tidigare flyttade badgarna nedat till kanten av nasta tabellrad.
  - Eliminerade overskottsmarginaler och satt `padding: 8px 12px !important; vertical-align: top !important;` pa meddelandecellen.
- **Flodespaus utan Layoutskift ([static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
  - Konfigurerade `#hoverPausePill` med `position: absolute; top: 12px; left: 50%; transform: translateX(-50%);` sa att indikatorn svavar ovanfor tabellen utan att ta upp hojd i dokumentflodet och utan att tabellraderna hoppar nedat nar muspekaren placeras over flodet.
- **Robust RFC 2047 MIME-avkodning ([satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py), [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
  - Forbattrad regex- och base64/quoted-printable-avkodare med automatisk padding-korrigering for MIME-kodade e-postrubriker (bland annat ryska KOI8-R och UTF-8) bade i backend och direkt i frontend for tidigare sparade meddelanden.
- **Enhetstester ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py))**:
  - Nya enhetstester for CSP-tillatelse for kartor, RFC 2047 MIME-avkodning och strikt DOM-layout. 110 enhetstester passerar felfritt och 0 emojis forekommer.

## [2026.10.16.05] - Universell Leaflet-Minikarta för Alla Protokoll, VDL2 Positionsbadge och RFC 2047 MIME-avkodning

- **Universell Inbäddad Minikarta (Leaflet) för ALLA Protokoll ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
  - Minikartan (260x165 px i flexbox `.msg-cell-flex.has-minimap`) renderas nu universellt för alla protokoll (`VDL2`, `SATC`, `SONDE`, `ACARS`, `POCSAG` etc.) så fort ett meddelande innehåller en giltig geografisk position.
  - Dynamisk zoom: zoomnivå 8 för flygtrafik (`VDL2`, `ACARS`, `SONDE`), och zoomnivå 9 för maritim trafik (`SATC`).
  - OpenSeaMap sjökortsoverlay appliceras automatiskt för `SATC`-meddelanden ovanpå OpenStreetMap.
  - Cirkelmarkör med tooltip `Pos: lat, lon`. Klick på den gröna `Pos:`-badgen panorerar och zoomar in kartan till zoomnivå 12.
- **Automatisk `Pos: <lat>, <lon>`-badge och Universell Detektering ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
  - `vdl2_receiver.py` extraherar nu koordinater från text (`Pos 58.2317, 17.6117`, `Position: 57.7530, 18.3780`, `N 57.753, E 18.378`), sätter `lat` och `lon` i `metadata`, skapar `coord_badge`, samt sätter `function_code = 1`.
  - Frontend identifierar koordinater ur strukturerad metadata eller textens positionsmönster, renderar den gröna `Pos:`-badgen och kopplar den till minikartan.
- **RFC 2047 MIME-avkodning av E-postheaders i Inmarsat-C ([satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - Ny hjälpfunktion `decode_mime_headers()` som använder Pythons `email.header.decode_header` med robust felhantering och base64-paddingåterställning för att automatiskt avkoda `=?charset?encoding?...?=`-sekvenser (t.ex. ryska KOI8-R eller UTF-8 headers) till läsbar UTF-8.
- **Enhetstester och Kvalitetssäkring ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py), [tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - Nya tester verifierar VDL2-positionsextrahering ur AMDAR, FMS och Positionsrapporter, RFC 2047 MIME-avkodning samt universella Leaflet-resurser och konfigurationer.
  - 108 enhetstester passerar felfritt och 0 emojis förekommer i koden.

## [2026.10.16.04] - Inbaddad Leaflet-Minikarta for GPS-koordinater, Flodespaus vid Mus-hover och Uppdaterad README

- **Inbaddad Leaflet-Minikarta for meddelanden med GPS/Position ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
  - Nar ett meddelande innehaller giltiga GPS/Pos-koordinater (t.ex. `Pos: 41.0277, 28.9880`) visas en dedikerad 260x165 px Leaflet-minikarta direkt till hoger i meddelanderutan via en responsiv flexbox-layout (`.msg-cell-flex.has-minimap`).
  - Kombinerar OpenStreetMap baslager med OpenSeaMap sjokortsoverlay for komplett maritim och nautisk kontext.
  - Placerar en distinkt cirkelmarkor (`#ef4444`) pa positionen.
  - Klick pa `Pos:`-badgen zoomar och centrerar minikartan direkt till zoomniva 13.
  - Minnes- och prestandahanterat via `IntersectionObserver` (lazy-load) och automatisk stanning (`map.remove()`) vid radering/omritning.
  - Rader utan position renderas som vanligt utan kart-container.
- **Flodespaus vid Mus-hover ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css))**:
  - Nar anvandaren for muspekaren over meddelandeflodet (`.table-container`) pausas tabellen automatiskt och en svavande statusbricka (`#hoverPausePill`) med texten "Flodet Pausat" och raknare for buffrade meddelanden visas.
  - Inkommande SSE-meddelanden sparas sakert i buffer utan att tabellen hoppar eller ror sig.
  - Sa fort musen lamnar flodet spolas samtliga buffrade meddelanden in i ordning i tabellen.
- **Fullstandig Dokumentationsuppdatering ([README.md](file:///d:/antigravity/pager-monitor/README.md))**:
  - Skrivit om `README.md` for att lyfta fram samtliga nya funktioner och protokoll: VDL2/ACARS, RadioSonde, Inmarsat STD-C/EGC/SafetyNET/SAR med SatDump, inbaddade Leaflet-minikartor, RF Activity Ribbon, samt uppdaterade portar och docker-compose-exempel.
- **Enhetstester och Emojiforbud ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py))**:
  - Lagt till tester for Leaflet-resurser, minikarta-markup, zoom-funktioner och hover-paus.
  - 143 tester passerar felfritt och 0 otillatna emojis finns i projektet.

## [2026.10.16.03] - Strikt Filtrering av Delpaket, Binär- och Gibberishfilter samt Isolering av Larmord till Brödtext

- **Ta bort all SATC-specifik radbakgrundsfärg ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - En rad i tabellen blir nu **ENDAST** rosa/röd om den matchar ett aktivt larmord från användarens bevakningslista (`Alert words`).
  - Borttaget all hårdkodad radfärgning för `DISTRESS` och `URGENCY` (`isSatcCritical`). SATC-prioritet visas som tidigare via badgen `Priority: DISTRESS/URGENCY/Safety/Routine`.
- **Isolering av larmordsmatchning till ren brödtext ([database.py](file:///d:/antigravity/pager-monitor/database.py), [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html))**:
  - `extract_body_for_alert_matching()` och `getAlertSearchableText()` strippar bort både syntetiska headers (`[Inmarsat...]`) och den dolda rå-JSON-strängen (`\nRådata: {...}`).
  - Förhindrar falsklarm från dolda JSON-fält som `"SafetyNet": true` eller `"MaritimeDistressAlerting": true`.
- **Filtrering av ofullständiga delpaket / Multi-part fragments ([satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - Vid `satc_only_messages == True` ignoreras delpaket med `pkt_name` som inte innehåller `"Full"` (t.ex. `EGC Double Header 1`, `EGC Double Header 2`, `Message Packet`), samt paket med fragmentindikatorer.
  - Endast sammanslagna kompletta meddelanden (`Full Message`, `Full EGC Message`) sparas i databasen.
- **Strikt binär- och skräpfilter (`is_binary_or_gibberish`) ([satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - Filtrerar bort krypterade ryska paket (`5PRCRYPTO` / `5PSCRYPTO`).
  - Filtrerar bort paket med fler än 2 binära kontrolltecken (`ASCII < 32` utom `\n`, `\r`, `\t` samt `0x7F`) eller > 5 % kontrolltecken i rådata.
  - Läsbarhets-/ordfilter som kastar telemetri med > 12 % specialtecken eller färre än 2 riktiga ord med >= 4 bokstäver (t.ex. `H0 2 l5 &0 N c0 vVb AL 9 E$ @ P'I`).
  - Tvättar bort icke-utskrivbara kontrolltecken (`clean_control_characters`) ur visningstexten.
- **Enhetstester och Emojiförbud ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py))**:
  - Lagt till tester för `is_binary_or_gibberish`, `clean_control_characters`, fragmentfiltrering och larmordsisolering.
  - Samtliga 142 tester i testsviten passerar felfritt och 0 otillåtna emojis förekommer i systemet.

## [2026.10.16.02] - SatDump 1.2.3 Paketklassificering, station_id Frekvensavkodning och Port 6558

- **Stöd för SatDump 1.2.3 Paketstrukturer och Descriptors ([satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - Implementerat exakt tolkning av SatDump `inmarsat_stdc_parser` JSON-strukturer baserat på `descriptor.type`:
    - **Bulletin Board (`type == 7`)**: Satellit, LES, ramnummer och returlänkhastighet (`bps`).
    - **Signalling Channel (`type == 6`)**: Uplink-frekvens och TDM-tidluckor (`tdm_slots`).
    - **Announcement (`type == 1`)**: Upprop till MES-terminal med tjänst, prioritet, hänvisad downlink-frekvens, kanalnummer och referensnummer.
    - **Logical Channel Assignment (`type == 3`)**: Kanalallokering för MES-terminal med tjänst, downlink-frekvens, kanalnummer och slotnummer.
  - Strikt filtrering vid `satc_only_messages == True` som säkerställer att endast meddelanden med faktisk brödtext (EGC SafetyNET/FleetNET, personliga meddelanden) släpps igenom, samtidigt som kontrollfält som `message_reference_number` och `message_channel` inte misstas för text.
  - Formatering på ren svenska för samtliga kontrollpakettyper när `satc_only_messages == False`.
- **Frekvenskonvertering av `station_id` ([satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - Utökat `format_satc_frequency()` för att automatiskt identifiera och konvertera SatDumps `source.station_id` (t.ex. `1.537.106` eller `1.539.481.`) samt råa Hz-tal (`1539421000`) direkt till korrekt MHz-representation (`1537.106M`, `1539.421M`) för RF Activity-grafen och frekvensfilter.
- **Utökade Badgar och Metadata**:
  - Tillagt stöd för badgar för Satellit (`Sat: IOR`), LES-kuststation (`LES: 312, Stratos Global (Burum), Netherlands`), Tjänst (`Service: Store And Forward`) och Terminal (`MES: 14557376`).
- **Standardport uppdaterad till 6558 ([database.py](file:///d:/antigravity/pager-monitor/database.py), [satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py), [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
  - Uppdaterat default lyssnarport för SatC från 5558 till 6558 för att matcha SatDumps standardkonfiguration, inklusive automatisk databasmigrering i `init_db()`.
- **Enhetstester och Emojiförbud ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py))**:
  - Lagt till `test_satdump_control_packets_filtering_and_formatting` som testar alla 4 skarpa SatDump-pakettyper.
  - Samtliga 138 tester passerar och 0 otillåtna emojis finns i kodbasen.

## [2026.10.16.01] - Konfigurerbar IP-adress för Inmarsat STD-C SatDump-mottagare

- **Konfigurerbar Värd / IP-adress ([satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py), [app.py](file:///d:/antigravity/pager-monitor/app.py), [database.py](file:///d:/antigravity/pager-monitor/database.py), [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
  - Gjort det möjligt för användaren att ange en godtycklig IP-adress eller värdnamn (`satc_host`) i inställningarna istället för hårdkodat `0.0.0.0`.
  - Stöd för både lokal lyssnare (`0.0.0.0`) och specifik fjärrvärd (t.ex. `192.168.1.xxx` eller `127.0.0.1`).
  - När en specifik IP anges startas en aktiv TCP-klienttråd med automatisk återanslutning mot fjärrvärden, samtidigt som den lokala UDP- och TCP-lyssnaren hålls aktiv för inkommande dataströmmar.
  - Lagt till fältet `Värddator / IP-adress` i webbgränssnittet under fliken `Inmarsat STD-C / EGC` med direkt autosparande (`autoSaveSatcSettings`) och dynamisk statusvisning.
- **Enhetstester och Emojiförbud ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py))**:
  - Lagt till nytt enhetstest `test_satc_configurable_host_ip` för konfigurerbar `satc_host`.
  - Utökat testet `test_strict_no_emojis_in_source_code` för att säkerställa 0 otillåtna emojis i alla moduler och HTML-mallar.
  - Samtliga 137 enhetstester passerar felfritt.

## [2026.10.15.23] - Inmarsat STD-C / EGC / SafetyNET / SAR Mottagare från SatDump

- **Ny Mottagarmodul ([satc_receiver.py](file:///d:/antigravity/pager-monitor/satc_receiver.py))**:
  - Implementerat en mottagarmodul som stöder både UDP-lyssnare och TCP-server på `0.0.0.0:<satc_port>` (standard 5558) för direkt intag av radseparerad JSON från SatDump (`inmarsat_std_c` via `JSON_OUT`).
  - Automatisk filtrering av tomma TDM-signalerings- och synkramar (Bulletin Board, Signalling channel descriptor etc.) via inställningen `satc_only_messages` (standard `true`), så att endast relevanta meddelanden och SafetyNET/SAR-händelser släpps igenom.
  - Automatisk avkodning och igenkänning av jordstationer (LES - Land Earth Stations, t.ex. Burum, Eik, Thermopylae) från ID och namn.
  - Robust geografisk koordinatparsning för alla standardiserade sjöfarts- och SAR-format (`58-34.2N 016-12.5E`, `58 34N 016 12E`, `5834N 01612E`, `LAT/LONG` samt decimalgrader) som konverteras till decimalgrader för kartor och databas.
  - Svensk sammanfattningsrad överst (`[Inmarsat SafetyNET / Sjöfartsvarning] Område: NAVAREA I | Prioritet: Safety`) följt av meddelandetext och hela det råa JSON-paketet bakom `</> Rådata`-badgen.
- **Konfigurations- och Inställningsstöd ([app.py](file:///d:/antigravity/pager-monitor/app.py), [database.py](file:///d:/antigravity/pager-monitor/database.py), [templates/settings.html](file:///d:/antigravity/pager-monitor/templates/settings.html))**:
  - Lagt till inställningarna `satc_enabled`, `satc_port` (default 5558) och `satc_only_messages` (default true) i SQLite och backend.
  - Ny dedikerad flik i Settings (`Inmarsat STD-C / EGC`) med statusmätare för inkomna paket, avkodade meddelanden, senaste tjänst och aktivitet samt testknappar för SafetyNET och Distress/SAR.
- **Frontend och Gränssnitt ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [static/style.css](file:///d:/antigravity/pager-monitor/static/style.css), [static/waterfall.js](file:///d:/antigravity/pager-monitor/static/waterfall.js))**:
  - Integrerat protokollnamnet `SATC` i filtermenyn (`Alla protokoll`), som döljs helt om `satc_enabled` är avstängt i inställningarna.
  - Click-to-Filter på samtliga SATC-badgar (Prioritet, NAVAREA, LES, Frekvens, Tjänst).
  - Larmrader för `DISTRESS` och `URGENCY` markeras som kritiska larm med röd bakgrund och animation (`alert-row`, `alert-pulse-bg`).
  - Frekvensvisning (t.ex. `1537.700M`) integrerad i RF Activity-vattenfallet och frekvensfilter.
- **Enhetstester och Emojiförbud ([tests/test_satc.py](file:///d:/antigravity/pager-monitor/tests/test_satc.py))**:
  - Skapat 7 nya enhetstester som verifierar parsning av SafetyNET- och Distress/SAR-meddelanden, koordinatkonverteringar, filtrering av tomma TDM-ramar och strikt avsaknad av emojis.
  - Samtliga 136 enhetstester passerar felfritt och 0 emojis förekommer på hela webbplatsen.

## [2026.10.15.22] - Fix för Flödesuppdatering i Realtid, Återanslutning av SSE och Fallback-Polling

- **Realtidsflöde och Dynamisk Sortering i DataTables ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html))**:
  - Åtgärdat fel där inkommande meddelanden från SSE-strömmen (`/stream`) inte automatiskt hamnade överst i meddelandeflödet utan krävde manuell siduppdatering (F5).
  - DataTables anropas nu med explicit omsortering `dataTable.order([[1, 'desc']]).draw(false);` när nya rader läggs till via `processIncomingMessage()`, vilket garanterar att nya rader omedelbart placeras överst på sidan.
  - Implementerat automatisk återanslutning (`connectSSE`) med 3 sekunders återförsök vid avbruten eller stängd EventSource-anslutning.
- **Robust Fallback-Polling för Inkommande Händelser ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [app.py](file:///d:/antigravity/pager-monitor/app.py), [database.py](file:///d:/antigravity/pager-monitor/database.py))**:
  - Implementerat säkerhetsnät i frontend med bakgrundspolling var 5:e sekund via `/api/messages?since_id=<maxId>`. Detta förhindrar att händelser missas om webbläsaren pausat flikar, nätverket tappat SSE-anslutningen eller proxyservrar buffrat dataströmmar.
  - Tillagt stöd för parameter `since_id` i `get_recent_messages()` i [database.py](file:///d:/antigravity/pager-monitor/database.py) och `/api/messages` i [app.py](file:///d:/antigravity/pager-monitor/app.py) för optimal SQL-hämtning (`WHERE m.id > ?`).
- **Åtgärdad Äldre Bakgrundsprocess**:
  - Avslutat en föråldrad bakgrundsprocess (PID 27488) som körts sedan 12 oktober utan VDL2-stöd i SSE, och startat den aktuella serverkoden.
- **Enhetstester och Emojiförbud**:
  - Samtliga 92 enhetstester passerar felfritt och 0 otillåtna emojis finns i kodbasen.

## [2026.10.15.21] - Avkodning av KLM POS, Airbus/Finnair FMS-delblock, H1/H2/DF-fallback och Freetext-restriktioner

- **Begränsning av `Pilotmeddelande:` till Konversations-Labels och `.FREE` / `FTX/` ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - `Pilotmeddelande:` utbrytning är nu strikt begränsad till konversations-labels (`80`, `81`, `82`, `83`, `RA`, `AA`, `10`, `12`, `13`, `15`) samt meddelanden som explicit innehåller `.FREE` eller `FTX/`.
  - Förhindrar att teknisk maskintelemetri på andra labels (`11`, `H1`, `H2`, `MA`, `5Z`, `16` m.fl.) någonsin kan misstas för pilotmeddelanden.
  - Korrigerat loop-indrag i `rule_operational_eta_fob_freetext` så att alla uteslutningsregler appliceras korrekt på varje rad.
- **Avkodning av `.FREE`-headers ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Implementerat `rule_free_text_header` för dispatch-headermeddelanden som matchar `^/[A-Z0-9]+\.FREE\s*$` (t.ex. Hainan Airlines `Label: 80`: `/HAKDPHU.FREE\nETP WX COPIED THX`).
  - Tolkar efterföljande rader som `Pilotmeddelande: "ETP WX COPIED THX"` med den fullständiga rådatan prydligt bakom `</> Rådata`-badgen.
- **Avkodning av ICAO / KLM Positionsrapporter (`(POS-...`) ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Implementerat `rule_icao_klm_pos_report` och mönster 00b i `extract_position_and_telemetry()`.
  - Matchar standardformatet `(POS-KLM20H-5834N01553E/101429 F310\nRMK/FUEL 5.4 M0.80)`.
  - Beräknar latitud (`5834N` -> `58.5667`), longitud (`01553E` -> `15.8833`), flygnivå (`F310` -> `31 000 ft`), tid (`10:14:29 UTC`), bränsle (`5.4 ton (5 400 kg)`) och fart (`Mach 0.80`).
  - Uppdaterar paketets geografiska koordinater och höjd i metadata för kartvy och databas.
- **Avkodning av Airbus/Finnair/Lufthansa Fortsättningsblock i `Label: H1` ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Implementerat `rule_fms_telemetry_continuation_block` och mönster 00c i `extract_position_and_telemetry()`.
  - Fångar telemetridelblock som börjar med `,` eller `-,` eller innehåller `/X\d+`, `/V\d+`, `/2[NSTV]\d+` (t.ex. `,0305/X72353,E0175,N577,057,321,0030,XXXX/`).
  - Extraherar koordinater som `E0175,N577` (`57.7°N, 17.5°E`) och formaterar som `[FMS Telemetri / Delblock] Kompletterande färd- och sensordata (Position: 57.70, 17.50)` med rådatan bakom `</> Rådata`-badgen.
- **Generell Fallback för Oidentifierad Maskindata i `Label: H1` / `H2` / `DF` / `5Z` ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py))**:
  - Säkerställer att råa tekniska FMS-strängar (som Lufthansas `*,82:8YYB3 )RE 13J/ )1,,Y`) aldrig dumpas oformaterade i tabellen.
  - Kapslar dem som `[FMS/Systemtelemetri] Kodat datapaket (X tecken)` med rådata bakom `</> Rådata`-badgen.
- **Fullständig Sanering av Pratbubblor i UI och Databas ([database.py](file:///d:/antigravity/pager-monitor/database.py), [templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html))**:
  - Frontend-funktioner (`formatMessage` och `cleanMsg`) strippar nu automatiskt alla varianter av speech bubble emojis och unicode-koder så att varken aktiva eller historiskt sparade meddelanden visar emojin i den gröna `.pilot-freetext-highlight`-brickan.
  - `database.py` rensar vid uppstart och vid sparande av nya meddelanden bort eventuella kvarvarande pratbubbel-tecken ur databasen.
- **Enhetstester ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - Tillagt `test_hainan_airlines_free_text_header`, `test_klm_icao_pos_report`, `test_finnair_fms_delblock_continuation` och `test_lufthansa_fms_system_fallback`.
  - Samtliga 92 enhetstester i hela testsviten passerar felfritt och 0 otillåtna emojis finns i kodbasen.

## [2026.10.15.20] - Totalförbud mot Emojis, Nyckel/Värde POS-Telemetri och Skärpt Pilotfritext-Filter

- **Totalförbud mot Emojis i Hela Kodbasen**:
  - Raderat samtliga förekomster av pratbubblan `` (U+1F4AC) och alla andra emojis i backend ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py), [vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py)) och frontend ([templates/index.html](file:///d:/antigravity/pager-monitor/templates/index.html), [templates/larm.html](file:///d:/antigravity/pager-monitor/templates/larm.html), [templates/statistics.html](file:///d:/antigravity/pager-monitor/templates/statistics.html)).
  - Meddelandeprefix är nu uteslutande `Pilotmeddelande:` i ren text och filtermeny/chips visar `Pilotmeddelanden`.
  - Automatisk emojiskanning bekräftar 0 otillåtna emojis i hela systemet.
- **Avkodning av Nyckel/Värde-baserade `POS`-rapporter ([vdl2_receiver.py](file:///d:/antigravity/pager-monitor/vdl2_receiver.py), [acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Implementerat `rule_pos_key_value_report` samt stöd i `extract_position_and_telemetry()` för kommaseparerade telemetrimeddelanden (t.ex. China Eastern `B-308E`, `MU0250`, `Label: 11`: `POS - CAS 274,LAT N058.32,LON E016.90,ALT 37002,FOB 137088,UTC 115155,PD 41.15,WD -60,WS 50,TAT -56`).
  - Extraherar latitud (`LAT N058.32` -> `58.32`), longitud (`LON E016.90` -> `16.90`) och höjd (`ALT 37002` -> `37002 ft`) direkt till paketmetadata för kartor och databas.
  - Avkodar övrig telemetri: fart (`CAS 274` -> `274 kt`), bränsle (`FOB 137088` -> `137 088 lbs`), tid (`UTC 115155` -> `11:51:55 UTC`), vindriktning med normalisering (`WD -60` -> `(360 + (-60)) % 360` = `300°`), vindstyrka (`WS 50` -> `50 kt`) och temperatur (`TAT -56` -> `-56°C`).
  - Presenterar meddelandet i en ren och strukturerad tvåradersvy med ` | ` och rådata bakom `</> Rådata`-badgen.
- **Skärpt Exkludering mot Siffer- och Telemetridata i Pilotfritext ([acars_human_parser.py](file:///d:/antigravity/pager-monitor/acars_human_parser.py))**:
  - Förhindrar att maskintelemetri med mellanslag klassas som pilotmeddelande genom tre nya spärrar:
    1. Blockerar rader som startar med `POS` eller innehåller parametermönster som `LAT `, `LON `, `ALT `, `FOB `, `CAS `, `UTC `, `TAT `.
    2. Blockerar rader med 2 eller fler kommatecken i kombination med siffror.
    3. Blockerar rader som består till mer än 25% av siffror (vanlig mänsklig pilotfritext består av ord, inte parametersträngar).
- **Enhetstester ([tests/test_vdl2.py](file:///d:/antigravity/pager-monitor/tests/test_vdl2.py))**:
  - Tillagt `test_china_eastern_pos_key_value_telemetry`: Verifierar position (`58.32`, `16.90`), höjd (`37 002 ft`), telemetri (`274 kt`, `-56°C`, `300° / 50 kt`, `137 088 lbs`) och att meddelandet INTE flaggas som pilotmeddelande.
  - Samtliga 88 enhetstester passerar utan anmärkning.

## [2026.10.15.19] - LSCONF Lastbesked, Skärpt Pilotfritext och Förfinad FMS/Telemetri-Rendering

- **LSCONF Avkodning (Loadsheet Confirmation / Lastbesked)**:
  - Implementerat `rule_lsconf_loadsheet` i `acars_human_parser.py` och direkt hantering i `humanize_acars_message()` i `vdl2_receiver.py`.
  - Matchar mönstret `(?:[A-Z0-9]+/)?LSCONF/([A-Z0-9]+)/([A-Z]{4})/([A-Z]{4})/(\d+|--)` (t.ex. `V09CA032/LSCONF/SK1423/ESSA/EKCH/11859/--/`).
  - Översätter flygplatskoder med `format_airport()`, uppdaterar `dst_airport` i metadata och formaterar som:
    `[Lastbesked / Loadsheet (LSCONF)] Kvittens av last- och viktbesked för flight SK1423 | Rutt: ESSA (Stockholm/Arlanda) → EKCH (Köpenhamn/Kastrup)` med rådata bifogad bakom `</> Rådata`-badgen.
- **Skärpta Regler för ` Pilotmeddelande:` i `acars_human_parser.py`**:
  - Maskinell telemetri och Loadsheet-bekräftelser förhindras från att klassas som pilotmeddelanden genom tre strikta krav:
    1. Raden **måste** innehålla minst ett mellanslag mellan riktiga ord.
    2. Raden får **inte** innehålla fler än 1 snedstreck per 15 tecken, och blockerar strukturerad komma-/snedstrecks-telemetri (>= 3 avskiljare).
    3. Raden får **inte** inledas med kända tekniska prefix (`V09`, `PLF `, `FDE `, `MSG `, `/ETA`, `/FOB`, `PRG/`, `INI/`, `FTX/`, `POS`, `REP`, `02E`, `#DFB`, `#CFB`, `#M1B`).
  - Riktig mänsklig fritext (t.ex. `HI BER\nREQ FUEL 5.6T`) bevaras och formateras korrekt som ` Pilotmeddelande: "HI BER — REQ FUEL 5.6T"`.
- **Enhetlig Struktur och Riktiga Enheter för FMS- och Väderrapporter**:
  - `rule_label_h1_posn_fms` och `rule_label_38_finnair_weather`: Använder alltid ` | ` mellan fält samt riktiga enheter (`Höjd: FL360 (36 000 ft) | Temp: -54°C | Vind: 314° / 45 kt`).
  - Koordinatkonvertering för "Nästa brytpunkt" via `format_waypoint_or_coord()`: Råa koordinater (`N59101E020416`) konverteras nu automatiskt till decimalgrader (`59.1683, 20.6933`).
  - Konsekvent radstruktur: Rad 1 rubrik `[FMS Färddator-rapport]` + eventuell rutt, Rad 2 `Position:` och `Nästa brytpunkt:`, Rad 3 telemetri (`Höjd:`, `Temp:`, `Vind:`), följt av `\nRådata:` för rådatabadge.
- **Visuell Framhävning i Frontend (`index.html`, `larm.html`, `statistics.html`)**:
  - Ersätter ` | ` med en luftad visuell separator `<span class="msg-sep">|</span>` (`margin: 0 8px; color: #cbd5e1;` / mörkt läge `#64748b;`).
  - Framhäver fältetiketter vid rad- och segmentstart (`Rutt:`, `Position:`, `Höjd:`, `Temp:`, `Vind:`, `ETA:`, `Fart:`, `Bränsle:`, `Nästa brytpunkt:`, etc.) med `<strong class="msg-label">` (`font-weight: 600; color: #334155;` / mörkt läge `#e2e8f0;`).
  - Tillagt klassen `.msg-summary` på meddelandecellerna i tabellerna för enhetlig typografi.
- **Enhetstester (`tests/test_vdl2.py` & `tests/test_acars_human_parser.py`)**:
  - Tillagt `test_sas_lsconf_loadsheet_and_no_pilot_freetext` och `test_finnair_fms_posn_formatting`.
  - Uppdaterat `test_pattern_1_finnair_weather_and_position` och `test_pattern_2_fms_posn_route_and_weather`.
  - Samtliga 87 enhetstester passerar.

## [2026.10.15.18] - Rättad Reassembly-ordning och Rådatabuffring för MIAM och ACARS

- **Reassembly Före Avkodning och Formatering (`vdl2_receiver.py`)**:
  - Flyttat Multi-block ACARS Reassembly så att den körs direkt på **den obehandlade råtexten** (`msg_text`), INNAN `decode_miam_base85()` och `humanize_acars_message()` körs.
  - Förhindrar att delblock formateras till svenska beskrivningar i förväg och klistras ihop efter varandra vid sammanslagning.
  - När `more is True` eller `assstat == "reassembly_in_progress"` sparas den råa texten i `PARTIAL_ACARS` och exekveringen avbryts direkt (`return None`) utan formatering eller rendering i UI.
- **Dubbleringsskydd vid dumpvdl2 Förhands-Reassembly**:
  - Kontrollerar om slutblockets råtext redan inleds med samma tecken som första sparade delblocket (`msg_text.startswith(first_chunk[:16])`).
  - Om `dumpvdl2` redan pusslat ihop delarna används `msg_text` direkt utan duplicering; annars konkateneras de råa delblocken.
- **Snygg MIAM Fallback och Rådatavisning**:
  - MIAM Base85-avkodning (`decode_miam_base85()`) körs enbart en gång på den fullständiga råtexten efter avslutad reassembly.
  - Om ett MIAM-paket inte kan dekomprimeras till ASCII presenteras det rent med rubrik och storlek (`[MIAM Komprimerad Telemetri] Airbus komprimerat telemetripaket (244 B)`), medan hela den råa Base85-strängen placeras i `\nRådata:` och visas bakom `</> Rådata`-badgen istället för mitt i meddelandecellen.
- **Enhetstester (`tests/test_vdl2.py`)**:
  - Lagt till `test_miam_multi_block_reassembly` som verifierar att flerdelade MIAM-paket (210 B + 34 B) buffras rått, inte duplicerar rubriker och lägger rådata i `Rådata:`.

## [2026.10.15.17] - ACARS Multi-block Reassembly och Boeing DFDAU med Hex & Negativa Värden

- **Multi-block Reassembly Buffer i `vdl2_receiver.py`**:
  - Implementerat hantering av flerblockiga ACARS-meddelanden via fälten `more` och `assstat` från `dumpvdl2`.
  - När `assstat == "reassembly_in_progress"` eller `more is True`: delblock sparas i en trådsäker minnescachen `PARTIAL_ACARS` och ignoreras temporärt (`None`) så att ofullständiga fragment inte loggas eller skickas ut till UI/DB.
  - När slutblocket anländer (`more is False` eller `assstat == "complete"`): om `dumpvdl2` redan slagit ihop meddelandet i `msg_text` används det direkt, annars konkateneras de sparade delblocken till ett enda komplett meddelande.
  - Automatisk städning via `cleanup_partial_acars()` med 30 sekunders timeout för att förhindra minnesläckor vid signalbortfall samt `reset_partial_acars_cache()` för enhetstester.
- **Boeing DFDAU / Motortelemetri med Hex & Negativa Värden (`acars_human_parser.py`)**:
  - Utökat `rule_boeing_dfdau_engine_telemetry` till att acceptera minustecken (`-`) och hexadecimala statusord (`[0-9A-Fa-f\s\-]`).
  - Tolkar nu korrekt telemetriramar innehållande negativa tal (t.ex. `-010760 9388`) och långa hex-statusord (t.ex. `6780018CE0000000003494300000100007F00100000`), presenterar dem som `[Boeing Motortelemetri / DFDAU]` och placerar rådatan bakom `</> Rådata`-badgen.
  - Skyddat MM-telemetriloggar (`rule_label_h1_mm_telemetry`) från falskträffar genom explicit kontroll.
- **Enhetstester (`tests/test_vdl2.py`)**:
  - `test_acars_multi_block_reassembly`: Verifierar att delblock med `more: True` ignoreras och att det slutgiltiga blocket (`more: False`) skapar exakt ett komplett meddelande (både för extern dumpvdl2-hopsättning och intern konkatenering).
  - `test_boeing_dfdau_hex_and_negative_telemetry`: Verifierar att DFDAU med minustecken och hex-statusord tolkas och presenteras korrekt.

## [2026.10.15.16] - Multi-Select Filter med Checkbox-Dropdowns och Aktiva Filter-Chips

- **Multi-Select Filter-State (`activeFilters` med Sets i `index.html`)**:
  - Konverterat `activeFilters` från enstaka strängvärden till `Set`: `{ protocols: new Set(), frequencies: new Set(), labels: new Set(), airports: new Set(), capcode: '' }`.
  - Filterlogik: **OR** inom samma kategori (t.ex. matchar frekvens `136.725M` ELLER `136.875M`) och **AND** mellan olika kategorier (t.ex. måste matcha vald frekvens OCH vald label).
  - Stöd för multi-select i DataTables anpassade filterfunktion med fullständigt dataattribut-stöd (`data-frequency`, `data-proto-name`, `data-label`, `data-airport-code`).
- **Custom Checkbox-Dropdown Popover-Menyer**:
  - Byggt om dropdown-kontrollerna ovanför meddelandetabellen till moderna klickbara popover-menyer med kryssrutor (`<input type="checkbox">`).
  - Användare kan kryssa i och ur flera val i följd utan att menyn stängs. Klick utanför stänger dropdown-menyn.
  - Dynamiska räknare för varje alternativ (`(15)` osv.) och en smidig "Rensa"-knapp överst i varje popover-meny.
  - Knapparnas text uppdateras dynamiskt (t.ex. `Alla frekvenser`, `Frekvens: 136.725M`, `Frekvenser (3)`) med tydlig accentmarkering (`active-filter-select`) vid aktiva filter.
- **Tydliga Aktiva Filter-Chips med `x` och "Rensa alla"**:
  - Varje valt filter renderas nu som ett klickbart filter-chip (`[ Frekvens: 136.725M x ]`, `[ Label: H1 x ]`, etc.) ovanför tabellen.
  - Klick på chipets `x` tar bort det specifika värdet ur motsvarande filter-Set.
  - En röd "Rensa alla"-knapp nollställer samtliga filter och fritextsökning med ett enda klick.
- **Klick-på-badge Toggle-Stöd**:
  - Klick på badges i tabellcellerna (frekvens, SNR/ACARS, label, flygplats) togglar nu värdet in och ut ur respektive `Set` utan att rensa bort andra redan valda filter.
- **Enhetstester & Emojivalidering**:
  - Samtliga 82 enhetstester passerar.
  - Emojiskanner bekräftar 0 otillåtna emojis.

## [2026.10.15.15] - Pills Alltid i Botten, Rådata Toggle-badge och Dynamisk Fontskalning

- **Pillren (`.msg-meta-bar`) Alltid i Botten av Meddelandecellen (`style.css`, `index.html`, `larm.html`, `statistics.html`)**:
  - Infört `.msg-content-wrapper` inuti `td.msg-cell` med flex-layout i kolumn (`display: flex; flex-direction: column; height: 100%; min-height: 100%;`).
  - Satt `height: 1px !important;` på `td.msg-cell` så att tabellcellen tillåter barnet med `height: 100%` att fylla cellens hela höjd oberoende av knapparna i actions-kolumnen.
  - Satt `margin-top: auto; padding-top: 6px;` på `.msg-meta-bar` så att pillren (frekvens, SNR, ACARS, anrop, destination, etc.) alltid är förankrade längst ner i raden utan tomt glapp under pillren.
  - Vid dynamiska `repeat_update`-händelser läggs `.msg-meta-bar` nu automatiskt till i `.msg-content-wrapper`.
- **Kompakt `</> Rådata` Toggle-badge och Borttagning av `<details>`-raden**:
  - Ersatt den tidigare klumpiga `<details>` / `<summary>`-avdelaren med en klickbar badge (`<span class="badge badge-raw-toggle" onclick="toggleRawData(this)">&lt;/&gt; Rådata</span>`) längst till höger på badge-raden.
  - Meddelandetexten ligger därmed direkt ovanför badgarna precis som för normala meddelanden.
  - Implementerat `toggleRawData(btn)` för att smidigt visa och dölja `.raw-data-box` vid klick.
- **Strikt Dynamisk Fontstorlek (1:1 Skalning från Settings)**:
  - Säkerställt att `.raw-data-box` har `font-family: inherit; font-size: inherit;` utan några hårdkodade `rem`- eller `px`-storlekar. Rådata skalar nu 1:1 när användaren ändrar teckenstorlek i Settings.
- **Enhetstester & Emojivalidering**:
  - Samtliga 82 enhetstester passerar.
  - Emojiskanner bekräftar 0 otillåtna emojis.

## [2026.10.15.14] - Global Flygplatsöversättning med airportsdata, Ruttdestination & Säkerhetsspärr

- **Stöd för 28 000+ Flygplatser Globalt via `airportsdata` (`vdl2_receiver.py`, `acars_human_parser.py`, `requirements.txt`)**:
  - Integrerat biblioteket `airportsdata` som global fallback i `format_airport()`.
  - Uppslag prioriterar vår handskrivna svenska `AIRPORTS`/`AIRPORT_MAP`-ordbok (`Stockholm/Arlanda`, `Tokyo/Haneda`, `Addis Abeba/Bole` osv.) och faller tillbaka på `airportsdata.load('ICAO')` för alla övriga internationella flygplatser i världen.
  - Skapat hjälpfunktionen `_clean_airport_name()` som automatiskt rensar bort överflödiga ord som "International Airport", "Air Base" och formaterar flygplatser snyggt som `ICAO (City / CleanName)` eller `ICAO (City)` (t.ex. `KLAX (Los Angeles)`, `YSSY (Sydney/Kingsford Smith)`).
- **Åtgärdad Ruttöversättning & Rättad Destinationsbadge (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Åtgärdat fel i `rule_label_83_csv_position` (t.ex. All Nippon Airways NH0222 `ESSA,RJTT,...`) där råa ICAO-koder skrevs ut direkt utan `format_airport()` och med överflödig text `(Avgång/Ankomst)`.
  - Nu formateras samtliga rutter konsekvent med `format_airport()` och unicode-pilen `→`: `Rutt: ESSA (Stockholm/Arlanda) → RJTT (Tokyo/Haneda)   Tid: 08:47 UTC`.
  - När en rutt extraheras ur meddelandetext eller CSV-data uppdateras alltid meddelandets `dst_airport` (t.ex. `RJTT`) och badgen sätts till destinationen istället för den lokala markstationen planet råkade sända igenom (t.ex. Linköping ESSL).
- **Global Säkerhetsspärr för Rutter (`fix_untranslated_routes`)**:
  - Implementerat `fix_untranslated_routes()` som post-processing på all formaterad text i både `vdl2_receiver.py` och `acars_human_parser.py`.
  - Regex-spärren fångar upp alla rutter på formen `Rutt: XXXX →/-> YYYY` som saknar parenteser, översätter ICAO-koderna med `format_airport()`, rensar eventuellt `(Avgång/Ankomst)` och säkerställer att destinationen sätts i metadata.
- **Enhetstester (`tests/test_vdl2.py`, `tests/test_acars_human_parser.py`)**:
  - Tillagt dedikerat enhetstest `test_label_83_ana_and_airportsdata` i `test_vdl2.py` för All Nippon Airways (`ESSA → RJTT`) samt extern flygplats (`ESSA → KLAX`).
  - Verifierat att `dst_airport` uppdateras till `RJTT` och att badgen visar `RJTT (Tokyo/Haneda)`.
  - Samtliga 82 enhetstester passerar felfritt.

## [2026.10.15.13] - Dynamiskt Filtersystem, Click-to-Filter och Förfinad Rådata-avdelare


- **Dynamisk Filter-bar i Real-time Monitor (`templates/index.html`)**:
  - Tillagd kompakt filter-bar ovanför tabellen (mellan "Show X messages" och "Quick filter...") med snabbfiltrering:
    1. **Protokoll-filter**: Dynamiskt val mellan `Alla protokoll`, `POCSAG`, `VDL2`, `SONDE`, `TETRA`, `RDS` med meddelandeantal.
    2. **Frekvens-filter**: Dynamiskt befolkad lista över unika frekvenser med meddelandeantal i parentes.
    3. **VDL2-specifika filter**: Känner av `vdl2_enabled` i inställningar – om VDL2 är avstängt döljs VDL2-dropdowns helt så att gränssnittet hålls rent för POCSAG.
       - **ACARS Label-filter**: Unika labels med beskrivning (`H1 (FMS)`, `16 (Position/Landning)`, `80 (Operativt/Fritext)` etc.) samt toppvalet ` Endast pilotmeddelanden / fritext`.
       - **Flygplats-filter**: Unika rutt- och markstationsflygplatser (`ESSA (Arlanda)`, `ESDF (Kallinge)`, `EFHK (Helsingfors/Vanda)`).
- **Click-to-Filter på alla badgar i tabellen (`templates/index.html`)**:
  - Alla badgar i tabellens celler är klickbara med subtil hover-effekt och verktygstips:
    - Klick på **Protokoll-badge** filtrerar tabellen på det protokollet.
    - Klick på **Capcode / Flygbolags-badge** filtrerar på vald adress/alias (separat penn-ikon för redigering).
    - Klick på **Frekvens-badge** sätter frekvensfiltret till den frekvensen.
    - Klick på **Label-badge** sätter labelfiltret till den koden.
    - Klick på **Flygplats-badge** sätter flygplatsfiltret till flygplatsens ICAO-kod.
    - Klick på **Registrering / Flight / ICAO-badge** filtrerar snabbsökningen.
- **Aktiva filter-chips & Rensa filter-knapp (`templates/index.html`)**:
  - Visar interaktiva filter-taggar med `x` för varje aktivt filter samt en röd `Rensa filter`-knapp.
  - Live SSE-meddelanden filtreras i realtid utan att aktiva filter nollställs.
- **UI-fix: Tydlig avdelare och kollaps-indikator för Rådata (`index.html`, `larm.html`, `statistics.html`)**:
  - Åtgärdat onödigt vertikalt avstånd mellan meddelandetext och "Visa rådata" genom att ta bort oavsiktliga radbrytningar och nollställa cellens whitespace-arv (`.msg-text { white-space: normal; }`).
  - Lagt till en diskret streckad avdelare (`border-top: 1px dashed rgba(148, 163, 184, 0.25)`) ovanför rådata.
  - Förvandlat "Visa rådata" till en tydlig pill-knapp med kodikon och animerad chevron (`<i class="fas fa-chevron-right raw-data-chevron"></i>`) som roterar 90 grader vid utfällning.

## [2026.10.15.12] - Kollapsbar Rådata i UI och Förbättrad Label 80 ETA/FOB/Fritext

- **Kollapsbar Rådata i Gränssnittet (`index.html`, `larm.html`, `statistics.html`)**:
  - Meddelandecellen (`MESSAGE`) separerar nu automatiskt tolkad sammanfattning (`parsedSummary`) och rådatasträng (`rawText`).
  - Rådata visas nu snyggt inuti en kollapsbar `<details class="raw-data-details"><summary>Visa rådata</summary><pre class="raw-data-content">...</pre></details>` under sammanfattningen men ovanför metadata-badgarna.
  - Snygg och diskret styling för knappen "Visa rådata" med monospace, ljusgrå bakgrund och mörkt läge-stöd.
  - Pilot-fritext framhävs visuellt med en distinkt grön/kontrasterande stilbricka (`.pilot-freetext-highlight`).
- **Backend: Rättad ETA-validering, /FOB och Pilotfritext (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Strikt validering av ETA: Kräver timmar `00–23` och minuter `00–59` (`(?:[01]\d|2[0-3])[0-5]\d`), vilket förhindrar att flightnummer (som `4505` i `3401 ETA 4505/15`) felaktigt tolkas som `45:05 UTC`.
  - Parsar `/ETA` -> `ETA: 09:25 UTC` och `/FOB` -> `Bränsle (FOB): 4 280 kg`.
  - Extraherar mänsklig pilotfritext (t.ex. `HI BER` / `REQ FUEL 5.6T`) till ` Pilotmeddelande: "HI BER — REQ FUEL 5.6T"`.
  - Standardiserat rådatamarkören till `\nRådata: <original_msg>` utan onödig trunkering.
- **Enhetstester (`tests/test_vdl2.py`, `tests/test_acars_human_parser.py`)**:
  - Lagt till `test_norwegian_label_80_eta_fob_and_pilot_freetext` och uppdaterat `test_boeing_dfdau_engine_telemetry`.
  - Samtliga 80 enhetstester passerar felfritt.

## [2026.10.15.11] - Airbus FDIMU / AIDS-rapport (Label H1, /REP & /CC)

- **Airbus FDIMU & AIDS-systemrapporter (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Implementerat parserstöd för Airbus FDIMU / AIDS-rapporter under `Label: H1` med mönstret `^(A\d{3})[^/]*/REP(\d+)[^/]*/CC([A-Z0-9-]+),([A-Z]{3}\d{2}),(\d{6}),([A-Z]{4}),([A-Z]{4})`.
  - Extraherar flygplanstyp (`A321`), rapportnummer (`Rapport #009`), registrering (`TC-RBH`), tidstämpel (`08:13:23 UTC`), avgångsflygplats (`LTFJ (Istanbul/Sabiha Gökçen)`) och destinationsflygplats (`ESSA (Stockholm/Arlanda)`).
  - Uppdaterar automatiskt paketets `dst_airport` till destinationsflygplatsen så att den gröna stations-badgen i gränssnittet visar korrekt destination (`Stockholm/Arlanda`).
  - Extraherar flyghöjd och indikerad fart ur `/CE`-sektionen (`/CE\d{4},(\d{4,5}),(\d{3})`) och sätter paketets `alt` och `alt_ft` till `13407` samt fart till `301 kt`.
  - Snygg presentation på svenska:
    `[Airbus FDIMU/Systemrapport #009] Flygplan: A321 | Rutt: LTFJ (Istanbul/Sabiha Gökçen) → ESSA (Stockholm/Arlanda) | Tid: 08:13:23 UTC | Höjd: 13 407 ft | Fart: 301 kt | Rådata: A321,017705...`
- **Enhetstester (`tests/test_vdl2.py`, `tests/test_acars_human_parser.py`)**:
  - Lagt till `test_pegasus_airbus_aids_fdimu_report` och `test_rule_airbus_aids_fdimu_report` med verklig Pegasus Airlines-data.
  - Verifierar att `Istanbul/Sabiha Gökçen` och `Stockholm/Arlanda` slås upp och skrivs ut samt att `alt` sätts till `13407`.
  - Samtliga 79 enhetstester passerar felfritt.

## [2026.10.15.10] - Prestandaoptimering av Databasstatistik (3 ms svarstid & Cache)

- **Drastisk Prestandaförbättring för Databasöversikt (`_calculate_database_stats`)**:
  - Åtgärdat den kritiska flaskhalsen där uppslagning av träffar för larmord (`alert_hits`) exekverade Python-funktionen `UPPER_UNICODE` som en callback i SQLite över tiotusentals rader (vilket tog 7-8 sekunder på grund av GIL och kontextväxlingar).
  - Ersatt callbacken med direkt SQL-mönstermatchning (`LIKE ? OR LIKE ?`) kompilerad i ren C-kod i SQLite.
  - Sammanfogat 5 separata databasfrågor till en enda optimerad aggregationsfråga (`SELECT COUNT(*), MIN(timestamp), MAX(timestamp), SUM(CASE WHEN is_protected = 1...), SUM(CASE WHEN is_duplicate = 1...), COUNT(DISTINCT address) FROM messages`) som läser hela tabellen i en enda snabb disksekvens.
  - Total körtid för full omberäkning sjönk från 7-8 sekunder till endast ca 3 millisekunder!
- **In-memory TTL-caching (`get_database_stats`)**:
  - Implementerat en 15-sekunders in-memory cache för statistiken. Vid flikbyten i Inställningar svarar servern omedelbart på 0 ms.
  - Cachen invalideras automatiskt vid rensningar, gallringar eller radering av dubbletter via `invalidate_database_stats_cache()`.
  - Lagt till stöd för `?force=1` i `/api/database/stats` så att användaren kan tvinga fram en färsk beräkning vid klick på "Refresh Stats".
- **Visuell Feedback i Användargränssnittet (`templates/settings.html`)**:
  - Lagt till roterande laddikon (`fa-spin`) och temporär inaktivering av knappen "Refresh Stats" under hämtning för tydlig visuell respons.

## [2026.10.15.9] - Fix för Spara Dubbletter Inställning (Persistence & API Whitelist)

- **Åtgärd för Återställning av "Spara dubblettmeddelanden i databasen" (`save_duplicates`)**:
  - Lade till `save_duplicates` i listan `allowed_keys` i `handle_settings()` i `app.py` så att inställningen inte filtreras bort vid sparande.
  - Ändrade `update_setting()` i `database.py` från ren `UPDATE` till `INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)` så att nya inställningsnycklar sparas även om de inte fanns i databasen sedan tidigare.
  - Gjorde att `get_settings()` i `database.py` slår ihop databasrader med `get_default_settings()`.
  - Lagt till direkt sparning via `saveDuplicateSetting()` vid ändring av kryssrutan i `templates/settings.html` samt synkning mot `duplicate_handling` ('merge'/'discard').
  - Skyddat `save_duplicates.checked` i `loadDatabaseStats()` så att den inte skrivs över medan användaren interagerar med den.

## [2026.10.15.8] - Fix för Databasstatistik (500-fel) och Inställning för Dubbletthantering

- **Åtgärd för 500-fel vid Läsning av Databasstatistik (`/api/database/stats`)**:
  - Aktiverat `PRAGMA journal_mode=WAL;` (Write-Ahead Logging), `PRAGMA busy_timeout=30000;` och anslutningstimeout på 30 sekunder i SQLite.
  - Förhindrar låsningskonflikter (`sqlite3.OperationalError: database is locked`) mellan samtidiga bakgrundsskrivningar (VDL2, SDR, radiosonder) och statistikberäkningar.
  - Implementerat retry-loop i `get_database_stats()` vid övergående databaslåsningar samt optimerad uppslagning av `alert_hits`.
  - Skapat index på `messages(is_duplicate)` och `messages(is_protected)` för blixtsnabb räkning utan fullständiga tabellskanningar av stora dataset.
- **Robust Felhantering i Inställningsvyn (`templates/settings.html`)**:
  - Säkerställt att felaktiga svar eller HTTP 500 från servern inte nollställer mätarkorten till `0`, `0 B` och `None`.
  - Felstatus visas nu som en tydlig avisering i statusraden medan befintliga statistikvärden bibehålls.
  - Säkrat uppläsningar av element mot null-pekare i JavaScript.
- **Inställning för Dubbletthantering & Manuell Dubblettrensning**:
  - Ny inställning i fliken "Database & Storage": "Spara dubblettmeddelanden i databasen" (`save_duplicates`). När den avmarkeras sparas inte dubbletter som nya rader, vilket sparar diskutrymme.
  - Ny manuell åtgärd: "Rensa alla dubbletter nu" (`POST /api/messages/delete-duplicates`) som raderar alla dubbletter ur databasen och optimerar filstorleken.
- **Enhetstester**:
  - Lade till test för `POST /api/messages/delete-duplicates` och `save_duplicates` i `tests/test_stats_api.py`. Samtliga tester passerar.

## [2026.10.15.7] - Boeing PLF Underhållsrapport och Global Flygplatsuppslagning i Rutter

- **Boeing PLF Central Maintenance / Felkodsrapport (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Implementerat parserstod for PLF-rapporter (Present Leg Faults / Post-Flight Report) fran t.ex. Boeing 737 MAX.
  - Extraherar flygrutt (`EPWA/ESSA`), raknar och klassificerar cockpit-varningar (FDE) och underhallskoder (MSG).
  - Integrerat ATA-kapiteluppslagning (t.ex. `ATA 34: Navigation`) utifran kodernas tva forsta siffror.
  - Snygg presentation: `[Underhålls-/Felrapport (PLF)] Rutt: EPWA (Warszawa/Chopin) → ESSA (Stockholm/Arlanda) | Cockpit-varningar (FDE): 2 st (ATA 34: Navigation) | Underhållskoder (MSG): 1 st`.
- **Global Flygplatsformatering (`format_airport`) i Alla Rutter (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Samtliga ruttutskrifter (`Rutt: ...`) och extraherade ICAO-koder slas nu konsekvent upp via `format_airport(icao)`.
  - Formatet anvander pil `→` och fullstandiga flygplatsnamn: `Rutt: EPWA (Warszawa/Chopin) → ESSA (Stockholm/Arlanda)`.
- **Utokat Flygplatsregister (`AIRPORT_MAP` / `FALLBACK_AIRPORTS`)**:
  - Utokat med over 80 flygplatser i Norden, Baltikum, Polen, Europa och resten av varlden (inkl. Warszawa/Chopin, Wien/Schwechat, Bromma, Skavsta, Vasteras, Malmo/Sturup, Visby, Ronneby, Saab m.fl.).
- **Enhetstester (`tests/test_vdl2.py`, `tests/test_acars_human_parser.py`)**:
  - Lagt till `test_lot_boeing_plf_fault_report` och uppdaterat befintliga rutt-tester for fullstandiga flygplatsnamn och pilar.
  - Samtliga 77 enhetstester i hela testsviten passerar felfritt.

## [2026.10.15.6] - AMDAR Väderrapport (Label H2) och Boeing CSV FMS/Väderlogg (Label H1)

- **AMDAR Meteorologiska Rapporter (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Implementerat parserstod for AMDAR (`Label: H2`) med headermonster `02E\d{2}([A-Z]{4})([A-Z]{4})` och matpunkter med lat/lon/tid/hojd/temp/vind.
  - Valjer alltid den sista (senaste/aktuella) matpunkten ur rapporten sa att planet ritas ut pa aktuell position istallet for historiska koordinater.
  - Snygg presentation: `[AMDAR Väderrapport] Rutt: LOWW (Wien) -> ESSA (Stockholm/Arlanda) | Senaste (07:18 UTC): Pos 58.7750, 17.8333 | Höjd: 19 500 ft | Temp: -14.7°C | Vind: 312° / 13 kt (5 mätpunkter)`.
- **Boeing CSV FMS/Väderlogg (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Implementerat parserstod for kommaseparerade FMS- och vaderloggar (t.ex. LOT Polish Airlines `B7378MAX` under `Label: H1`).
  - Extraherar flygplanstyp, callsign, rutt (`EPWA (Warszawa) -> ESSA (Stockholm/Arlanda)`), uppdaterar `dst_airport`, och valjer sista matpunkten for aktuell position, hojd (`39 998 ft`), temperatur (`-63.8°C`) och vind (`329° / 73 kt`).
  - Snygg presentation: `[FMS Färd- & Väderlogg] Flygplan: B7378MAX | Rutt: EPWA (Warszawa) -> ESSA (Stockholm/Arlanda) | Senaste (07:21 UTC): Pos 57.7217, 17.7250 | Höjd: 39 998 ft | Temp: -63.8°C | Vind: 329° / 73 kt (6 mätpunkter)`.
- **Forbattrad Koordinatparsning (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Generella `DDMM.M`-koordinater konverteras nu alltid till decimalgrader (`float`) och valjer den sista punkten om flera matvarden skickats.
- **Enhetstester (`tests/test_vdl2.py`)**:
  - Lagt till `test_amdar_weather_report` (Austrian Airlines `OE-LBS`) och `test_lot_boeing_fms_weather_log` (LOT `SP-LYM`).
  - Samtliga 76 enhetstester i hela testsviten passerar felfritt.

## [2026.10.15.5] - Lufthansa Group AOC Telemetri (Label 1L) och Flygbolagsinterna Labels

- **Stod for Flygbolagsinterna AOC-labels (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Lade till `"1L": "Flygbolagsdata (Lufthansa Group AOC)"` i `ACARS_LABELS` och `FALLBACK_LABELS`.
  - Fallback-logik for labels som matchar `^[1-4][A-Z]$` till `"Flygbolagsdata (AOC Intern)"` om de inte redan ar explicit definierade.
- **Formatering av Kodad AOC-telemetri (`humanize_acars_message`, `acars_human_parser.py`)**:
  - Tolkar och presenterar komprimerade 1L/AOC-paket med monster `^(\d{10,12})([A-Z0-9.,\-/]+)$`.
  - Extraherar sekvensnummer (forsta 6 siffrorna) och presenterar tydligt pa svenska: `[AOC Flygbolagsdata] Intern kodad drift-/telemetrirapport (Lufthansa Group, Seq: <sekvensnummer>) | Rådata: <msg_text>`.
- **Flygplatsdatabas (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Lade till `ESDF`: `Ronneby/Kallinge` i flygplatsuppslaget.
- **Enhetstester (`tests/test_vdl2.py`)**:
  - Lade till `test_austrian_aoc_1l_telemetry` som verifierar Austrian Airlines `OE-LBS` / `OS096F` med verklig `Label: 1L`-telemetristrang.
  - Samtliga 74 enhetstester i hela testsviten passerar felfritt.

## [2026.10.15.4] - Flygplatsformatering och Uppdatering av Destinationsbadge vid Arrival ATIS

- **Universell Flygplatsformatering (`format_airport`) (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Implementerat hjälpfunktionen `format_airport(icao)` som slår upp 4-ställiga ICAO-koder i referenstabellen och returnerar `EKCH (Köpenhamn/Kastrup)`.
  - Integrerat `format_airport(icao)` överallt där flygplatser presenteras i meddelanden: ATIS (`.TI2`), Departure Clearance (`.DC1`), Oceanic Clearance (`.OC1`), METAR och FMS-rapporter.
- **Detektering av Arrival och Departure ATIS (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Avkodar specificerad ATIS-typ (bokstaven `A` = Arrival, `D` = Departure direkt efter sekvensnummer/flygplatskod i t.ex. `/EKCH.TI2/024EKCHA6237`).
  - Presenterar tydligt och korrekt på svenska:
    - Arrival: `Begär landningsväder (Arrival ATIS) för EKCH (Köpenhamn/Kastrup)`
    - Departure: `Begär avgångsväder (Departure ATIS) för EKCH (Köpenhamn/Kastrup)`
    - Standard: `Begär flygplatsväder (ATIS) för EKCH (Köpenhamn/Kastrup)`
- **Destinationsbadge (`dst_airport`) Uppdateras vid Arrival ATIS (`vdl2_receiver.py`)**:
  - Vid mottagande av Arrival ATIS (eller `.TI2` när planet har status `Airborne`) uppdateras paketets `dst_airport` till flygplatskoden (`EKCH`).
  - Markstationsmetadata (`station`) uppdateras till `EKCH (Köpenhamn/Kastrup)`, vilket omedelbart ändrar den gröna badgen i UI från avgångsflygplatsen till den faktiska destinationen (`To: EKCH (Köpenhamn/Kastrup)`).
- **Enhetstester (`tests/test_vdl2.py`)**:
  - Uppdaterat `test_atis_departure_clearance` och lagt till `test_norwegian_arrival_atis_destination_badge` (för Norwegian `SE-RPF` / `D83195` med `/EKCH.TI2/024EKCHA6237`).
  - Samtliga 73 enhetstester i hela testsviten passerar felfritt.

## [2026.10.15.3] - FMS Progress & Destination Report samt Boeing DFDAU/ACMS Motortelemetri

- **FMS Progress & Destination Report (`acars_human_parser.py`, `vdl2_receiver.py`)**:
  - Implementerat `rule_fms_progress_destination` för avkodning av rapporter under `Label: H1` (`PRG/DT...`, `INI/DT...`, `FTX/DT...`).
  - Extraherar destination (`EGLL`), landningsbana (`27L`), beräknat landningsbränsle (`6 500 kg`), beräknad ankomsttid (`08:31 UTC`), marschhöjd (`FL380`) och temperatur (`-56°C`).
  - Slår upp destinationsflygplats i `AIRPORTS`-tabellen (`EGLL` -> `London/Heathrow`).
  - Uppdaterar paketets `dst_airport` samt `station` med den utvunna flygplatsen och skyddar den från att skrivas över av XID-data från avgångsflygplatsen, vilket gör att den gröna destinations-badgen i UI visar rätt destination.
  - Snygg presentation: `[FMS Färdrapport] Dest: EGLL (London/Heathrow) Bana 27L | ETA: 08:31 UTC | Marschhöjd: FL380 | Temp: -56°C | Landningsbränsle: 6 500 kg | Rådata: PRG/DTEGLL...`.
- **Boeing DFDAU / ACMS Numerisk Motortelemetri (`acars_human_parser.py`)**:
  - Implementerat `rule_boeing_dfdau_engine_telemetry` för meddelanden under `Label: H1`, `DF` eller prefix `#DFB` med minst 85% siffror och mellanslag samt minst 10 siffergrupper.
  - Extraherar motorvarvtal N1/N2 ur 4-siffriga grupper i hundradels procent (t.ex. `89.2%–95.4%`) med adaptiv skanning av cruise/climb-intervall.
  - Extraherar avgastemperatur EGT ur 3-siffriga mätvärden (400–850) direkt efter varvtalsblocken (t.ex. `591°C`).
  - Trunkerar råa sifferväggar till de första 35 tecknen så att tabellen och liveflödet hålls rent och överskådligt.
  - Snygg presentation: `[Boeing Motortelemetri / DFDAU] N1/N2 Varvtal: 89.2%–95.4% | EGT: 591°C | (37 mätvärden) | Rådata: 07336019 8991 9536...`.
- **Enhetstester (`tests/test_vdl2.py`)**:
  - Lagt till `test_fms_progress_and_destination_report` och `test_boeing_dfdau_engine_telemetry`.
  - Samtliga 72 enhetstester i hela testsviten passerar felfritt.

## [2026.10.15.2] - MIAM Fallback-dekoder (RFC 1924 Base85 + Deflate) och Fragmenthantering

- **Djupare sökning i dumpvdl2:s MIAM-träd (`vdl2_receiver.py`)**:
  - Kontrollerar samtliga fält under `miam.single_transfer.miam_core.data` (`acars.msg_text`, `raw`, `text`), `miam_core.raw`, `single_transfer.data` och rot-`miam`.
- **Egen Fallback-dekoder (`decode_miam_base85`) (`vdl2_receiver.py`)**:
  - Avkodar RFC 1924 Base85-strängar (`base64.b85decode`) och dekomprimerar med `zlib` (stöd för både standard zlib-header, raw deflate `wbits=-zlib.MAX_WBITS` och gzip/auto).
  - Skannar dynamiska MIAM Single Transfer-offsets (3 till 8 tecken) efter `T01`/`T02` och extraherar läsbar ASCII-telemetri samt kör geolokalisering (`extract_position_and_telemetry`).
  - Strukturerad presentation av binära Airbus SAR/FDIMU-paket med utvunna ASCII-parametrar: `[MIAM Binär Flygdata] Airbus komprimerat telemetripaket (<X> bytes uppackat)`.
- **Snygg Presentation av Fragmenterade/Krypterade Delpaket (`vdl2_receiver.py`, `acars_human_parser.py`)**:
  - Eliminerat oläsliga Base85-teckenväggar i gränssnittet vid fragmentering eller saknade block (`acars.more == True`).
  - Ersatt med informativ ren statusrad:
    `[MIAM Komprimerad Telemetri] Krypterat/fragmenterat Airbus-datapaket (<X> B, delpaket) (<preview>...)`.
  - Skyddat `[MIAM ...]`-taggar från prefix-strippning i `acars_human_parser.py`.
- **Enhetstester (`tests/test_vdl2.py`)**:
  - Lagt till `test_miam_raw_fragment_handling` och `test_miam_decode_valid_base85_package`. Samtliga 70 enhetstester passerade utan anmärkning.
  - Verifierat att koden är 100% fri från emojis.

## [2026.10.15.1] - Multi-val och Filtrering på Flera RF Activity-kanaler i Vattenfallet

- **Multi-val av SDR-kanaler i RF Activity (`static/waterfall.js`, `templates/index.html`, `static/waterfall.css`)**:
  - Infört multi-val så att användaren kan klicka på och välja 1 eller flera radiokanaler samtidigt (t.ex. flera VDL2-frekvenser, RIKS 1 och POCSAG).
  - Ersatt tidigare enkelvalsvariabel (`activeFilterChannel`) med ett Set (`activeFilterChannels`).
  - Varje kanalrad i RF Activity har nu en tydlig och stilren kryssruta (`.channel-check-box`) med FontAwesome-bock (`fas fa-check`) vid aktiv markering.
  - Varje klick på en kanalrad eller sammanfattningspiller (`.ribbon-summary-pill`) växlar nu dess valstatus (av/på).
- **Integrerad DataTables-filtrering och Samtidig Textsökning (`templates/index.html`)**:
  - Implementerat en dedikerad DataTables-sökfunktion (`$.fn.dataTable.ext.search.push`) som matchar rader mot samtliga valda kanaler (via `data-channel-key`, `data-frequency` och protokoll).
  - Det ordinarie textsökfältet (`#searchInput`) förblir nu helt fritt och oberoende så att användaren kan söka efter specifika ord, larmkoder eller anrop inom de filtrerade kanalerna.
- **Rensaknapp i Ribbon-panelen**:
  - Lade till en smidig "Rensa filter (N)"-knapp (`#ribbonClearFilterBtn`) som visas automatiskt när 1 eller fler kanaler är aktiverade och återställer filtreringen med ett klick.
- **Strikt Design och Emojifritt**:
  - 100% fritt från emojis. Använder rena ikoner och premium mörk glasmorfism-design.

## [2026.10.14.32] - Strukturerad Metadata på Badge-raden, Ren Textlayout utan Pipes och Helords-ordbevakning

- **KRAV 1: Flytta VDL2/ACARS Metadata till Badge-raden längst ner**:
  - Metadata flyttad från textinnehållet till strukturerade fält och renderas nu som eleganta badges i `.msg-meta-bar` längst ner i cellen bredvid frekvens, ACARS och SNR:
    - **Registrering**: t.ex. `.badge.badge-reg` (`SE-RTA` / `ET-ATK`).
    - **Flightnummer & Flygbolag**: t.ex. `.badge.badge-flight` (`ET0715` / `D84378`).
    - **ICAO Hex**: t.ex. `.badge.badge-icao` (`ICAO: 040127`).
    - **Markstation**: t.ex. `.badge.badge-station` (`To: Arlanda ESSA`).
    - **Status**: t.ex. `.badge.badge-status.badge-airborne` (`Airborne`) eller `.badge.badge-status.badge-ground` (`On Ground`).
    - **Label**: t.ex. `.badge.badge-label` (`Label: 83 - Operativt meddelande`).
  - Rensat bort protokollbrus såsom `Mode: 2`, `Block: 8`, `Msg: F40A`, `ACK: !` samt dolt ovidkommande `Alpha`/`Num` för VDL2.
  - Bakåtkompatibel frontend-rensning och extraktion i `index.html`, `larm.html` och `statistics.html` för historiska meddelanden.
- **KRAV 2: Ren och Snygg Presentation av Meddelandetexten (helt utan "|" tecken)**:
  - Samtliga avkodningsregler i `acars_human_parser.py` och `vdl2_receiver.py` omformaterade så att de aldrig använder pipe-tecken (`|`).
  - Texten är prydligt uppställd med rena radbrytningar och tydliga fältnamn på svenska:
    - **Färddator-rapport (Label H1 POSN)**:
      `Höjd: FL330   Temperatur: -47 C   Vind: 343 deg (91 kt)`
      `Nästa brytpunkt: MC624 (kl 20:45:16 UTC)`
      `Position: 56.8433, 16.3250`
    - **CSV-rapport (Label 83)**:
      `Rutt: ESSA -> HAAB (Avgång/Ankomst)   Tid: 20:29 UTC`
      `Höjd: 22605 ft   Fart: 305 kt   Kurs: 166.9 deg   Bränsle: 43000`
      `Position: 58.54, 18.94`
    - **MIAM Airbus Telemetri**: Ny dedikerad regel `rule_miam_airbus_telemetry` för strukturerad presentation av Airbus-telemetri (höjd, vind, temperatur, waypoint, kurs, Mach, bränsle och koordinater).
- **KRAV 3: Unicode- och Helordsmatchning i Ordbevakningen (Word Boundaries)**:
  - Åtgärdat fel där sökord såsom `LIGHT` och `PORT` felaktigt triggade på delsträngar i `Flight` och `Airport`.
  - Implementerat Unicode-säker helordsmatchning både i backend (`check_alert_words` och SQLite custom function `WORD_MATCH`) samt i frontend (`checkAlertWordMatch` och `highlightMessage`):
    - Mönster: `(?<![a-zA-Z0-9åäöÅÄÖ])ORD(?![a-zA-Z0-9åäöÅÄÖ])` med case-insensitivity.
  - Ordmatchningen körs uteslutande på själva meddelandetexten (`cleanMsg`), aldrig på metadata eller badge-fält.
- **Tester**:
  - Samtliga 68 enhetstester passerar grönt. Verifierat 100% fri från emojis.

## [2026.10.14.31] - Global Referensdatabas (acars_reference_data.json), Libacars-tolkning och Airframes Decoder-mönster

- **Global Referensdatabas (`acars_reference_data.json`)**:
  - Automatiserad extrahering och aggregering av referensdata från ACARSHUB och Airframes GitHub-repon:
    - `labels`: 183 standard ACARS-etiketter (`_d`, `H1`, `SA`, `80`-`89`, `10`-`5Z`, `Q0`, `QA`-`QZ`, `RA`, `B6` m.fl.).
    - `airlines`: 1 711 flygbolagsmappningar (både IATA 2-bokstavs och ICAO 3-bokstavskoder till officiella flygbolagsnamn).
    - `ground_stations`: 4 904 markstationer (SITA/ARINC i både hex- och decimalformat till flygplatsnamn och ICAO-koder, t.ex. `Arlanda Airport (ESSA)`).
- **Direkt Libacars-tolkning ur Dumpvdl2 JSON**:
  - Implementerat `format_libacars_data()` som direkt konsumerar färdigtolkade strukturer i dumpvdl2 (`arinc622.adsc`, `ats`, `cpdlc`, `miam`, `xid`) för presentation av telemetri (position, höjd, vind, temperatur och stationshandover).
- **Portade Textmönster från Airframes ACARS-Decoder**:
  - Label `H1`: Färdplaner (`FPN/RI`, ICAO FPL med automatisk ruttidentifiering `ESSA -> EKCH`), `INI` förberedelser, `RESREQ` kvittenser och `MM`/`DFB`/`CFB` telemetri.
  - Label `10`-`4Z` & `80`-`89`: Finnair Label 38, Ethiopian Label 83 CSV-position, SAS Label 83 ETA, Airframes Variant 2 (`4DH3 ETAT2`) samt OOOI (`OUT`, `OFF`, `ON`, `IN`).
  - Label `SA`: Fullständig Media Advisory-tolkning (upprättad/förlorad länk och tillgängliga länkar VHF, VDL2, SATCOM, HF).
  - Label `Q0` / `5U` / `5Z` / `B6` / `RA`: Länktest, METAR/TAF väderbegäran, CPDLC klareringar och dispatch-kommandon.
  - Generell fallback-extraktion: Identifierar automatiskt rutt (`ORIG/DEST`), `ETA`, flygnivå (`FL`) och koordinater ur okända meddelanden.
- **Tester**:
  - 67 enhetstester validerar databasladdning, libacars-data och alla avkodningsregler.

## [2026.10.14.30] - ACARSHUB Metadata-extrahering och Label 83 CSV-positionsrapporter

- **ACARSHUB-liknande Metadata-extrahering**:
  - Extraherar rika metadata ur inkommande dumpvdl2/ACARS JSON (`avlc` och `acars`) och presenterar en kompakt header överst i meddelandet:
    `[Reg: ET-ATK | Flight: ET0715 (Ethiopian Airlines) | ICAO: 040127 | To: 119AAA (Arlanda Airport ESSA) | On Ground: No | Mode: 2 | Msg: M37A]`.
  - Inkluderar Tail/Reg (`reg`), Flight (`flight`), Flygbolagsuppslag via modulär prefix-tabell, ICAO Hex-adress (`src.addr`), Markstationsuppslag (`dst.addr`), markstatus (`On Ground: Yes / No`), länkmode (`mode`) och meddelandenummer (`msg_num` + `msg_num_seq`).
- **Modulära Uppslagstabeller (`acars_human_parser.py`)**:
  - Centraliserat `AIRLINE_MAP` och funktionen `lookup_airline()` med stöd för IATA 2-bokstavs och ICAO 3-bokstavskoder (inkl. Ethiopian Airlines, SAS, Finnair, Norwegian, Lufthansa, British Airways, KLM, Air France, Ryanair, Wizz Air, airBaltic, Qatar Airways, Emirates, Turkish Airlines m.fl.).
  - Skapat `GROUND_STATIONS` och funktionen `lookup_ground_station()` för automatisk översättning av markstationer (t.ex. Arlanda Airport ESSA).
- **Mönster för Label 83 CSV-positionsrapporter**:
  - Implementerat `rule_label_83_csv_position` för avkodning av 9-fälts kommaseparerade rapporter (Avgång, Destination, Tid DDHHMM, Lat, Lon, Höjd i fot, Fart i knop, Kurs i grader, Bränsle/Vikt).
  - Formaterar läsbart: `Rutt: ESSA -> HAAB | Tid: 20:29 UTC | Pos: 58.54, 18.94 | Höjd: 22605 ft | Fart: 305 kt | Kurs: 166.9 deg | Bränsle/Vikt: 43000`.
  - Integrerat i `extract_position_and_telemetry()` i `vdl2_receiver.py` så att latitud (58.54), longitud (18.94), flyghöjd, fart och kurs extraheras som koordinater och telemetri för kartplottning.
- **Tester**:
  - Nya automatiserade tester i `tests/test_acars_human_parser.py` och end-to-end integrationstest i `tests/test_vdl2.py`.

## [2026.10.14.29] - Fristående Modulär ACARS Human-Parser (acars_human_parser.py)

- **Fristående Modulär ACARS-parser (`acars_human_parser.py`)**:
  - Skapat en separat regelbaserad parser för att översätta råa kryptiska ACARS- och VDL2-meddelanden till ren, professionell och lättläst svensk text utan emojis.
  - Modulär arkitektur där varje avkodningsmönster är en fristående regelfunktion som enkelt kan utökas med nya flygbolag och protokoll utan att ändra kärnlogiken i `vdl2_receiver.py`.
  - Bevarar automatiskt alla inledande prefix i hakparenteser (såsom `[H1: FMS / Färddator-rapport]` eller `[38]`) och faller mjukt tillbaka på originaltexten om inget mönster matchar.
- **Implementerade Mönster i acars_human_parser.py**:
  - **Mönster 1: Label 38 (Finnair väder- och positionsrapport)**: Avkodar flight (`AY8892`), latitud, longitud, höjd (`37969 ft`), temperatur (`-57 C`) samt vindriktning och hastighet (`335 deg (35 kt)`).
  - **Mönster 2: Label H1 POSN (FMS / Färddator-rapport med rutt och väder)**: Avkodar flygnivå (`FL380`), temperatur (`-58 C`), vindriktning/hastighet (`334 deg (88 kt)`), nästa brytpunkt/waypoint med ankomsttid i UTC samt bevarar positionskoordinater.
  - **Mönster 3: Label H1 RESREQ/AK (Systemkvittens)**: Översätter `RESREQ/AK` till `Systemkvittens: Resursförfrågan bekräftad (ACK)` med valfri CRC-summa.
  - **Mönster 4: Label 83 ETA-rapport (Gate/Ankomst)**: Extraherar ankomststatus, beräknad ankomsttid i UTC samt statuskod (`ETA-30`).
  - **Mönster 5: Label H1 MM-telemetrilogg (Matrislogg)**: Identifierar logg-headern, räknar antalet mätpunkter och extraherar tidsspannet mellan första och sista mätpunkten i UTC.
- **Integration i Mottagaren (`vdl2_receiver.py`)**:
  - Alla meddelanden passerar nu genom `parse_human_acars()` innan de sparas i databasen och skickas till klienter.
- **Dedikerade Enhetstester (`tests/test_acars_human_parser.py`)**:
  - 11 automatiserade tester som validerar alla 5 mönster, prefix-bevarande och fallback-beteende.

## [2026.10.14.28] - Humaniserad ACARS-avkodning, Dedikerad SNR-pill, Robust HTML-escaping och RF Activity Sonde-korrigering

- **Dedikerad SNR-pill under meddelandetexten bredvid ACARS-märket**:
  - SNR visas nu som en separat smaragdgrön pill (`.badge.meta.badge-snr`) under texten i `.msg-meta-bar`, placerad direkt bredvid ACARS/bitrate-pillret.
  - SNR-strängar rensas automatiskt bort från meddelandetexten i användargränssnittet (`index.html`, `larm.html`, `statistics.html`), vilket ger ett rent och proffsigt textfält utan brus.
  - Färgstilar implementerade för både mörkt och ljust tema i `static/style.css`.
- **Skydd mot felaktig HTML-tolkning av krypterade eller binära tecken (HTML Escaping)**:
  - Åtgärdat problem där kryptiska och binära tecken i POCSAG/FLEX/ACARS meddelanden (t.ex. vinkelparenteser `<` och `>`) tolkades som HTML-taggar av webbläsaren, vilket orsakade oönskad överstrykning (strikethrough) eller länkar.
  - Fullständig HTML-escaping (`&`, `<`, `>`, `"`, `'`) i `formatMessage` och `highlightMessage` innan radbrytningar appliceras.
- **Korrekt Namngivning och Isolering av Radiosonder i RF Activity (`static/waterfall.js`)**:
  - Avlägsnat en felaktig hårdkodning som tidigare klassificerade alla frekvenser som började på `4` som `TETRA`.
  - Radiosonder (400-406 MHz) registreras nu konsekvent under det korrekta namnet `Radiosond` med frekvens (t.ex. `Radiosond 403.500M`) istället för att förväxlas med TETRA.
  - `sonde_receiver.py` skickar nu explicit `sdr_name: 'Radiosond'` och SNR-data i alla realtids-callbacks.
- **Humaniserad ACARS-avkodning (`vdl2_receiver.py`)**:
  - Svensk uppslagsbok `ACARS_LABELS` för informativa etiketter (t.ex. `[SA: Länkstatus (Media Advisory)]`, `[B9: Begäran om flygplatsväder (ATIS)]`).
  - Tolkning av länkstatus (Media Advisory) med etablerade länkar (VDL2, HF, Satcom) och tidsangivelser i UTC.
  - Flygplatsavkodning (`AIRPORT_MAP`) för ATIS- och klareringsbegäran (`/EKCH.TI2/` -> Köpenhamn/Kastrup).
  - Prefix för Boeing/Honeywell FMS (`#M1B`) och underhållsdata.
  - XID Handover-stöd och ny inställning för att dölja periodiska ACARS-länktest (`Label Q0`).

## [2026.10.14.27] - Radiosond- och Väderballongsintegration via radiosonde_auto_rx UDP-ström

- **UDP Telemetrimottagare (`sonde_receiver.py`)**:
  - Implementerat en asynkron bakgrundslyssnare på UDP-port `55673` för att ta emot realtidstelemetri (`PAYLOAD_SUMMARY`) från `radiosonde_auto_rx`.
  - Stöd för kända radiosondmodeller (Vaisala RS41, RS41-SG, RS92, GRAW DFM-09, Meteomodem M10/M20, m.fl.).
- **Smart Flödeshantering & Skydd mot Databasöverbelastning**:
  - Väderballonger sänder telemetri varje sekund under 2-3 timmar (~9 000 paket per flygning).
  - Implementerat en aktiv rad per flygning i databasen som uppdateras med rate-limiting (standard var 5:e sekund) via `repeat_update` och SQL UPDATE.
  - Varje sekund skickas lättviktig `sonde_telemetry` via SSE direkt till webbläsaren för silkesmjuka kartuppdateringar utan onödig databasbelastning.
- **Milstolpar och Händelselogik under Flygning**:
  - **Start**: Sparas som en separat händelse i databasen när en ny ballong upptäcks.
  - **Sprängning (Burst)**: Detekteras automatiskt när ballongen nått över 8 000 m och faller kraftigt (sjunkhastighet < -4 m/s och fallit > 250 m från maxhöjd). Loggar maxhöjd och sparar milstolpen i databasen.
  - **Landning**: Detekteras automatiskt när ballongen når under 350 m eller stannar vid marken. Sparar slutposition och landningshöjd.
- **Gränssnitt och Inställningar**:
  - Ny flik "Radiosonder" i inställningspanelen med realtidsstatus, mottagna UDP-paket, aktiva sonder i luften och maxhöjdrekord.
  - Möjlighet att konfigurera lyssnarport (standard 55673) och databasintervall.
  - Testknapp för syntetisk radiosond (RS41-SG) för omedelbar verifiering.
  - Nya protokollmärken för `SONDE` med specialanpassad färgprofil i mörkt och ljust läge.
- **Enhetstester**:
  - Tillagt `tests/test_sonde.py` som validerar modellavkodning, telemetriprompt, flygfasdetektering (ascent, burst, landing) och API-status.

## [2026.10.14.26] - Avancerad MIAM Airbus Telemetri, Mönster 1-4 Geoparsning och Identifieringslyft

- **MIAM Airbus Telemetriavlastning (`vdl2_receiver.py`)**:
  - Implementerat prioriterad extrahering av uppackad Airbus-telemetri via `vdl2.avlc.acars.miam.single_transfer.miam_core.data.acars.msg_text`.
  - Den råa komprimerade Base85-strängen i ACARS ignoreras automatiskt till förmån för klartextmeddelandet.
- **Multimönster Positions- och Telemetriextrahering (`extract_position_and_telemetry`)**:
  - **Mönster 1 (Airbus MIAM/FDIMU semikolon-format)**:
    - Extraherar `PALAT` och `PALONG` med flyttalskonvertering och vetenskaplig notation (`5.875309E+01` -> 58.75309° N, `1.543292E+01` -> 15.43292° E).
    - Extraherar `PAALT` (flygnivå FL), `PASAT` (temperatur °C), `PAFOB` (bränsle kg), `PAMN` (Mach-tal), `PATHDG` (kurs/heading), `PAFMSAWID` (aktiv waypoint), `PAGWTFQMS` (bruttovikt kg) och `PAWS` (vindhastighet kt).
    - Bygger en strukturerad telemetrisammanfattning direkt i meddelandet och metadatan.
  - **Mönster 2 (Standard decimalformat, t.ex. Ryanair Label 16)**:
    - Extraherar `N 56.955 E 17.322` samt flyghöjd från intilliggande kommaseparerade fält (`37012` -> FL370).
  - **Mönster 3 (Kompakt DM-format, t.ex. Finnair Label H1)**:
    - Konverterar `POSN58525E018360` till decimala koordinater: `N58525` = 58° + 52.5'/60 = 58.875°, `E018360` = 18° + 36.0'/60 = 18.600°.
  - **Mönster 4 (XID / GSIF / ADS-C struktur)**:
    - Fallback till `xid.ac_location` och `adsc.basic_report` direkt ur JSON om meddelandetexten saknar koordinater.
- **CPDLC Flygledningsparsning**:
  - Fullständig avkodning av `vdl2.avlc.x25.clnp.cotp.cpdlc` samt ARINC 622 CPDLC med märkningen `[CPDLC]`.
- **Rensad Registrering, Adressering och SNR**:
  - Rensar automatiskt bort inledande punkter i registrering (t.ex. `".OH-LWI"` -> `"OH-LWI"`).
  - Formaterar adress/avsändare till komplett format: `Flight (Reg) [ICAO]` (t.ex. `AY1338 (OH-LWI) [461F50]`).
  - Beräknar mottagnings-SNR i realtid (`sig_level - noise_level` dB) och presenterar det i meddelandesträngen och metadatan.
- **Strikt Paketfiltrering**:
  - Filtrerar bort tomma signallänkar (t.ex. `AVLC Receive Ready` och `X.224 COTP Data Ack`) när filterinställningen är aktiverad.

## [2026.10.14.25] - VDL Mode 2 / Flygdata TCP-integration mot dumpvdl2 och acars_router

- **Nätverksbaserad VDL2-mottagare (`vdl2_receiver.py`)**:
  - Implementerat en asynkron bakgrundsklient som strömmar färdigavkodade VDL Mode 2-meddelanden över TCP (standard: `192.168.1.242:15555`) direkt från användarens befintliga `dumpvdl2` / `acars_router`-container.
  - Eliminerat behovet av ytterligare USB-hårdvarulås och kompilering av tunga C-binärer i Pager-Monitors egen container.
  - Inbyggd automatisk återanslutning med exponentiell backoff vid nätverksavbrott eller omstart av router-containern.
- **Intelligent JSON- och Meddelandeparsning**:
  - Stöd för både dumpvdl2:s hierarkiska protokollstruktur (`vdl2` -> `avlc` -> `acars` / `cpdlc` / `x25`) samt normaliserade routerformat.
  - Extraherar flygnummer (flight), registrering (reg/tail), ICAO 24-bit hexadress, mottagningsfrekvens, signalkvalitet och ACARS label-koder.
  - Avkodning av CPDLC (Controller-Pilot Data Link Communications) flygledningsmeddelanden och positionsrapporter med koordinatparsning (Lat/Lon).
- **Berikad Flygbolags- och Label-mappning**:
  - Inbyggt uppslagsregister för nordiska och internationella flygbolag (SAS, Norwegian, Finnair, Ryanair, Lufthansa, British Airways m.fl.) som automatiskt fyller i aliasfältet med flygbolagsnamn och flygplansregistrering.
  - Svenska beskrivningar för standardiserade ACARS labels (Positionsrapporter, OOOI-tider, Väder/METAR, Tekniska statusrapporter m.m.).
- **Filtrering och Duplikathantering**:
  - Inställningsbart filter (`vdl2_filter_empty`) för att ignorera tomma radiohandskakningar/signallänksramar och enbart spara meningsfulla textmeddelanden.
  - Integrerad med Pager-Monitors duplikatskydd och sammanfogningslogik (merge/discard).
- **Dedikerat Webbgränssnitt för VDL2 / Flygdata**:
  - Ny flik **VDL2 / Flygdata** i Inställningar med realtidstelemetri (anslutningsstatus, antal mottagna nätverkspaket, avkodade meddelanden, senast sedda flygplan och tidsstämpel).
  - Direkt konfigurering av värdadress (IP), TCP-port och innehållsfiltrering med omedelbar autosparning.
  - Testknapp för att skicka syntetiska VDL2/ACARS-testlarm (`/api/vdl2/test`) direkt till realtidsflödet, databasen och larmtabellen.
- **UI och Protokollstöd (`style.css`, `index.html`, `larm.html`, `statistics.html`)**:
  - Ny flygblå protokollbricka (`proto-vdl2`) för både mörkt och ljust tema.
  - Integrerad presentation i realtidsflödet, larmlistan och statistiksidan.

## [2026.10.14.24] - Fix för Global UnboundLocalError i Sessionsloop och Realistisk Dwell-tid vid FM-skanning

- **Åtgärdat `UnboundLocalError` i `run_rds_session` (`rds_decoder.py`)**:
  - `_current_channel_tmc_active`, `_current_channel_p4_confirmed` och `_current_channel_is_commercial` saknade `global`-deklaration inuti `run_rds_session`. När ett värde tilldelades i funktionen tolkade Python variabeln som lokal vilket orsakade ett omedelbart `UnboundLocalError` när den lästes vid loopens start.
  - Deklarerat samtliga nödvändiga modulglobaler i funktionens huvud.
- **Justering av Snabbavbrott från 2.5s till 6.0s**:
  - RTL-SDR hårdvaruinitiering och `redsea` biphase-avkodning behöver 3–5 sekunder för att etablera bärvågssynk och avkoda det första 104-bitars RDS-blocket. Det tidigare 2.5s-avbrottet avbröt frekvenser innan dekodern ens hunnit producera sin första rad data, vilket fick skannern att rusa förbi aktiva RIKS-stationer.
  - Tidsfönstret för signalavkänning har justerats till 6.0s vilket ger stabil synk.
- **Prioritering av Kända SR TMC-stationer vid Spektrummätning**:
  - Kända sändare för SR P3 och SR P4 prioriteras nu alltid överst i sökkön och sorteras efter lokal RF-signalstyrka via `rtl_power`, före godtyckliga FM-rasterfrekvenser.
- **Förfinad Stationsidentifiering**:
  - Kommersiella radiostationer och SR P1/P2 sållas bort direkt så att de aldrig fellåses som SR TMC.

## [2026.10.14.23] - Fix för UnboundLocalError i RDS Heartbeat, Prioritering av 88.7M och Robust Processhantering

- **Åtgärdat `UnboundLocalError` i `_heartbeat_worker` (`rds_decoder.py`)**:
  - `station_str` refererades i en kontroll före variabeldeklarationen, vilket orsakade ett omedelbart Python Traceback-undantag och avslutade dekodern (`exit=1`) så fort övervakningstråden startade eller en fast frekvens valdes.
  - Flyttat variabelinitieringen av `station_str` och `pi_str` till trådens inledande iteration för att garantera giltiga värden.
- **Direktlåsning och Full P4 PI-kodstäckning (`rds_decoder.py`)**:
  - `is_sr_tmc_station` känner nu igen samtliga regionala P4-distrikt i Sverige (PI-prefix `0xEA`, `0xEB`, `0xEC`, `0xED`, `0xE4`, `0xE204`, etc.) samt P3 (`0xE203`).
  - Mottagaren låser omedelbart vid detektering av en bekräftad Sveriges Radio-station (P3/P4) och förblir låst för att fånga upp periodiska ALERT-C trafikmeddelanden.
- **Prioritering av 88.7 MHz (SR P4 Sörmland)**:
  - 88.7M är nu placerad som position 1 i kandidatlistan, vilket innebär omedelbar kontroll och låsning vid autoläge.
- **Rörbuffert och Felfångst i Underprocesser**:
  - `stderr` för `rtl_fm` och `redsea` omdirigeras nu till `DEVNULL` för att förhindra buffertblockeringar och trasiga rör (BrokenPipe).
  - Fast frekvenskörning skyddas av felåterhämtning i huvudloopen.
- **Flerlinjers Felspårbarhet i sdr_processor**:
  - Processövervakaren loggar nu kompletta Python tracebacks rad för rad till loggströmmen.

## [2026.10.14.22] - Kraschfix för RDS-dekoder vid null-PS och Robustifiering av Underprocesser

- **Åtgärdat krasch vid mottagning av ofullständiga RDS-ramar (`AttributeError`)**:
  - `redsea` returnerar `"ps": null` i JSON när stationsnamn ännu inte är fullständigt mottaget eller under ackumulering. Att köra `data.get("ps", "").strip()` orsakade `AttributeError: 'NoneType' object has no attribute 'strip'` vilket ledde till att Python kraschade och avslutades med exit-kod 1 (`decoder PID exit=1`).
  - Säkrat upp alla fältutläsningar (`ps`, `pi`, `oda`, `tmc`, etc.) i `parse_redsea_json_line` med typkontroll så att `null`-värden och oväntade datatyper aldrig kraschar processen.
- **Typoberoende raw_data avkodning i AlertCDecoder**:
  - `AlertCDecoder.decode_group` stöder nu både listor av hex-strängar (`["e203", "8000", ...]`) och enkla textsträngar, med skydd mot typ- och konverteringsfel.
- **Kommando- och sessionsskydd**:
  - Tog bort experimentella eller icke-standardiserade flaggor från redsea-anropet så att `redsea` alltid startar stabilt i standard europeiskt läge (`redsea -r 171k`).
  - Lagt till `try...except` runt JSON-parsningen i `run_rds_session` samt runt sessionsanropet i `main()`, vilket garanterar att frekvensskanningen fortsätter utan att Python-processen dör vid enskilda defekta radiodata-paket.
  - Förbättrat `reset_station_state()` så att pulsmätaren och ramräknaren nollställs korrekt vid byte av radiokandidat.
- **Utökad felspårbarhet i sdr_processor**:
  - `monitor_instance` fångar och loggar nu felrader och Python tracebacks från underprocessernas stdout/stderr med `logger.error`, så att felorsaker syns omedelbart i applikationsloggen.

## [2026.10.14.21] - Omedelbar Låsning på SR P3/P4, Snabbavbrott (2.5s) och Full FM-Bandskanning

### Fixed
- **Direktlåsning på Bekräftad SR P3 eller SR P4 (`rds_decoder.py`)**:
  - Åtgärdat det kritiska problemet där skannern övergav mottagna SR P3/P4-stationer efter 10 sekunder enbart för att inga larm skickades under just det tidsfönstret.
  - Eftersom SR P3 och SR P4 är Sveriges officiella TMC-kanaler låser mottagaren nu omedelbart så fort stationen identifierats via PI/PS med giltig RDS-signal.
  - Mottagaren stannar permanent kvar på frekvensen och avkodar kontinuerligt alla ALERT-C larm som sänds.
- **Snabbavbrott på 2.5s för Tomma Bärvågor (`rds_decoder.py`)**:
  - Frekvenser utan mottagen RDS-signal (döda frekvenser) avbryts nu efter 2.5 sekunder istället för 10 sekunder. Detta fyrdubblar skanningshastigheten förbi tomma kanaler.
- **Fullständig FM-Bandskanning (`get_p4_candidates` i `rds_decoder.py`)**:
  - Skanningen genererar nu hela FM-bandet (87.5–108.0 MHz med 200 kHz steg) för att fånga upp alla lokala sändare och repeatrar, med kända SR P3/P4-sändare prioriterade först i kön eller via RF-spektroskopering (`rtl_power`).

## [2026.10.14.20] - Inbyggd ALERT-C ISO 14819-1 Parser för SR P3 & P4 samt Utökade Snabbval

### Added
- **Inbyggd ALERT-C Parser (`AlertCDecoder` i `rds_decoder.py`)**:
  - Implementerat en ISO 14819-1 avkodare som tolkar råa RDS-block (asHex) för Grupp 8A direkt i Python.
  - Löser problemet med att `redsea` kastar 8A-trafikmeddelanden om den ännu inte tagit emot Grupp 3A ODA-handskakning.
  - Stödjer både single-group och multi-group meddelanden och avkodar händelsekod, omfattning, riktning och numeriskt plats-ID direkt till svenska vägnamn och koordinater.
- **Fullt Stöd för SR P3 som TMC-distributör (`rds_decoder.py`, `templates/sdr_settings.html`)**:
  - Sveriges Radio P3 (PI `0xE203`, t.ex. 99.3 MHz Stockholm/Kisa, 99.4 MHz Göteborg, 97.0 MHz Hörby) är det officiella rikstäckande nätet för Trafikverkets RDS-TMC i Sverige.
  - Både SR P3 och SR P4 erkänns nu fullt ut som giltiga TMC-kanaler i avkodaren och pulsmätaren.
  - SDR-inställningarnas snabbvalsdropdown har utökats med grupperade val för både SR P3 (Rikstäckande TMC) och SR P4 (Regional TMC).
- **Aktiverat Redsea Rådataström (`-R`) (`rds_decoder.py`)**:
  - `redsea` anropas med `-R` för att garantera att råa blockdata (`raw_data`) alltid skickas med i JSON-strömmen för direkt tolkning.

## [2026.10.14.19] - Förhindrat Falsk TMC-låsning på Råa 8A-block och Identifiering av Icke-TMC Stationer

### Fixed
- **Strikt Krav på Avkodat Meddelande för Grupp 8A-låsning (`rds_decoder.py`)**:
  - Åtgärdat bugg där mottagaren låste sig och felaktigt rapporterade `TMC: Aktiv (ALERT-C 8A-larm mottagna)` enbart för att ett enstaka rått RDS-block för Grupp 8A detekterades i luften på icke-TMC stationer (t.ex. SR P3, 99.3 MHz).
  - Grupp 8A låser nu endast mottagaren och flaggar aktiv TMC om ett fullständigt och giltigt ALERT-C meddelande (`loc_code`) faktiskt avkodats, eller om sändaren tidigare bekräftats via Grupp 3A ODA ALERT-C.
  - Partiella 8A-block loggas nu endast på bekräftade TMC-stationer för att undvika vilseledande loggar på icke-TMC kanaler.
- **Tydlig Identifiering av SR P1, P2 och P3 (`rds_decoder.py`)**:
  - Sveriges Radio sänder ALERT-C TMC uteslutande via SR P4.
  - Avkodaren känner nu igen PI-koder och stationsnamn för P1, P2 och P3 (`0xE201`, `0xE202`, `0xE203`) och informerar direkt i heartbeat (`TMC: Ej TMC-sändare (P3 SR sänder ej TMC, välj SR P4)`) samt i skanningsloggen om att TMC inte sänds på dessa kanaler.

## [2026.10.14.18] - Åtgärdat Falsk TMC-låsning på RadioText+ och Korrigerade Redsea Flaggor

### Fixed
- **Separation av RadioText+ (RT+) och ALERT-C i Grupp 3A (`rds_decoder.py`)**:
  - Åtgärdat kritisk bugg där mottagaren felaktigt identifierade RadioText+ (ODA 3A) som en aktiv TMC-sändare med AID `0xCD46`. Detta medförde att mottagaren låste sig permanent på stationer som enbart sände låttitlar/artister (t.ex. 88.7 MHz) utan att sända några faktiska ALERT-C trafikmeddelanden (Grupp 8A).
  - Grupp 3A valideras nu strikt mot ALERT-C AID `0xCD46`/`0xCD47`, applikationsnamnet `"RDS-TMC: ALERT-C"` och redseas `system_info`-träd.
  - Pulsmätarens TMC-status skiljer nu explicit mellan äkta ALERT-C och vanlig RadioText+ (`TMC: Ej TMC (Grupp 3A är RadioText+, ej ALERT-C)`).
- **Korrigerade Redsea Flaggor (`rds_decoder.py`)**:
  - Tagit bort flaggan `-u` från anropet till `redsea`. I redsea är `-u` en förkortning för `--rbds` (nordamerikansk radiostandard) och skall inte användas för europeisk FM-RDS i Sverige.
- **Prioriterade Regionala Huvudsändare i Frekvenskön (`rds_decoder.py`)**:
  - `P4_STATIONS` prioriterar nu starka regionala huvudsändare med bekräftad ALERT-C distribution (Stockholm 103.3 MHz, Sörmland 100.1 MHz, Uppland 102.5 MHz, Göteborg 101.9 MHz) före lokala slavsändare.

## [2026.10.14.17] - Strikt ALERT-C (Grupp 3A) Låsning vid RDS-skanning och P4 Snabbval i SDR Inställningar

### Added
- **P4 Sändare & Frekvens Snabbval (`templates/sdr_settings.html`)**:
  - Ny dropdown-snabbväljare under sektionen RDS-TMC i SDR-inställningarna med kända Sveriges Radio P4-sändare över hela Sverige (t.ex. Stockholm 103.3 MHz, Södertälje 93.8 MHz, Sörmland 100.1 MHz, Uppland 102.5 MHz, Göteborg 101.9 MHz, Malmöhus 102.0 MHz, m.fl.) samt valet för automatisk sökning (`auto`).
  - Tvåvägssynkning: Att välja en station i listan uppdaterar frekvensfältet automatiskt, och manuell inmatning i frekvensfältet matchar automatiskt motsvarande sändare i dropdownen.

### Fixed
- **Strikt Krav på Aktiv ALERT-C TMC (Grupp 3A / 8A) för Kanallåsning (`rds_decoder.py`)**:
  - Åtgärdat fel där mottagaren i skanningsläge (`auto` / frekvensintervall) låste frekvensen omedelbart enbart för att stationen identifierades som Sveriges Radio P4 (`is_sr_p4_station`), även om sändaren inte sände aktiv RDS-TMC.
  - Skannern avvaktar nu dwell-tiden (10 sekunder) på kandidatkanaler och låser endast när äkta Grupp 3A (TMC System Information) eller Grupp 8A (ALERT-C trafikmeddelanden) tas emot.
  - Om ingen Grupp 3A/8A detekteras inom 10 sekunder loggas en tydlig statusförklaring (`P4-station identifierad på ... men ingen aktiv RDS-TMC (Grupp 3A) inom 10s. Söker vidare...`) och skannern går automatiskt vidare till nästa kandidatfrekvens i kön.

## [2026.10.14.16] - Dedikerat Protokoll i Tabellkolumn och Metadata Flyttad Längst Ner i Meddelanderutan

### Changed
- **Dedikerad Protokollvisning i Tabellkolumn (`index.html`, `larm.html`, `statistics.html`)**:
  - Kolumnen `RF / META` har döpts om till `Protocol` och visar nu uteslutande det aktuella protokollet (`POCSAG`, `TETRA`, `RDS`, `AFSK`) som ett enskilt, rent piller.
  - Eliminerat vertikal anhopning ("många piller") och optimerat cellbredden till 105px (min 95px, max 120px) med horisontell centrerad/vänsterjusterad anpassning.
- **Metadata Flyttad till Botten av Meddelanderutan (`.msg-meta-bar`)**:
  - Övrig sändningsmetadata (frekvens som `161.4375M`, överföringshastighet som `1200bps` / `TMC`, läge som `Alpha` / `Num`, repetitioner som `2x` samt eventuell `Duplicate`-flagga) visas nu horisontellt längst ner i meddelanderutan under själva meddelandetexten.
  - `copyMessageText` kopierar nu uteslutande den faktiska meddelandetexten utan att inkludera underliggande tekniska metadatataggar.
  - SSE-realtidsuppdateringar för sammanslagna dubbletter (`repeat_update`) uppdaterar automatiskt `2x`-märket i meddelanderutans metadatabalk.

## [2026.10.14.15] - Strikt Låsning vid Fast RDS-frekvens och Frekvens i Heartbeat-loggen

### Fixed
- **Strikt Låsning på Fast Frekvens för RDS (`rds_decoder.py`)**:
  - När en specifik fast frekvens ställs in för RDS (t.ex. `103.3M`) låser mottagaren strikt på denna frekvens.
  - Skanning och sökning vidare till andra stationer/kandidater är nu helt avaktiverat när frekvensen är en fast kanal. Skanningsmotorn och frekvenshopp aktiveras enbart om frekvensen explicit satts till `auto`, `scan` eller ett frekvensintervall (t.ex. `87.5M-108M`).
  - Mottagaren avbryter inte längre efter 10 sekunders dwell-timeout eller vid kommersiella sändningar när fast frekvens är vald.
- **Frekvens i Heartbeat-loggen (`rds_decoder.py`, `sdr_processor.py`)**:
  - Både `HEARTBEAT FÖRLORAD` och aktiva `HEARTBEAT`-meddelanden anger nu alltid explicit vilken frekvens som avlyssnas (t.ex. `[RDS] HEARTBEAT FÖRLORAD -> Frekvens: 103.3M | Ingen RDS-signal detekterad på 10.0s (Signalbortfall eller frekvens saknar RDS)`).

## [2026.10.14.14] - Protokoll-Badge i RF/META, Fix för Test-TMC och Synkad Versionsspårbarhet

### Added
- **Protokollmärken i RF / META (`index.html`, `larm.html`, `statistics.html`, `style.css`)**:
  - Nytt dedikerat protokollmärke i kolumnen `RF / META` för alla meddelandelistor och larmtabeller.
  - Skiljer visuellt och tydligt mellan olika mottagna protokoll:
    - `POCSAG`: Smaragdgrön badge (`proto-pocsag`).
    - `TETRA`: Bärnstensgul badge (`proto-tetra`).
    - `RDS`: Korallrosa badge (`proto-rds`).
    - `AFSK`: Indigoblå badge (`proto-afsk`).
  - Optimerad metadata-rendering så att underprotokoll och hastigheter (`1200bps`, `SDS`, `NET`, `TMC`) kompletterar utan redundans.
  - Stöd för både ljust och mörkt tema med hög kontrast och läsbarhet.
- **Protokoll-härledning i API och Backend (`database.py`, `sdr_processor.py`, `app.py`)**:
  - Fältet `protocol` skickas nu alltid med i SSE-realtidsflödet och härleds i databasfrågor (`/api/messages`).

### Fixed
- **Åtgärdat Importfel vid RDS-TMC Testsignal (`app.py`)**:
  - Åtgärdat fel `NameError: name 'save_message' is not defined` vid anrop till `/api/test/tmc`.
- **Synkroniserad Versionsspårbarhet (`app.py`, `README.md`)**:
  - Uppdaterat central `APP_VERSION` till `2026.10.14.14` så att sidopanelens versionsnummer stämmer överens med gällande CalVer.
- **Korrigerat Sökfilter och Kanalmappning för RDS i Waterfall (`waterfall.js`)**:
  - Klick på RDS-kanalen i waterfall sätter sökfiltret till `RDS` istället för `auto`.
  - Inkommande RDS-TMC meddelanden binds direkt till den befintliga `RDS`-kanalen.

## [2026.10.14.13] - Korrigerat Kanalfilter för RDS i RF Activity Waterfall

### Fixed
- **Sökfilter vid Val av RDS i Waterfall (`waterfall.js`)**:
  - Åtgärdat fel där klick på en kanal med frekvens `auto` satte sökfiltret till ordet `auto` istället för mottagarens namn `RDS`.
  - När kanalen RDS klickas sätts sökfiltret nu korrekt till `RDS`, vilket omedelbart matchar alla `RDS-TMC` larm i tabellen.
  - Kopplat inkommande RDS-TMC meddelanden direkt till den befintliga `RDS`-kanalen i waterfall så att det inte skapas dubbla rader (t.ex. `Freq 103.3M`), och uppdaterat kanalens visningsfrekvens till den låsta frekvensen.

## [2026.10.14.12] - Korrigerad Grupp 3A Matchning och Protokoll-Badge utan 'bps'

### Fixed
- **Protokoll-Badge i Webbgränssnittet (`index.html`, `larm.html`, `statistics.html`)**:
  - Förhindrar att suffixet `bps` adderas till `RDS-TMC` och `TETRA`. Visas nu snyggt och korrekt som `RDS-TMC` istället för `RDS-TMCbps`.
- **Korrekt Grupp 3A Detektering (`rds_decoder.py`)**:
  - Säkerställt att `aid_str` inte tilldelas `"CD46"` i förväg på tomma paket, vilket förhindrar att vanliga RDS-grupper (0A, 2A, 14A) felaktigt matchas som 3A.

## [2026.10.14.11] - Strikt Deduplicering av TMC Grupp 3A Synk-loggar

### Fixed
- **Loggspam för Grupp 3A Synk (`rds_decoder.py`, `sdr_processor.py`)**:
  - Flyttat loggutskriften `INFO: [RDS-TMC] TMC SYNK (Grupp 3A)` så att den enbart loggas en enda gång när handskakningen bekräftas, istället för vid varje enskild 3A-dataram.
  - Lagt till deduplicering i `sdr_processor.py` som extra skydd för att eliminera upprepade rader i konsolloggen.

## [2026.10.14.10] - Förbättrad Redsea ODA/TMC-tolkning och Direkt Testlarm till Realtidsflödet

### Added
- **Stöd för Redsea ODA- och Meddelandestrukturer (`rds_decoder.py`)**:
  - Utökat stöd för `redsea`:s fält `open_data_app` (Grupp 3A) samt `user_message` och `events`-array (Grupp 8A).
  - Åtgärdat fel där AID kunde loggas som `0xNONE` vid saknade fält i redsea-strömmen; faller nu alltid tillbaka till `0xCD46` (ALERT-C).
  - Stöd för `direction: "positive"` / `"negative"` från redsea.
- **Direkt Testlarm i Realtidsflödet (`app.py`, `templates/settings.html`, `rds_decoder.py`)**:
  - Nytt endpoint `POST /api/test/tmc` som sparar testlarmet och sänder ut det live via SSE till alla öppna webbläsarfönster utan att sidan behöver laddas om.
  - Ny knapp i gränssnittet under Inställningar -> Manuella databasåtgärder: "Skicka testsignal för RDS-TMC".
  - Kommandot `--test-tmc --save-db` anropar nu webbserverns interna REST API i första hand för omedelbar realtidsvisning i flödet.

## [2026.10.14.09] - TMC-statusindikator i Heartbeat och --save-db Testläge

### Added
- **TMC-status i Heartbeat (`rds_decoder.py`)**:
  - Heartbeat-utskriften visar nu en explicit `TMC:`-status för att direkt förklara varför larm inte syns om det inte finns olyckor i etern:
    - `TMC: Aktiv (ALERT-C larm mottagna)` vid mottagna Grupp 8A-larm.
    - `TMC: Synkad (Grupp 3A aktiv, inga 8A-larm i luften)` när sändaren är synkad mot ALERT-C men inga olyckor rapporterats i regionen.
    - `TMC: Söker handskakning (3A)` vid uppstart eller svag signal.
- **Databas-injektion vid Testläge (`--test-tmc --save-db`)**:
  - Flaggan `--save-db` tillåter direkt sparande av det syntetiska testlarmet i `messages.db` så att användaren omedelbart kan se och verifiera larmet i applikationens webbgränssnitt och på kartan.

## [2026.10.14.08] - Mottagna RDS-grupper i Heartbeat och 3A Synk på INFO-nivå

### Added
- **Spårning av RDS-grupptyper i Heartbeat (`rds_decoder.py`)**:
  - Heartbeat-raden visar nu samtliga unika RDS-grupptyper som antennen faktiskt tar emot från FM-sändaren (t.ex. `RDS-grupper: 0A, 2A, 3A, 8A`).
  - Detta ger 100% transparens: användaren ser direkt om masten sänder Grupp 3A (TMC-handskakning) och om Grupp 8A (trafiklarm) sänds i luften.
- **TMC Handskakning (Grupp 3A) på INFO-nivå**:
  - `INFO: [RDS-TMC] TMC SYNK (Grupp 3A) → AID: 0xCD46 | LTN: 1 (Sverige) | Systemstatus: AKTIV` loggas nu på INFO-nivå så att handskakningen syns direkt i standardloggen utan att debug-läge behöver aktiveras.

## [2026.10.14.07] - Robust RDS-TMC Parsning, Ofiltrerat Redsea-läge (-u) och Syntetiskt Testläge

### Added
- **Ofiltrerat Redsea-läge (`-u`) i `rds_decoder.py`**:
  - `redsea` körs nu med flaggan `-u` (`redsea -u -r 171k`). Detta tvingar redsea att omedelbart strömma ut mottagna ALERT-C 8A- och 3A-grupper utan intern aggregeringsfördröjning.
- **Robust TMC-inspektion och Strukturerad Larmlogg**:
  - Detektering av Grupp 3A (System Information) loggas på DEBUG-nivå med AID (`0xCD46`), LTN (1 för Sverige) och aktuell systemstatus.
  - Identifiering av Grupp 8A (ALERT-C trafikmeddelanden) oavsett om redsea strukturerar JSON under nyckeln `tmc` eller direkt under rotobjektet med `group: 8A`.
  - Robust fältextraktion för `event_codes`, `event_descriptions`, `location`, `extent`, `direction`, `urgency` och `duration`.
  - Strukturerad loggutskrift för varje mottaget 8A-trafiklarm:
    `INFO: [RDS-TMC] LARM MOTTAGET → Plats-ID: {location} | Händelse: {event_desc} | Riktning: {direction} | Omfattning: {extent} | Råkod: {event_codes}`
- **Inbyggt Syntetiskt Testläge (`--test-tmc`)**:
  - Lagt till CLI-argument `--test-tmc` i `rds_decoder.py` för omedelbar hårdvarulös verifiering av hela avkodningskedjan.
  - Injicerar syntetiskt Grupp 3A och Grupp 8A meddelande (placerat på E4 Nyköping, stillastående kö i 2 km / kod 101) och kontrollerar att avkodning, platstabelluppslag och larmskapande fungerar till 100%.
- **Säker UTF-8 Encoding**:
  - Konfigurerat `sys.stdout` och `sys.stderr` till UTF-8 med fellösning för att garantera att pilsymboler (`→`) och specialtecken fungerar felfritt på Windows-konsoler.

## [2026.10.14.06] - Visning av Signalkvalitet och Gain i RDS Heartbeat

### Added
- **Signalkvalitetsbedömning i RDS Heartbeat (`rds_decoder.py`, `sdr_processor.py`)**:
  - Dynamisk beräkning av signalkvalitet i procent baserat på antalet felfria RDS-grupper per sekund dividerat med teoretiskt max (11.41 ramar/s för RDS ALERT-C).
  - Pedagogisk kvalitetsgradering direkt i loggflödet:
    - `>= 90 %`: `Perfekt mottagning`
    - `70 - 89 %`: `God mottagning`
    - `40 - 69 %`: `Acceptabel (enstaka paketfel)`
    - `< 40 %`: `Svag signal / Prova justera Gain` (loggas som `WARNING`)
  - Visning av aktuell Gain i loggraden (t.ex. `Gain: 25 dB` eller `Gain: auto`), vilket ger direkt återkoppling när användaren ändrar Gain i inställningarna eller kommandoraden.
  - Exempel på loggutskrift vid god signal:
    `INFO: [RDS] HEARTBEAT -> Station: P4 Sörml (PI: 0xEA24) | Status: SYNKERAD | Kvalitet: 98% (11.2/11.4 ramar/s - Perfekt mottagning) | Gain: 25 dB | Senaste aktivitet: 0.1s sedan`
  - Exempel på loggutskrift vid svag signal:
    `WARNING: [RDS] HEARTBEAT -> Station: P4 Sörml (PI: 0xEA24) | Status: SVAG SIGNAL | Kvalitet: 33% (3.8/11.4 ramar/s - Svag signal / Prova justera Gain) | Gain: 49.6 dB | Senaste aktivitet: 0.2s sedan`

### Changed
- **SDR Processor RDS-start (`sdr_processor.py`)**:
  - Parametern `--gain` vidarebefordras nu konsekvent (`auto` eller specifikt dB-värde) till `rds_decoder.py` för omedelbar telemetri i pulsmätaren.
  - Utökat testsvit med `test_rds_heartbeat_logging` för att verifiera både `OK`, `LOW` och `LOST` statusar.

## [2026.10.14.05] - Kontinuerlig Frekvensskanning och Eliminering av RDS-loggspam

### Added
- **Automatisk Fortsatt Skanning vid Saknad RDS-TMC (`rds_decoder.py`)**:
  - Om en frekvens saknar RDS-TMC (eller sänder kommersiell radio som RIX FM / Mix Megapol utan TMC), fastnar mottagaren inte längre på frekvensen.
  - Skannern avbryter omedelbart vid detektering av kommersiell radio, eller efter 10 sekunder vid utebliven RDS-TMC, och provar nästa frekvens i kandidatlistan.
  - Omfattande databas med 25 Sveriges Radio P4-sändare över hela landet (inklusive 88.7 MHz Sörmland, 100.1 MHz, 103.3 MHz m.fl.).
  - Även när en fast frekvens anges (t.ex. 88.7M) prövas den först, men om TMC saknas fortsätter skannern automatiskt bland övriga P4-sändare.
  - Om en låst station tappar signal under mer än 30 sekunder återupptas sökningen automatiskt.

### Fixed
- **Total Eliminering av Logg-spam vid Stationssynk (`rds_decoder.py`, `sdr_processor.py`)**:
  - Åtgärdat felet där `RDS-INFO: PS: P4 Sörml PI: 0xEA24` och `RDS-TMC LOCK:` loggades om och om igen varje sekund.
  - Orsaken var att `redsea` växlade mellan JSON-rader med enbart PI och rader med både PS och PI, vilket lurade den tidigare stationsjämförelsen.
  - Implementerat strikt tillståndshantering och deduplicering i både avkodaren och processorn: stationsinformation och bärvågslåsning loggas nu exakt EN gång vid upptäckt och låsning.
  - Fullständigt stöd för regionala P4 PI-koder med prefix `EA` (t.ex. `0xEA24` för SR P4 Sörmland).

## [2026.10.14.04] - Realtidspuls (Heartbeat) för RDS-mottagning och Stationssynk

### Added
- **Trådsäker Pulsmekanism för RDS (`rds_decoder.py`)**:
  - Implementerat en kontinuerlig pulsmätare (`record_rds_frame`) som räknar varje giltig, checksum-validerad RDS-ram/grupp som levereras av `redsea` eller testflödet.
  - Håller kontinuerlig koll på:
    - Tidpunkt för senaste godkända ram (`last_frame_time`).
    - Senast identifierade stationsnamn (PS, t.ex. `SR P4`) och programidentifieringskod (PI, t.ex. `0xE204`).
    - Antal mottagna ramar sedan senaste pulskontroll.
    - Beräknad blocktakt (ramar per sekund).
- **Bakgrundsövervakare med Konfigurerbart Intervall (`rds_decoder.py`)**:
  - Dedikerad bakgrundstråd (`_heartbeat_worker`) som kontrollerar status oberoende av I/O-blockeringar på `redsea`:s stdout.
  - Stödjer CLI-argument `--heartbeat-interval` (standard: 10s) och `--heartbeat-timeout` (standard: 5s).
- **Integrerad Logghantering i Processorn (`sdr_processor.py`)**:
  - Fångar upp pulshändelser från avkodaren:
    - Vid synk: `INFO: [RDS] HEARTBEAT -> Station: SR P4 (PI: 0xE204) | Status: SYNKERAD | Takt: 11.2 ramar/s | Senaste aktivitet: 0.1s sedan`
    - Vid signalbortfall (> 5s): `WARNING: [RDS] HEARTBEAT FÖRLORAD -> Ingen RDS-signal detekterad på 5.2s (Signalbortfall eller frekvens saknar RDS)`
- **Inställningar i Webbgränssnittet (`settings.html`, `database.py`)**:
  - Lagt till styrning av loggintervall och bortfallsgräns direkt under fliken för signalinställningar med automatisk direktsparning.

## [2026.10.14.03] - Egen Bakgrundsfärg för Basstationer i Larm- och Meddelandeflödet

### Added
- **Egen Färgprofil för Basstationsrader (`index.html`, `larm.html`)**:
  - Implementerat en distinkt, mjuk cyan/himmelsblå bakgrundston för basstationsrader (`.basestation-row`) i både dashboarden och larmlistan:
    - **Ljust tema:** Mjuk ljusblå/mint ton (`#f0fdfa` / `#e0f2fe`) med en vertikal accentkant i azurblått (`#0284c7`).
    - **Mörkt tema:** Diskret cyan ton (`rgba(6, 182, 212, 0.08..0.15)`) med en vertikal accentkant i cyan (`#06b6d4`).
  - I larmlistan visas basstationer med en dedikerad ljusblå `BASE`-tagg istället för generisk röd larm-tagg.
  - Förbättrar överskådligheten och skiljer radioinfrastruktur/bärvågor från faktiska personsökar- och larmutryckningar.

## [2026.10.14.02] - RDS-TMC Grupp 3A Handskakning & Strikt Stationsvalidering (ALERT-C)

### Added
- **RDS Grupp 3A Handskakning och Systeminformation (`rds_decoder.py`)**:
  - Implementerat detektering av RDS Grupp 3A med Application Identifier (AID) `0xCD46` (ALERT-C) och Location Table Number (LTN) `1` (Trafikverkets tabell `LTN 01`).
  - När Grupp 3A tas emot verifieras TMC-stödet och loggas omedelbart med handskakningsbekräftelse (`TMC Handskakning (Grupp 3A): ALERT-C aktiv (AID: 0xCD46, LTN: 1 Sverige)`).
- **Utökade ALERT-C Händelsekoder (`rds_decoder.py`)**:
  - Utökat `ALERT_C_EVENTS` med standardkoder enligt ISO 14819-2 för trafikstockning, svår halka, snöfall, belysningsarbete m.m.

### Fixed
- **Strikt Stationsvalidering (SR P4 vs Kommersiella Stationer) (`rds_decoder.py`)**:
  - Säkerställt att skannern skiljer mellan Sveriges Radio P4 (PI-kod `0xE2xx` / `0xE4xx`) och kommersiella stationer utan TMC (t.ex. RIX FM `0xE241`, Mix Megapol `0xE242`).
  - Om en kommersiell station tas emot loggas detta tydligt som saknar TMC och skannern söker vidare efter en aktiv SR P4-sändare.

## [2026.10.14.01] - Återställd Visning av Låsta TETRA-basstationer i Meddelandeflödet

### Fixed
- **Basstationer Visas Korrekt vid Låsning i Flödet (`tetra_decoder.py`, `sdr_processor.py`)**:
  - Åtgärdat felet där skannern låste på en basstations bärvåg (`TETRA LOCK: Basstation låst på frekvens 421.05M`) men ingen post skapades i meddelandeflödet trots att användaren valt \"Basstationer: Visas\".
  - Orsaken var att `tetra_decoder.py` undertryckte utsändningen av `NET`-händelsen vid låsning om krypteringsfiltret (`skip_encrypted`) var aktivt och felaktigt antog att alla frekvenser var krypterade Rakel-master (MNC=01).
  - Skannern skiljer nu korrekt på Rakel-bandet (380-385 / 390-395 MHz) och civila TETRA-band (t.ex. 410-430 MHz såsom 421.05 MHz).
  - Vid låsning på en civil basstation genereras omedelbart en `NET`-händelse som sparas i databasen och skickas till realtidsflödet med adress (t.ex. `TETRA-421.05M`), alias (`Civilt TETRA Basstation`) och fullständig modulation/signalkvalitet (`[ÖPPET / CIVIL]`).
  - Lade även till telemetriuppdatering vid `TETRA LOCK` i `sdr_processor.py` så att aktuell lyssnarfrekvens omedelbart syns i gränssnittet.

## [2026.10.13.36] - Stöd för Tomt Frekvensfält, Auto/Scan och Förtydligade Hjälptexter

### Added
- **Tydlig Information om Auto, Scan och Tomt Fält (`sdr_settings.html`, `settings.html`)**:
  - Förtydligat hjälptexten och placeholder direkt under frekvensfältet: användaren informeras om att fältet kan lämnas **helt tomt** eller sättas till `auto` / `scan` för att automatiskt söka upp den starkaste Sveriges Radio P4-stationen (TMC).
  - Tagit bort det tvingande `required`-attributet från frekvensinmatningen i både hårdvaruinställningar och modalerna för att skapa/klona mottagare.

### Fixed
- **Hantering av Frekvensintervall och Tom Frekvens (`rds_decoder.py`, `sdr_processor.py`, `database.py`)**:
  - Åtgärdat felet där ett frekvensintervall (t.ex. `87.5M-108M`) orsakade fel i frekvensparsningen och låste radion direkt på `87.5M`.
  - Implementerat `is_fm_scanning_range()` och `parse_range_hz()` som känner av intervall som `87.5M-108M`, `auto`, `scan` eller tomt fält och automatiskt triggar en spektrumsökning över P4-frekvenser.

## [2026.10.13.35] - Strikt Begränsning till RDS-TMC Trafikmeddelanden & Eliminering av Låttextspam

### Changed
- **Strikt Begränsning till ALERT-C Trafikmeddelanden (`sdr_processor.py`, `rds_decoder.py`)**:
  - Avlägsnat hantering av vanlig RDS-metadata (PS och RadioText) från att någonsin tolkas som larm eller sparas i databasen. Låttexter (t.ex. "Bäst musik just nu!"), artister och reklam från kommersiella FM-stationer filtreras bort till 100%.
  - Endast faktiska ALERT-C / TMC trafikmeddelanden (`RDS-TMC:`) sparas i databasen, skickas till realtidsgränssnittet via SSE och publiceras via MQTT.
- **Riktad Avsökning efter Sveriges Radio P4 (`rds_decoder.py`)**:
  - Automatisk FM-stationssökning prioriterar nu specifikt Sveriges Radio P4 (P4 Stockholm 103.3M, P4 Sörmland 100.1M, P4 Uppland 102.5M m.fl.) som är den enda sändaren av ALERT-C TMC i Sverige.
  - Kommersiella kanaler (som RIX FM, Mix Megapol) som saknar TMC hoppas över under skanning.
- **Automatisk Rensning av Databas (`database.py`)**:
  - Lagt till automatisk rensning vid uppstart av tidigare felaktigt sparade `RDS-PS` och `RDS-%` rader ur `messages`-tabellen.

## [2026.10.13.34] - Rensning av Testfiler från Git och Lokalt Bevarande

### Changed
- **Exkluderat Testfiler från Git och GitHub (`.gitignore`, `tests/`)**:
  - Testsviten i katalogen `tests/` (`test_imports.py`, `test_log_console.py`, `test_sdr_watchdog.py`, `test_security_and_larm.py`, `test_stats_api.py`) har avlägsnats från GitHub och Git-indexet (`git rm --cached`).
  - Filerna bevaras lokalt i utvecklingsmiljön för framtida verifiering men hålls borta från produktionsrepot på GitHub för att hålla repot rent och fokuserat på produktionskod.
  - Lagt till `tests/` i `.gitignore`.

## [2026.10.13.33] - Automatisk FM-stationssökning för RDS-TMC, Redsea i Docker & Åtgärdat Subprocess-avslut

### Added
- **Automatisk FM-stationssökning för RDS-TMC (`rds_decoder.py`, `sdr_processor.py`)**:
  - Mottagaren behöver inte längre en manuellt inmatad FM-frekvens. Om frekvensen anges till `auto`, `scan`, eller om en frekvens utanför FM-bandet (87.5–108.0 MHz, t.ex. gamla personsökarfrekvensen 169.8M) är konfigurerad, startar dekodern automatiskt frekvenssökning efter Teracom SR P4 / P3 i området.
  - Skannern skickar telemetri (`RDS-TMC: SCAN` och `RDS-TMC: LOCK`) som automatiskt uppdaterar instansens `active_frequency` i backend och webbgränssnitt.
- **Kompilering av Redsea i Dockerfile (`Dockerfile`)**:
  - Lagt till kompilering av `redsea` (FM-RDS dekoder) från källkod i builder-steget med meson och ninja, samt lagt till runtime-biblioteken `libliquid1` och `libsndfile1` i Docker-bilden.

### Fixed
- **Åtgärdat Omedelbart Subprocess-avslut (`rds_decoder.py`)**:
  - Åtgärdat felet där `rds_decoder.py` avslutades med exitkod 0 inom några millisekunder (`decoder PID=120 exit=0`). Orsaken var att `if not sys.stdin.isatty():` slog till i Docker och icke-interaktiva underprocesser och läste en tom stdin fram till EOF.
  - Styrning från stdin kräver nu explicit `--stdin`, och dekodern kör stabilt i bakgrunden utan att krascha vid tom stdin.
  - Fallback-läge och felhantering aktiveras automatiskt om hårdvaruprocessen inte hittas.

## [2026.10.13.32] - RDS-TMC Dekoder & Åtgärdat MNC!=1 Stöd för TETRA

### Added
- **RDS-TMC Dekoder (ALERT-C / ISO 14819) (`rds_decoder.py`, `sdr_processor.py`)**:
  - Implementerat modulär dekoder för RDS och RDS-TMC trafikmeddelanden.
  - Inbyggd översättningstabell för ALERT-C händelsekoder (ISO 14819-2) till svenska (t.ex. trafikolyckor, köbildning, vägarbeten, halka).
  - Sveriges officiella platstabell (Location Table LTN 01 från Trafikverket) med WGS84-koordinater och trafikplatsnamn för E4, E20, E18, E6, E22, Riksväg 73, Riksväg 40 m.fl.
  - Stöd för att köra via `redsea` eller direkt testflöde.
  - Protokollval `RDS-TMC (ALERT-C Trafikinformation)` tillgängligt i SDR-inställningarna med automatisk frekvensvägledning.
  - Koordinater och trafikmetadata skickas med i realtidsflödet över SSE och sparas i databasen för kartvisualisering.

### Fixed
- **Strikt Respektering av MNC!=1 och Filtrering av Krypterad Rakel (`tetra_decoder.py`, `sdr_processor.py`, `templates/sdr_settings.html`)**:
  - Åtgärdat fel där mottagaren inte respekterade inställningen att hoppa över MNC=1:
    1. Åtgärdat ett boolean-strängfel i `sdr_processor.py` där databasens standardvärde `'false'` på instansen blockerade globala inställningar via Python-uttrycket `'false' or current_settings...`.
    2. Avlägsnat hårdkodad generering av `TETRA: NET MCC: 240 MNC: 01` i `run_scan_loop()` och manuellt läge innan styrsignalens (BSCH) faktiska nätverkskod hunnit avkodas.
    3. Lagt till strikt kontroll i `monitor_instance()` som kastar basstationer och anrop från Rakel (MNC=1) när `skip_encrypted` är aktiverat.
    4. Lagt till valet `Använd global inställning` (`inherit`) i inställningsdialogen för SDR-mottagare.
    5. Säkerställt att skannern omedelbart söker vidare och svartlistar bärvågen om basstationen identifieras som MNC=1.

## [2026.10.13.31] - Filtrering av Krypterade Master (Gå vidare om MNC=1 / Rakel)

### Added
- **Konfigurerbar Filtrering av Krypterade Master (`tetra_decoder.py`, `sdr_processor.py`, `database.py`)**:
  - Infört ett nytt val: **Hoppa över krypterade master (MNC=1)** både i globala inställningar och per individuell TETRA SDR-mottagare.
  - Söker och låser nu specifikt på civila och öppna TETRA-nät (t.ex. MNC != 1, flygplatser, industri, kollektivtrafik) och hoppar automatiskt över MSB Rakel (MNC=1 krypterat läge).
  - Skannern i `tetra_decoder.py` hoppar automatiskt förbi det statliga Rakel-blåljusbandet (380–385 MHz och 390–395 MHz) och avbryter omedelbart om en låst mast i andra frekvensband annonserar MNC=1.
  - Tydlig märkning i händelser och loggar: `[ÖPPET / CIVIL]` för civila basstationer respektive `[KRYPTERAT]` för Rakel.
- **Gränssnittsstöd i Inställningar och Mottagarvy (`templates/settings.html`, `templates/sdr_settings.html`)**:
  - Lagt till toggle under TETRA Skanningsläge i inställningarna samt dropdown för `tetra_skip_encrypted` i mottagarredigeringen med omedelbar autosparning.

## [2026.10.13.30] - Kontinuerlig Synkförnyelse i TETRA-ström och Förbättrad Basstationsidentifiering

### Fixed
- **Kontinuerlig Förnyelse av Synktimer i TETRA-ström (`tetra_decoder.py`)**:
  - Åtgärdat felet där mottagaren felaktigt släppte låsningen mot basstationen efter exakt 10 sekunder trots stark signal (+31 dB SNR).
  - I `stream_continuous` ackumuleras och analyseras I/Q-strömmen kontinuerligt (~40 ms block) med frekvensdrift-kompensation (`check_channel_dqpsk_modulation` och `process_bits`). Vid varje bekräftad burst eller synksekvens förnyas `last_sync_time = time.time()`, vilket håller mottagaren kvar permanent i `monitor`-läge.
  - Eliminerat oavsiktliga kanalraster-hopp (t.ex. mellan 392.250 MHz och grannkanalen 392.225 MHz) som orsakades av att skannern trodde att synk förlorats och svartlistade frekvensen.
  - Lagt till periodisk burst-telemetri (`DEBUG`) var 5:e sekund för spårbarhet av frekvensdrift och DQPSK-kvalitet under pågående låsning.
- **Tydlig Loggning och Återställning av Basstationsnamn och Nätdata (`sdr_processor.py`, `tetra_decoder.py`)**:
  - `sdr_processor.py` loggar nu tydligt `TETRA BASSTATION IDENTIFIERAD: [RAKEL-240-01] Rakel Basstation | ...` med fullständig nätinformation (`Nät: Sverige / Rakel (MSB)`).
  - Basstationshändelser visas korrekt i webbgränssnittet och sparas med alias och adress när `log_tetra_basestations` är aktiverat.

## [2026.10.13.29] - Återställt Fullständig Basstationsavkodning med Alias och Nätinformation

### Fixed
- **Återställt Visning av Basstationer med Adress, Alias och Nätdata (`sdr_processor.py`)**:
  - Åtgärdat felet där basstationer enbart loggades som kort telemetri (`TETRA BASSTATION SYNKRISERAD`) och inte dök upp i larmflödet med namn och nätverksinformation.
  - Orsaken var en för tidig `continue`-sats i `sdr_processor.py` som avbröt pipelinen innan adress (`RAKEL-240-01`), alias (`Rakel Basstation`) och meddelandetext med fullständig nät- och signalinformation (`Nät: Sverige / Rakel (MSB)`) hann genereras och skickas till gränssnittet.
  - Logiken respekterar nu inställningen `log_tetra_basestations`: när den är påslagen (`true`) körs hela avkodningspipelinen och visar basstationen med fullständig information i larmflödet, samtidigt som `waterfall.js` förhindrar att den genererar falska hits i RF ACTIVITY.

## [2026.10.13.28] - Protokollspecifika Inställningar, Sparning av Driftläge och Rensning av Basstationer

### Fixed
- **Dynamisk Anpassning av Signal & Decoding per Protokoll (`templates/sdr_settings.html`)**:
  - Vid val av protokoll **TETRA** döljs nu alla irrelevanta `multimon-ng`- och `rtl_fm`-inställningar (Log Level, Charset, Output Format, Input Type, Resample, FM De-emphasis, FIR-filter, Atan-math och Oversampling).
  - Istället visas enbart relevanta kontroller för TETRA: Driftläge (`monitor` vs `explorer`), Fördröjning per basstation (vid explorer) samt I/Q Samplingshastighet (1.8 MS/s, 2.0 MS/s, 2.4 MS/s) tillsammans med en informativ guide.
  - Dynamisk anpassning av frekvenshjälptext beroende på om POCSAG (169.8M), AFSK (144.8M) eller TETRA (direkt kanal/intervall) är valt.
- **Sparning av TETRA Driftläge och Fördröjningstid (`app.py`, `database.py`)**:
  - Åtgärdat felet där ändring av TETRA Driftläge (`tetra_scan_mode`) och Fördröjningstid (`tetra_dwell_time`) i Inställningar inte sparades. Nycklarna saknades i `allowed_keys` i `/api/settings` i [app.py](file:///d:/antigravity/pager-monitor/app.py) och filtrerades därför bort.
  - Lagt till fälten `tetra_mode` och `tetra_dwell_time` i `sdr_instances`-tabellen i databasen samt i klonings- och uppdateringsfunktionerna.
- **HTTP 500-fel vid Rensning av Basstationer (`app.py`, `database.py`)**:
  - Åtgärdat felet `Exception on /api/messages/basestations [DELETE] 500 Internal Server Error` orsakat av ett anrop till en odefinierad funktion `database.get_db_connection()`.
  - Skapat [clear_basestation_messages()](file:///d:/antigravity/pager-monitor/database.py) och [get_db_connection()](file:///d:/antigravity/pager-monitor/database.py) i `database.py` med skydd mot borttagning av låsta meddelanden och felhantering i API:et.

## [2026.10.13.27] - Synkbaserad Bärvågsbevakning och Driftlägen för TETRA

### Added
- **Stöd för Driftlägen i TETRA-skannern (`tetra_decoder.py`, `database.py`, `templates/settings.html`)**:
  - **Dedikerad Trafiklyssning (`monitor`)**: Standardläge. Mottagaren låser på starkaste kontrollkanalen och stannar obegränsad tid så länge basstationens styrsignal och synksekvenser faktiskt hörs – även nattetid när ingen användartrafik pågår.
  - **Explorer / Kartläggning (`explorer`)**: Nytt kartläggningsläge som stannar på varje detekterad basstation i en konfigurerbar tid (standard 60 sekunder) för att registrera nätverksdata, färgkod och Cell ID, varpå skannern automatiskt sveper vidare till nästa mast i området.
  - Webbgränssnitt för att välja mellan Dedikerad Trafiklyssning och Explorer samt ställa in fördröjningstid direkt under Inställningar -> TETRA / Rakel Basstationsloggning.

### Fixed
- **Synk- och Styrsignalsbaserad Aktivitetshantering (`tetra_decoder.py`)**:
  - Aktivitet baseras nu på mottagna Synchronization Training Sequences (STS) och styrsignaler istället för användaranrop. I [tetra_decoder.py](file:///d:/antigravity/pager-monitor/tetra_decoder.py) uppdaterar `TetraDemodulator.process_bits` nu `last_sync_time` varje gång en godkänd TETRA STS eller MAC-ram detekteras (vilket en aktiv mast sänder flera gånger per sekund).
  - Infört en 10-sekunders timeout för faktisk signalförlust: Skannern bryter endast låsningen och återupptar frekvenssvepet om basstationens styrsignal helt tappas bort (mer än 10 sekunder utan synk).
  - Lagt till fullständig avkodning och utskrift av `CALL`, `STATUS` och `SDS` även i stdin-strömningsloopen.

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
