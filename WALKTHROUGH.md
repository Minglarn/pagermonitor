# Walkthrough: PagerMonitor - LARM-sida och HTTP-säkerhet

## Versionsinformation
- **CalVer**: `2026.10.11`
- **Datum**: 2026-10-11
- **Språk**: Svenska

---

## Genomförda funktioner och ändringar

### 1. Separat sida för LARM
- **Placering i sidomenyn**: Ny länk `LARM` med klockikon.
- **Mall**: `templates/larm.html` (URL: `/larm`).
- **Funktionalitet**:
  - Filtrerar automatiskt fram enbart meddelanden som har fått en träff (HIT) på något aktivt bevakat ord.
  - Varje meddelanderad förses med en färgkodad bricka som visar vilket larmord som triggat händelsen.
  - Inkommande meddelanden över SSE (`/stream`) granskas i realtid: meddelanden med larmträff infogas direkt högst upp med pulserande markering, medan övriga meddelanden ignoreras i denna vy.
  - Sökfunktion i realtid och historisk bläddring via infinite scroll mot backend (`/api/messages?alerts_only=1&before_id=...`).
  - Snabbknappar för att skydda/låsa meddelanden mot automatisk rensning samt radera meddelanden.
  - Snabbmodal för att namnge eller dölja CapCodes direkt från tabellen.

### 2. Backend och Databasstöd
- **`database.py`**:
  - `get_recent_messages` har utökats med stöd för `alerts_only=True`.
  - Frågan använder optimerad SQL för att matcha mot aktiva ord i tabellen `alert_words`:
    ```sql
    EXISTS (
        SELECT 1 FROM alert_words aw
        WHERE aw.is_active = 1
        AND (
            m.message LIKE '%' || aw.word || '%'
            OR UPPER(m.message) LIKE '%' || UPPER(aw.word) || '%'
        )
    )
    ```
- **`app.py`**:
  - API-endpointen `/api/messages` läser parametern `alerts_only` (t.ex. `?alerts_only=1`) och anropar databasen med filtret.
  - Rutt `/larm` renderar `templates/larm.html`.

### 3. HTTP-säkerhet och Autentisering
- **Miljövariabler i `docker-compose.yml`**:
  ```yaml
  environment:
    - AUTH_USER=${AUTH_USER:-admin}
    - AUTH_PASS=${AUTH_PASS:-}
  ```
- **HTTP Basic Auth**:
  - Aktiveras om `AUTH_PASS` är angivet. Om tomt körs appen i öppet läge (bakåtkompatibelt).
  - Jämförelse sker med `hmac.compare_digest` med UTF-8-kodning för att förhindra timing-attacker och hantera svenska tecken.
- **Säkerhetsheaders på alla HTTP-svar**:
  - `X-Frame-Options: SAMEORIGIN` (förhindrar Clickjacking).
  - `X-Content-Type-Options: nosniff` (stoppar MIME-sniffing).
  - `X-XSS-Protection: 1; mode=block`.
  - `Referrer-Policy: strict-origin-when-cross-origin`.
  - `Content-Security-Policy`.
- **Payload-begränsning**:
  - `app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024` (2 MB) för att förhindra överbelastningsattacker (DoS via minnesutmattning).

### 4. Automatiserade tester
- Skapat `tests/test_security_and_larm.py` och flyttat `tests/test_imports.py`:
  - Verifierar att `/larm` svarar med 200 OK och rätt element.
  - Verifierar att säkerhetsheaders returneras.
  - Verifierar att `alerts_only=1` endast returnerar larmade händelser.
  - Verifierar att HTTP Basic Auth blockerar obehöriga och tillåter behöriga anrop.
- Samtliga tester i testsviten körs och passerar.

### 5. Reposanering och källkodsskydd
- **Borttagning av temporära filer och scratch-skript**:
  - Samtliga diff-filer (`*.diff`, `*.txt`), temporära testscheman och äldre testskript som tidigare råkat spåras i Git har tagits bort (`git rm`).
- **Anonymisering av konfiguration**:
  - Hårdkodade interna IP-adresser och användarnamn har ersatts med generiska miljövariabler med fallback-värden i `docker-compose.yml`.
- **Härdad `.gitignore`**:
  - Utökad för att permanent blockera lokala databaser (`*.db`, `*.sqlite3`), loggfiler, diffar, cache-kataloger och `.env`-filer från att nå GitHub.
- **Uppdaterad README.md**:
  - Helt omskriven på svenska, anpassad för CalVer `2026.10.11` och fri från emojis.
