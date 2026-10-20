import os
import json
import re

# Modulär parser för att översätta råa ACARS/VDL2-meddelanden till läsbar text
# samt berika med ACARSHUB-liknande metadata (flygbolag, markstationer, länkstatus m.m.).
# STRIKT KRAV: Inga emojis får förekomma i denna modul eller dess formaterade utdata.

DATA_FILE = os.path.join(os.path.dirname(__file__), 'acars_reference_data.json')

AIRLINE_MAP = {}
GROUND_STATIONS = {}
ACARS_LABELS = {}

# Inbäddade basdata som fallback om referensfilen saknas
FALLBACK_AIRLINES = {
    'ET': 'Ethiopian Airlines',
    'ETH': 'Ethiopian Airlines',
    'SK': 'SAS',
    'SAS': 'SAS Scandinavian Airlines',
    'AY': 'Finnair',
    'FIN': 'Finnair',
    'DY': 'Norwegian',
    'D8': 'Norwegian',
    'NOZ': 'Norwegian Air Shuttle',
    'NAX': 'Norwegian Air Shuttle',
    'NSZ': 'Norwegian Air Sweden',
    'LH': 'Lufthansa',
    'DLH': 'Lufthansa',
    'BA': 'British Airways',
    'BAW': 'British Airways',
    'KL': 'KLM',
    'KLM': 'KLM Royal Dutch',
    'AF': 'Air France',
    'AFR': 'Air France',
    'FR': 'Ryanair',
    'RYR': 'Ryanair',
    'W6': 'Wizz Air',
    'WZZ': 'Wizz Air',
    'BT': 'airBaltic',
    'BTI': 'airBaltic',
    'QR': 'Qatar Airways',
    'QTR': 'Qatar Airways',
    'EK': 'Emirates',
    'UAE': 'Emirates',
    'TK': 'Turkish Airlines',
    'THY': 'Turkish Airlines',
    'U2': 'easyJet',
    'EJU': 'easyJet Europe',
    'EZY': 'easyJet',
    'LX': 'Swiss International',
    'SWR': 'Swiss International',
    'OS': 'Austrian Airlines',
    'AUA': 'Austrian Airlines',
    'TF': 'Braathens Regional Airways',
    'BRX': 'Braathens Regional Airways',
    'FI': 'Icelandair',
    'ICE': 'Icelandair',
    'AMF': 'Amapola Flyg',
    'VKG': 'Sunclass Airlines',
    'TOM': 'TUI fly',
    'BLX': 'TUI fly Nordic',
    'UPS': 'UPS Airlines',
    'FDX': 'FedEx Express',
    'BCS': 'European Air Transport (DHL)',
    'BOX': 'AeroLogic (DHL)',
    'SWN': 'West Air Sweden',
    'SRK': 'Swedflight',
    'WIF': 'Widerøe'
}

FALLBACK_GROUND_STATIONS = {
    '119AAA': 'Arlanda Airport (ESSA)',
    '1153706': 'Arlanda Airport (ESSA)',
    '262439': 'Arlanda Airport (ESSA)',
    '111E93': 'Arlanda Airport (ESSA)',
    '119B1A': 'Landvetter Airport (ESGG)',
    '1198A6': 'Kastrup Airport (EKCH)',
    '1199A6': 'Gardermoen Airport (ENGM)',
    '1197A6': 'Helsinki Airport (EFHK)',
}

FALLBACK_LABELS = {
    'SA': 'Länkstatus (Media Advisory)',
    'B9': 'Begäran om flygplatsväder (ATIS)',
    'A9': 'Flygplatsväder (ATIS)',
    'B6': 'Begäran om färdtillstånd (PDC/DCL)',
    'A6': 'Begäran om färdtillstånd (PDC/DCL)',
    'BA': 'Oceanic Clearance',
    'AA': 'Oceanic Clearance',
    '10': 'Positionsrapport',
    '14': 'ETA / Beräknad ankomst',
    '15': 'Positionsrapport (Start / Takeoff)',
    '16': 'Positionsrapport (Landning / Touchdown)',
    '20': 'Positionsrapport (Bränsle & Prestanda)',
    '21': 'Positionsrapport (Motorrapport)',
    '38': 'Finnair Positions- och Väderrapport',
    '4J': 'Positionsrapport',
    'POS': 'Positionsrapport',
    'H1': 'FMS / Färddator-rapport',
    'MA': 'MIAM Komprimerad Telemetri',
    '80': 'Operativt meddelande / Dispatch (OUT)',
    '81': 'Operativt meddelande / Dispatch (OFF)',
    '82': 'Operativt meddelande / Dispatch (ON)',
    '83': 'Operativt meddelande / Dispatch (IN)',
    'RA': 'Operativt meddelande / Driftrapport',
    '5U': 'Väderbegäran / METAR',
    '57': 'Väderbegäran / METAR',
    'WX': 'Väderbegäran / METAR',
    '30': 'Väder / METAR / TAF',
    '44': 'Teknisk flygplansstatus',
    '4A': 'Motorövervakning (ECM)',
    '5D': 'Flygplatsväder (ATIS)',
    '5Z': 'Flygbolagsdata (Airline Designated)',
    '1L': 'Flygbolagsdata (Lufthansa Group AOC)',
    'H2': 'Meteorologisk rapport (AMDAR)',
    'Q0': 'Länktest (ACARS Link Test)',
    'Q1': 'Avgångsrapport (OOOI)',
    'Q2': 'Ankomstrapport (OOOI)',
    '_d': 'Kvittens (ACK)',
    'SQ': 'Transponder / Squawk',
    '_': 'Flygledning (ATC)'
}

FALLBACK_AIRPORTS = {
    # Norden:
    'ESSA': 'Stockholm/Arlanda',
    'ESSB': 'Stockholm/Bromma',
    'ESKN': 'Stockholm/Skavsta',
    'ESOW': 'Stockholm/Västerås',
    'ESGG': 'Göteborg/Landvetter',
    'ESMS': 'Malmö/Sturup',
    'ESSV': 'Visby',
    'ESDF': 'Ronneby/Kallinge',
    'ESCF': 'Linköping/Malmen',
    'ESSL': 'Linköping/Saab',
    'ESMQ': 'Kalmar',
    'ESMX': 'Växjö',
    'ESTA': 'Ängelholm',
    'ESMT': 'Halmstad',
    'ESGJ': 'Jönköping',
    'ESGT': 'Trollhättan',
    'ESOE': 'Örebro',
    'ESOK': 'Karlstad',
    'ESSD': 'Borlänge',
    'ESNN': 'Sundsvall',
    'ESNZ': 'Östersund/Åre',
    'ESNU': 'Umeå',
    'ESNK': 'Kramfors',
    'ESNS': 'Skellefteå',
    'ESPA': 'Luleå/Kallax',
    'ESPE': 'Vidsel',
    'ESNQ': 'Kiruna',
    'ESNG': 'Gällivare',
    'EKCH': 'Köpenhamn/Kastrup',
    'EKBI': 'Billund',
    'EKYT': 'Aalborg',
    'ENGM': 'Oslo/Gardermoen',
    'ENTO': 'Oslo/Torp',
    'ENBR': 'Bergen/Flesland',
    'ENVA': 'Trondheim/Værnes',
    'ENZV': 'Stavanger/Sola',
    'ENTC': 'Tromsø',
    'ENBO': 'Bodø',
    'EFHK': 'Helsingfors/Vanda',
    'EFTU': 'Åbo',
    'EFTP': 'Tammerfors',
    'EFOU': 'Uleåborg',
    'EFRO': 'Rovaniemi',
    'EFVA': 'Vasa',
    'BIKF': 'Reykjavik/Keflavik',

    # Baltikum & Polen:
    'EETN': 'Tallinn',
    'EVRA': 'Riga',
    'EYVI': 'Vilnius',
    'EYKA': 'Kaunas',
    'EPWA': 'Warszawa/Chopin',
    'EPMO': 'Warszawa/Modlin',
    'EPGD': 'Gdansk',
    'EPKK': 'Krakow',
    'EPWR': 'Wroclaw',
    'EPPO': 'Poznan',
    'EPKT': 'Katowice',

    # Övriga Europa & Världen:
    'EDDF': 'Frankfurt',
    'EDDM': 'München',
    'EDDB': 'Berlin/Brandenburg',
    'EDDL': 'Düsseldorf',
    'EDDH': 'Hamburg',
    'EDDK': 'Köln/Bonn',
    'EDDS': 'Stuttgart',
    'EDDP': 'Leipzig',
    'EHAM': 'Amsterdam/Schiphol',
    'EHEH': 'Eindhoven',
    'EBBR': 'Bryssel',
    'EBCI': 'Charleroi',
    'ELLX': 'Luxemburg',
    'EGLL': 'London/Heathrow',
    'EGKK': 'London/Gatwick',
    'EGSS': 'London/Stansted',
    'EGGW': 'London/Luton',
    'EGLC': 'London/City',
    'EGCC': 'Manchester',
    'EGPH': 'Edinburgh',
    'EIDW': 'Dublin',
    'LFPG': 'Paris/Charles de Gaulle',
    'LFPO': 'Paris/Orly',
    'LFMN': 'Nice',
    'LFLL': 'Lyon',
    'LSZH': 'Zürich',
    'LSGG': 'Genève',
    'LOWW': 'Wien/Schwechat',
    'LOWI': 'Innsbruck',
    'LKPR': 'Prag',
    'LHBP': 'Budapest/Ferenc Liszt',
    'LROP': 'Bukarest/Otopeni',
    'LBSF': 'Sofia',
    'LGAV': 'Aten',
    'LTFM': 'Istanbul',
    'LTFJ': 'Istanbul/Sabiha Gökçen',
    'LTAI': 'Antalya',
    'LEMD': 'Madrid/Barajas',
    'LEBL': 'Barcelona/El Prat',
    'LEMG': 'Málaga',
    'LEPA': 'Palma de Mallorca',
    'LPPT': 'Lissabon',
    'LIRF': 'Rom/Fiumicino',
    'LIMC': 'Milano/Malpensa',
    'LIME': 'Milano/Bergamo',
    'LIPZ': 'Venedig',
    'OMDB': 'Dubai',
    'OTHH': 'Doha/Hamad',
    'KJFK': 'New York/JFK',
    'KEWR': 'New York/Newark',
    'KORD': "Chicago/O'Hare",
    'ZBAA': 'Peking/Capital',
    'ZSPD': 'Shanghai/Pudong',
    'RJTT': 'Tokyo/Haneda',
    'VTBS': 'Bangkok/Suvarnabhumi',
    'HAAB': 'Addis Abeba/Bole'
}


AIRPORTS = dict(FALLBACK_AIRPORTS)

def load_reference_data():
    """Laddar referensdata från acars_reference_data.json med fallback till inbäddade data."""
    global AIRLINE_MAP, GROUND_STATIONS, ACARS_LABELS, AIRPORTS
    AIRLINE_MAP = dict(FALLBACK_AIRLINES)
    GROUND_STATIONS = dict(FALLBACK_GROUND_STATIONS)
    ACARS_LABELS = dict(FALLBACK_LABELS)
    AIRPORTS = dict(FALLBACK_AIRPORTS)

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'airlines' in data and isinstance(data['airlines'], dict):
                    AIRLINE_MAP.update(data['airlines'])
                if 'ground_stations' in data and isinstance(data['ground_stations'], dict):
                    GROUND_STATIONS.update(data['ground_stations'])
                if 'labels' in data and isinstance(data['labels'], dict):
                    ACARS_LABELS.update(data['labels'])
                if 'airports' in data and isinstance(data['airports'], dict):
                    AIRPORTS.update(data['airports'])
        except Exception:
            pass

# Ladda vid import
load_reference_data()

try:
    import airportsdata
    _AIRPORTSDATA_ICAO = airportsdata.load('ICAO')
except Exception:
    _AIRPORTSDATA_ICAO = {}

def _clean_airport_name(ap_dict: dict) -> str:
    if not ap_dict:
        return ""
    city = (ap_dict.get('city') or '').strip()
    name = (ap_dict.get('name') or '').strip()
    clean = re.sub(
        r'\s+(?:International|Intercontinental)?\s*(?:Airport|Air Base|Airbase|Aerodrome|Field|Heliport)\b.*$',
        '',
        name,
        flags=re.IGNORECASE
    ).strip()
    if not clean:
        clean = name
    if city and clean:
        if clean.lower().startswith(city.lower()):
            rest = clean[len(city):].strip(' -/')
            return f"{city}/{rest}" if rest else city
        return f"{city}/{clean}"
    return city or clean

# Ord och förkortningar som har 4 versaler men INTE är ICAO-flygplatser
INVALID_ICAO_WORDS = {
    'BLND', 'DEAF', 'WCHC', 'WCHS', 'WCHR', 'TRUE', 'FALS', 'NONE', 'MALE', 'FEMA',
    'CREW', 'PASS', 'HIGH', 'LOWS', 'OPEN', 'CLOS', 'FROM', 'DEST', 'FUEL', 'TAXI',
    'TRIP', 'TIME', 'DATA', 'TEXT', 'DATE', 'INFO', 'LOAD', 'STAT', 'TYPE', 'CODE',
    'NAME', 'NEXT', 'LAST', 'ACAR', 'VDL2', 'FREQ', 'CALL', 'FLIG', 'MSGS', 'WIND',
    'TEMP', 'KNOT', 'FEET', 'AUTO', 'MANU', 'CONF', 'REQ', 'REQU', 'REPL', 'SEND',
    'RECV', 'RCVD', 'NULL', 'POSI', 'POSN', 'FL00', 'FL10', 'FL20', 'FL30', 'FL40',
    'KG00', 'LB00', 'TEST', 'FAIL', 'OKAY', 'WARN', 'STOP', 'WAIT', 'HOLD', 'GATE',
    'MINS', 'SECS', 'DEGS', 'LEFT', 'RGHT', 'BACK', 'FORW', 'PACK', 'APPR', 'DEPT',
    'ARRV', 'CLRC', 'PUSH', 'PULL', 'TAKE', 'LAND', 'CLMB', 'DESC', 'CRUS', 'EXEC',
    'STAN', 'MAST', 'SLAV', 'CONT', 'SLOW', 'FAST', 'NORM', 'ABN',
    'ELEV', 'FLAP', 'SLAT', 'RUDD', 'AILN', 'SPOI', 'GEAR', 'BRAK', 'TIRE', 'WHEL'
}

def is_valid_icao_code(code: str) -> bool:
    """Validerar om en 4-ställig sträng är en trovärdig ICAO-flygplatskod."""
    if not code or len(code) != 4 or not code.isupper() or not code.isalpha():
        return False
    if code in INVALID_ICAO_WORDS:
        return False
    if code in AIRPORTS:
        return True
    if _AIRPORTSDATA_ICAO and code in _AIRPORTSDATA_ICAO:
        return True
    # Kända internationella ICAO-prefix
    KNOWN_PREFIXES = (
        'ES', 'EN', 'EF', 'EK', 'EG', 'ED', 'ET', 'LF', 'LE', 'LI', 'LH',
        'LO', 'LS', 'EH', 'EB', 'EP', 'LK', 'LT', 'LG', 'LP', 'LR', 'LB',
        'LZ', 'LY', 'LD', 'LJ', 'BK', 'EY', 'EV', 'EE', 'BI', 'DA', 'DT',
        'HE', 'LL', 'OE', 'OM', 'OB', 'OT', 'OK', 'OI', 'OO', 'OR', 'OS',
        'RC', 'RJ', 'RK', 'RO', 'RP', 'VT', 'VV', 'WM', 'WS', 'YB', 'SA',
        'SB', 'SC', 'SK', 'SP', 'SU', 'SV', 'UB', 'UG', 'UD', 'UK', 'UM'
    )
    if code.startswith(('K', 'C')) or code[:2] in KNOWN_PREFIXES:
        return True
    return False

def is_valid_airport_pair(orig: str, dest: str) -> bool:
    """Kontrollerar om två koder utgör ett giltigt flygplatspar och inte falska positiva som BLND/DEAF."""
    if not orig or not dest or orig == dest:
        return False
    if not (is_valid_icao_code(orig) and is_valid_icao_code(dest)):
        return False
    return True

def find_valid_route_pair(text: str):
    """
    Söker efter giltiga flygplatspar (t.ex. ESSA-LHBP eller ESSA/EKCH) och ignorerar icke-flygplatser.
    Returnerar (orig, dest) eller None.
    """
    if not text:
        return None
    # 1. 4-ställiga ICAO-koder med bindestreck eller snedstreck
    for m in re.finditer(r'\b([A-Z]{4})[-/]([A-Z]{4})\b', text):
        orig, dest = m.group(1), m.group(2)
        if is_valid_airport_pair(orig, dest):
            return orig, dest
    # 2. 3-ställiga koder som fallback om de inte är telemetriord
    for m in re.finditer(r'\b([A-Z]{3})[-/]([A-Z]{3})\b', text):
        orig, dest = m.group(1), m.group(2)
        if orig not in ('MIN', 'SEC', 'DEG', 'KMH', 'UTC', 'ETA', 'FOB', 'ALT', 'POS') and \
           dest not in ('MIN', 'SEC', 'DEG', 'KMH', 'UTC', 'ETA', 'FOB', 'ALT', 'POS'):
            return orig, dest
    return None

def lookup_airport(icao_code: str) -> str:
    """Slår upp flygplatsnamn utifrån ICAO-kod (4 tecken)."""
    if not icao_code:
        return ""
    code = str(icao_code).strip().upper()
    return AIRPORTS.get(code, "")

def format_airport(icao_code: str) -> str:
    """Slår upp flygplatsnamn utifrån 4-ställig ICAO-kod och returnerar 'EKCH (Köpenhamn/Kastrup)'."""
    if not icao_code:
        return ""
    code = str(icao_code).strip().upper()
    name = lookup_airport(code)
    if name:
        return f"{code} ({name})"
    if _AIRPORTSDATA_ICAO and code in _AIRPORTSDATA_ICAO:
        clean = _clean_airport_name(_AIRPORTSDATA_ICAO[code])
        if clean:
            return f"{code} ({clean})"
    return code

def fix_untranslated_routes(text: str, metadata: dict = None) -> str:
    """
    Global säkerhetsspärr: Ersätter råa ICAO-koder i rutter med format_airport()
    om de inte redan följs av flygplatsnamn inom parentes.
    Rensar även bort överflödig text som '(Avgång/Ankomst)'.
    """
    if not text:
        return ""

    clean_text = re.sub(r'\s*\(Avgång/Ankomst\)', '', text)
    if 'Rutt:' not in clean_text:
        return clean_text

    def _replace_route(m):
        dep = m.group(1)
        dep_paren = m.group(2) or ''
        arr = m.group(3)
        arr_paren = m.group(4) or ''

        if not is_valid_airport_pair(dep, arr):
            return m.group(0)

        dep_str = f"{dep}{dep_paren}" if ('(' in dep_paren) else format_airport(dep)
        arr_str = f"{arr}{arr_paren}" if ('(' in arr_paren) else format_airport(arr)

        if isinstance(metadata, dict):
            metadata['dst_airport'] = arr

        return f"Rutt: {dep_str} → {arr_str}"

    pattern = r'Rutt:\s*([A-Z]{4})(\s*\([^)]+\))?\s*(?:→|->)\s*([A-Z]{4})(\s*\([^)]+\))?'
    return re.sub(pattern, _replace_route, clean_text)

def lookup_airline(flight_code: str) -> str:
    """Slår upp flygbolagsnamn utifrån callsign/flight via ICAO (3 tecken) eller IATA (2 tecken)."""
    if not flight_code:
        return ""
    code = str(flight_code).strip().upper()
    if len(code) >= 3 and code[:3] in AIRLINE_MAP:
        return AIRLINE_MAP[code[:3]]
    if len(code) >= 2 and code[:2] in AIRLINE_MAP:
        return AIRLINE_MAP[code[:2]]
    return ""

def lookup_ground_station(addr: str) -> str:
    """Slår upp namn på känd markstation utifrån hexadecimal eller decimal adress."""
    if not addr:
        return ""
    clean = str(addr).strip().upper()
    if clean in GROUND_STATIONS:
        return GROUND_STATIONS[clean]
    # Försök hex -> dec
    try:
        dec_val = str(int(clean, 16))
        if dec_val in GROUND_STATIONS:
            return GROUND_STATIONS[dec_val]
    except ValueError:
        pass
    # Försök dec -> hex
    try:
        if clean.isdigit():
            hex_val = hex(int(clean))[2:].upper()
            if hex_val in GROUND_STATIONS:
                return GROUND_STATIONS[hex_val]
    except ValueError:
        pass
    return ""

def lookup_label(label_code: str) -> str:
    """Slår upp beskrivning av en ACARS-etikett."""
    if not label_code:
        return ""
    lbl = str(label_code).strip().upper()
    if lbl in ACARS_LABELS:
        return ACARS_LABELS[lbl]
    if re.match(r'^[1-4][A-Z]$', lbl):
        return "Flygbolagsdata (AOC Intern)"
    return ""

# -----------------------------------------------------------------------------
# Airbus CMS / CFDIU / FDIMU Flygfaser och ATA-kapitel
# -----------------------------------------------------------------------------
AIRBUS_FLIGHT_PHASES = {
    '01': "Pre-flight",
    '02': "Taxi out",
    '03': "Take-off",
    '04': "Initial Climb",
    '05': "Climb",
    '06': "Cruise",
    '07': "Descent",
    '08': "Approach",
    '09': "Roll-out/Landing",
    '10': "Taxi in"
}

ATA_CHAPTERS = {
    '21': "Air Conditioning",
    '22': "Auto Flight",
    '23': "Communications",
    '24': "Electrical Power",
    '25': "Equipment/Furnishings",
    '26': "Fire Protection",
    '27': "Flight Controls",
    '28': "Fuel",
    '29': "Hydraulic Power",
    '30': "Ice & Rain Protection",
    '31': "Instruments/Recorders",
    '32': "Landing Gear",
    '33': "Lights",
    '34': "Navigation",
    '35': "Oxygen",
    '36': "Pneumatic",
    '38': "Water/Waste",
    '45': "Central Maint System (CMS)",
    '46': "Information Systems",
    '49': "APU",
    '52': "Doors",
    '70': "Engine",
    '71': "Engine",
    '72': "Engine",
    '73': "Engine",
    '74': "Engine",
    '75': "Engine",
    '76': "Engine",
    '77': "Engine",
    '78': "Engine",
    '79': "Engine",
    '80': "Engine"
}

def format_airbus_flight_phase(code: str):
    """Returnerar (phase_name, phase_code, phase_desc)."""
    c = str(code).strip() if code is not None else ""
    name = AIRBUS_FLIGHT_PHASES.get(c)
    if name:
        return name, c, f"{name} ({c})"
    return c or "Okänd", c, c if c else "Okänd"

def format_ata_chapter(c1: str, c2: str = "00", c3: str = "00"):
    """Returnerar (ata_code, ata_name, ata_desc)."""
    c1_s = str(c1).strip()
    c2_s = str(c2).strip()
    c3_s = str(c3).strip()
    ata_code = f"{c1_s}-{c2_s}-{c3_s}"
    name = ATA_CHAPTERS.get(c1_s)
    if not name:
        try:
            n = int(c1_s)
            if 70 <= n <= 80:
                name = "Engine"
        except (ValueError, TypeError):
            pass
    if name:
        return ata_code, name, f"{ata_code} ({name})"
    return ata_code, "", ata_code


def extract_acars_metadata(avlc: dict = None, acars: dict = None, vdl2_frame: dict = None) -> dict:
    """
    Extraherar strukturerade metadatafält för ACARS/VDL2.
    Returnerar en dictionary med reg, flight, airline, icao, station, to_addr, ground_status, label, label_desc.
    """
    if not avlc and isinstance(vdl2_frame, dict):
        avlc = vdl2_frame.get('avlc', {})
    if not acars and isinstance(avlc, dict):
        acars = avlc.get('acars', {})
    if not isinstance(avlc, dict):
        avlc = {}
    if not isinstance(acars, dict):
        acars = {}

    src = avlc.get('src', {}) if isinstance(avlc.get('src'), dict) else {}
    dst = avlc.get('dst', {}) if isinstance(avlc.get('dst'), dict) else {}

    # Tail / Reg
    reg = str(acars.get('reg') or '').strip()
    if reg:
        reg = re.sub(r'^\.+', '', reg).strip().upper()

    # Flight / Callsign
    flight = str(acars.get('flight') or '').strip().upper()
    airline = lookup_airline(flight) if flight else ""

    # ICAO Hex
    icao = str(src.get('addr') or '').strip().upper()
    if not icao and isinstance(vdl2_frame, dict):
        icao = str(vdl2_frame.get('icao') or vdl2_frame.get('hex') or vdl2_frame.get('addr') or '').strip().upper()

    # Ground Station / To Address
    to_addr = str(dst.get('addr') or '').strip().upper()
    if not to_addr and dst and not isinstance(dst, dict):
        to_addr = str(dst).strip().upper()

    station = ""
    if to_addr:
        gs = lookup_ground_station(to_addr)
        if gs:
            clean_gs = re.sub(r'[\(\)]', '', gs).replace(' Airport', '').strip()
            station = f"{clean_gs}" if clean_gs else to_addr
        else:
            station = to_addr

    # On Ground status
    status_raw = str(src.get('status') or '').strip().lower()
    ground_status = ""
    if 'on ground' in status_raw or status_raw == 'ground':
        ground_status = "On Ground"
    elif 'airborne' in status_raw or status_raw == 'air':
        ground_status = "Airborne"

    # Label
    label = str(acars.get('label') or '').strip()
    label_desc = lookup_label(label) if label else ""

    return {
        'reg': reg,
        'flight': flight,
        'airline': airline,
        'icao': icao,
        'station': station,
        'to_addr': to_addr,
        'ground_status': ground_status,
        'label': label,
        'label_desc': label_desc
    }

def build_acars_metadata_header(avlc: dict = None, acars: dict = None, vdl2_frame: dict = None) -> str:
    """
    Bygger en ren och strukturerad ACARS-metadata header utan pipe-tecken eller protokollbrus.
    Format:
    Flight: ET0715 (Ethiopian Airlines)   Reg: ET-ATK   ICAO: 040127   To: Arlanda (ESSA)   Status: Airborne
    """
    meta = extract_acars_metadata(avlc=avlc, acars=acars, vdl2_frame=vdl2_frame)
    parts = []
    if meta['flight']:
        if meta['airline']:
            parts.append(f"Flight: {meta['flight']} ({meta['airline']})")
        else:
            parts.append(f"Flight: {meta['flight']}")
    if meta['reg']:
        parts.append(f"Reg: {meta['reg']}")
    if meta['icao']:
        parts.append(f"ICAO: {meta['icao']}")
    if meta['station']:
        parts.append(f"To: {meta['station']}")
    if meta['ground_status']:
        parts.append(f"Status: {meta['ground_status']}")

    return "   ".join(parts)


def format_libacars_data(acars_dict: dict = None, xid_dict: dict = None, vdl2_frame: dict = None) -> str:
    """
    Extraherar strukturerad data som libacars i dumpvdl2 eller libacars_bridge redan har avkodat
    (t.ex. ARINC-622 ADS-C, ATS, CPDLC, MIAM och VDL2 XID).
    Berikar även acars_dict/metadata direkt med koordinater (lat, lon, alt_ft).
    """
    parts = []

    # 1. ARINC-622 och applikationslager från libacars
    if isinstance(acars_dict, dict):
        la_obj = acars_dict.get('libacars')
        arinc = acars_dict.get('arinc622')
        if not arinc and isinstance(la_obj, dict):
            arinc = la_obj.get('arinc622') or la_obj

        if isinstance(arinc, dict):
            # ADS-C rapport
            adsc = arinc.get('adsc')
            if isinstance(adsc, dict):
                brep = adsc.get('basic_report', adsc)
                if isinstance(brep, dict):
                    lat = brep.get('lat') or brep.get('latitude')
                    lon = brep.get('lon') or brep.get('longitude')
                    alt = brep.get('alt') or brep.get('altitude')
                    if lat is not None and lon is not None:
                        try:
                            f_lat = float(lat)
                            f_lon = float(lon)
                            pos_str = f"Position: {f_lat:.4f}, {f_lon:.4f}"
                            alt_str = f"Höjd: {int(float(alt))} ft" if alt is not None else ""
                            ads_lines = ["ADS-C Positionsrapport"]
                            w_items = []
                            if alt_str:
                                w_items.append(alt_str)
                            
                            # Väderdata i earth_ref
                            earth = adsc.get('earth_ref', {})
                            if isinstance(earth, dict):
                                wd = earth.get('wind_dir')
                                ws = earth.get('wind_spd')
                                temp = earth.get('temp')
                                if temp is not None:
                                    w_items.append(f"Temperatur: {temp} C")
                                if wd is not None and ws is not None:
                                    w_items.append(f"Vind: {wd} deg ({ws} kt)")
                            if w_items:
                                ads_lines.append("   ".join(w_items))
                            ads_lines.append(pos_str)
                            parts.append("\n".join(ads_lines))

                            # Berika metadata direkt om möjligt
                            if 'lat' not in acars_dict or acars_dict['lat'] is None:
                                acars_dict['lat'] = round(f_lat, 4)
                            if 'lon' not in acars_dict or acars_dict['lon'] is None:
                                acars_dict['lon'] = round(f_lon, 4)
                            if alt is not None and ('alt_ft' not in acars_dict or acars_dict['alt_ft'] is None):
                                acars_dict['alt_ft'] = int(float(alt))
                        except (ValueError, TypeError):
                            pass

            # CPDLC Flygledningsmeddelande
            cpdlc = arinc.get('cpdlc') or (la_obj.get('cpdlc') if isinstance(la_obj, dict) else None)
            if isinstance(cpdlc, dict):
                cpdlc_lines = ["CPDLC Flygledningsmeddelande"]
                extracted_texts = []
                for subkey in ('atc_uplink_msg', 'atc_downlink_msg', 'msg'):
                    sub = cpdlc.get(subkey)
                    if isinstance(sub, dict):
                        for k in ('text', 'descr', 'content', 'msg'):
                            if sub.get(k):
                                extracted_texts.append(str(sub[k]).strip())
                    elif isinstance(sub, list):
                        for item in sub:
                            if isinstance(item, dict):
                                for k in ('text', 'descr', 'content', 'msg'):
                                    if item.get(k):
                                        extracted_texts.append(str(item[k]).strip())
                            elif isinstance(item, str):
                                extracted_texts.append(item.strip())
                for k in ('text', 'msg', 'data'):
                    if cpdlc.get(k) and str(cpdlc[k]).strip() not in extracted_texts:
                        extracted_texts.append(str(cpdlc[k]).strip())
                if extracted_texts:
                    cpdlc_lines.extend(extracted_texts)
                    parts.append("\n".join(cpdlc_lines))
                else:
                    parts.append("CPDLC Flygledningsmeddelande")

            # ATS meddelanden
            ats = arinc.get('ats')
            if isinstance(ats, dict):
                ats_text = ats.get('text') or ats.get('data') or ''
                if ats_text:
                    parts.append(f"ATS Meddelande: {str(ats_text).strip()}")

    # 2. XID struktur (stationsinformation och handover)
    if isinstance(xid_dict, dict):
        vdl_params = xid_dict.get('vdl_params', {}) if isinstance(xid_dict.get('vdl_params'), dict) else {}
        dst_ap = vdl_params.get('dst_airport') or xid_dict.get('dst_airport')
        if dst_ap:
            parts.append(f"VDL2 Stationslänk: Destination {dst_ap}")

    return "\n".join(parts) if parts else ""


# ============================================================================
# MODULÄRA REGLER FÖR ACARS HUMAN PARSER (PORTADE FRÅN AIRFRAMES OCH ACARSHUB)
# ============================================================================

def parse_acars_payload(text: str, label: str = None, metadata: dict = None) -> dict:
    """
    Detaljavkodar meddelandetext (Payload Sub-parsing) för ACARS/VDL2.
    Identifierar och bryter ner kända strukturerade format:
      1. FM-rapporter (FM1, FM2, FM3, FMA m.fl.) med tid, ETA, koordinater, höjd och parametrar.
      2. OOOI-rapporter (OUT, OFF, ON, IN) med fas, flygplats, tider och bränsle (FOB).
      3. Väder (WX / WXRQ / METAR / TAF / ATIS) med begärda/rapporterade ICAO-flygplatser och data.
    Returnerar en strukturerad ordbok eller None om inget känt format matchas.
    Om metadata skickas med berikas det automatiskt med decoded_fields, lat, lon, alt_ft, eta.
    """
    if not text or not isinstance(text, str):
        return None

    stripped = text.strip()
    lbl = (label or '').strip().upper()
    result = None

    # -------------------------------------------------------------------------
    # 1. FM-rapporter (FM1, FM2, FM3, FMA):
    # Exempel: "FM3 194836,2147,N 57.686,E 18.017,33186,  399,80"
    # -------------------------------------------------------------------------
    m_fm = re.search(
        r'\b(FM[0-9A-Z]?)\s+(\d{6})\s*,\s*(\d{4})\s*,\s*([NS])\s*(\d{1,2}(?:\.\d+)?)\s*,\s*([EW])\s*(\d{1,3}(?:\.\d+)?)\s*,\s*(\d+)(?:,\s*(.+))?',
        stripped,
        re.IGNORECASE
    )
    if m_fm:
        fm_type = m_fm.group(1).upper()
        raw_time = m_fm.group(2)
        raw_eta = m_fm.group(3)
        ns_hemi = m_fm.group(4).upper()
        raw_lat = float(m_fm.group(5))
        ew_hemi = m_fm.group(6).upper()
        raw_lon = float(m_fm.group(7))
        raw_alt = int(m_fm.group(8))
        raw_extra = (m_fm.group(9) or '').strip()
        if raw_extra:
            raw_extra = re.sub(r',\s*', ', ', raw_extra)

        lat = -raw_lat if ns_hemi == 'S' else raw_lat
        lon = -raw_lon if ew_hemi == 'W' else raw_lon

        hh, mm, ss = raw_time[:2], raw_time[2:4], raw_time[4:6]
        time_utc = f"{hh}:{mm}:{ss}"

        eta_hh, eta_mm = raw_eta[:2], raw_eta[2:4]
        eta_formatted = f"{eta_hh}:{eta_mm}:00"

        alt_fmt = f"{raw_alt:,} ft".replace(',', ' ')
        pos_str = f"Lat {raw_lat:.3f}, Lon {raw_lon:.3f}" if (ns_hemi == 'N' and ew_hemi == 'E') else f"Lat {lat:.3f}, Lon {lon:.3f}"

        fields = {
            "Typ": f"Flight Report ({fm_type})",
            "Meddelandetid (UTC)": time_utc,
            "ETA (Beräknad ankomst)": eta_formatted,
            "Position": pos_str,
            "Höjd": alt_fmt
        }
        if raw_extra:
            fields["Övrig data"] = raw_extra

        result = {
            'report_type': f"Flight Report ({fm_type})",
            'type_code': fm_type,
            'msg_time_utc': time_utc,
            'time_utc': time_utc,
            'eta': eta_formatted,
            'eta_utc': eta_formatted,
            'lat': lat,
            'lon': lon,
            'pos_str': pos_str,
            'altitude_ft': raw_alt,
            'altitude_str': alt_fmt,
            'extra_data': raw_extra,
            'extra': raw_extra,
            'fields': fields
        }

    # -------------------------------------------------------------------------
    # 2. OOOI-rapporter (OUT, OFF, ON, IN):
    # Exempel: "OUT/ESSA/1234", "OFF ESSA 1245", "ON/EKCH/1330", "IN EKCH 1338", "OUT /ESSA 1015 /FOB 14500"
    # -------------------------------------------------------------------------
    elif (
        (re.search(r'(?:^|[\r\n/])\s*(OUT|OFF|ON|IN)(?:[\s/]+([A-Z]{3,4}))?(?:[\s/]+(\d{2}:?\d{2}(?::?\d{2})?))?', stripped, re.IGNORECASE))
        and (lbl in ('80', '81', '82', '83', 'Q1', 'Q2', '15', '16', '_D') or re.match(r'^(OUT|OFF|ON|IN)\b', stripped, re.IGNORECASE) or '/OUT' in stripped or '/OFF' in stripped or '/ON' in stripped or '/IN' in stripped)
    ):
        m_oooi = re.search(
            r'(?:^|[\r\n/])\s*(OUT|OFF|ON|IN)(?:[\s/]+([A-Z]{3,4}))?(?:[\s/]+(\d{2}:?\d{2}(?::?\d{2})?))?',
            stripped,
            re.IGNORECASE
        )
        event = m_oooi.group(1).upper()
        ap = m_oooi.group(2)
        ap_code = ap.upper() if ap and len(ap) in (3, 4) and ap.isalpha() else None
        if not ap_code:
            for w in re.findall(r'\b([A-Z]{4})\b', stripped):
                if is_valid_icao_code(w):
                    ap_code = w
                    break
        tm_raw = m_oooi.group(3)
        tm_formatted = None
        if tm_raw:
            digits = re.sub(r'\D', '', tm_raw)
            if len(digits) == 4:
                tm_formatted = f"{digits[:2]}:{digits[2:4]}:00"
            elif len(digits) >= 6:
                tm_formatted = f"{digits[:2]}:{digits[2:4]}:{digits[4:6]}"
            else:
                tm_formatted = tm_raw

        desc_map = {
            'OUT': 'Pushback från gate (OUT)',
            'OFF': 'Startat från bana (OFF)',
            'ON': 'Landat på bana (ON)',
            'IN': 'Parkerat vid gate (IN)'
        }
        event_desc = desc_map.get(event, event)

        # Extrahera FOB om det finns
        fob_str = None
        fob_val_raw = None
        m_fob = re.search(r'(?:/FOB\s*|\bFOB\s*[:=]?\s*)(\d{3,5})\b', stripped)
        if m_fob:
            fob_val_raw = m_fob.group(1)
            val = int(fob_val_raw)
            fob_kg = val * 100 if len(fob_val_raw) == 3 else (val * 10 if len(fob_val_raw) == 4 else val)
            fob_str = f"{fob_kg:,} kg".replace(',', ' ')

        fields = {
            "Typ": f"OOOI ({event})",
            "Händelse": event_desc
        }
        if ap_code:
            fields["Flygplats"] = format_airport(ap_code)
        if tm_formatted:
            fields["Tid (UTC)"] = tm_formatted
        if fob_str:
            fields["Bränsle (FOB)"] = fob_str

        result = {
            'report_type': f"OOOI ({event})",
            'type_code': event,
            'oooi_event': event,
            'oooi_desc': event_desc,
            'airport': ap_code,
            'msg_time_utc': tm_formatted,
            'time_utc': tm_formatted,
            'fob': fob_str,
            'fuel_on_board': fob_val_raw or fob_str,
            'fields': fields
        }

    # -------------------------------------------------------------------------
    # 3. Väder (WX / WXRQ / METAR / TAF / ATIS):
    # Exempel: "/ARN.TI2/026ESSA0700A", "METAR ESSA 161950Z ...", "WXRQ ESSA EKCH"
    # -------------------------------------------------------------------------
    elif (
        re.search(r'/([A-Z]{4})\.TI2/(?:\d{1,4}\1)?([AD])?', stripped, re.IGNORECASE)
        or lbl in ('5U', '57', 'WX', '30', '5D', 'B9', 'A9')
        or 'METAR' in stripped.upper()
        or 'ATIS' in stripped.upper()
        or 'TAF' in stripped.upper()
        or 'WXRQ' in stripped.upper()
    ):
        m_atis = re.search(r'/([A-Z]{4})\.TI2/(?:\d{1,4}\1)?([AD])?', stripped, re.IGNORECASE)
        found_airports = []
        atis_icao = None
        atis_type = None

        if m_atis:
            atis_icao = m_atis.group(1).upper()
            found_airports.append(atis_icao)
            atis_type = m_atis.group(2).upper() if m_atis.group(2) else ""

        # Hitta övriga ICAO-koder
        for m in re.finditer(r'\b([A-Z]{4})\b', stripped):
            c = m.group(1).upper()
            if is_valid_icao_code(c) and c not in found_airports:
                found_airports.append(c)

        is_metar = bool(re.search(r'\bMETAR\b', stripped, re.IGNORECASE))
        is_taf = bool(re.search(r'\bTAF\b', stripped, re.IGNORECASE))
        is_atis = bool(atis_icao or lbl in ('5D', 'B9', 'A9') or '.TI2' in stripped or re.search(r'\bATIS\b', stripped, re.IGNORECASE))

        if is_metar:
            rep_type = "Väderrapport (METAR)"
            w_type = "METAR"
        elif is_taf:
            rep_type = "Flygplatsprognos (TAF)"
            w_type = "TAF"
        elif is_atis:
            rep_type = "Flygplatsväder (ATIS)"
            w_type = "ATIS"
        elif 'WXRQ' in stripped or 'WX REQ' in stripped:
            rep_type = "Väderbegäran (WXRQ)"
            w_type = "WXRQ"
        else:
            rep_type = "Väderdata"
            w_type = "WX"

        fields = {
            "Typ": rep_type
        }
        if found_airports:
            fields["Flygplatser"] = ", ".join([format_airport(a) for a in found_airports])
        if atis_type:
            fields["ATIS-typ"] = "Arrival (Landning)" if atis_type == 'A' else ("Departure (Start)" if atis_type == 'D' else atis_type)

        primary_ap = found_airports[0] if found_airports else None
        result = {
            'report_type': rep_type,
            'type_code': 'WX',
            'airport': primary_ap,
            'wx_airport': primary_ap,
            'airports': found_airports,
            'weather_type': w_type,
            'wx_type': w_type,
            'fields': fields
        }

    # -------------------------------------------------------------------------
    # 4. Airbus Cockpit Warning (WRN / Label H1):
    # Exempel: "WRN/PNRC12860AA07/WN26101816350034000006NAV ADS-B TRAF FAULT"
    # -------------------------------------------------------------------------
    elif 'WRN/' in stripped or '/WRN/' in stripped or re.search(r'\bWRN\/', stripped):
        clean_text = stripped.replace('\r', '').replace('\n', ' ').strip('\x03\x17 ')
        m_wrn = re.search(
            r'WRN\/PN(?:R|\b)?([A-Z0-9]+)\/WN(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\s*([^\r\n\x03\x17]+)',
            clean_text
        )
        if m_wrn:
            pnr = m_wrn.group(1).strip()
            if pnr.startswith('R') and len(pnr) > 7:
                pnr = pnr[1:]

            yy, mm, dd = m_wrn.group(2), m_wrn.group(3), m_wrn.group(4)
            date_str = f"20{yy}-{mm}-{dd}"

            hh, mn, ss = m_wrn.group(5), m_wrn.group(6), m_wrn.group(7)
            time_str = f"{hh}:{mn}:{ss}"

            c1, c2, c3 = m_wrn.group(8), m_wrn.group(9), m_wrn.group(10)
            ata_code, ata_name, ata_desc = format_ata_chapter(c1, c2, c3)

            phase_code = m_wrn.group(11)
            phase_name, _, phase_desc = format_airbus_flight_phase(phase_code)

            ecam_warning = m_wrn.group(12).strip().rstrip('/\x03\x17 ')

            fields = {
                "Typ": "Airbus ECAM-Varning",
                "Larm": ecam_warning,
                "ATA": ata_desc,
                "Flygfas": phase_desc,
                "Tid": f"{time_str} UTC",
                "Artikelnummer (PNR)": pnr,
                "Datum": date_str
            }
            result = {
                'report_type': 'Airbus ECAM-Varning',
                'type_code': 'WRN',
                'is_warning': True,
                'severity': 'warning',
                'pnr': pnr,
                'date': date_str,
                'flight_time_utc': time_str,
                'time_utc': time_str,
                'ata': ata_code,
                'ata_name': ata_name,
                'ata_desc': ata_desc,
                'phase': phase_name,
                'phase_code': phase_code,
                'phase_desc': phase_desc,
                'warning_text': ecam_warning,
                'fault_text': ecam_warning,
                'summary': f"Larm: {ecam_warning} | ATA: {ata_desc} | Fas: {phase_desc} | Tid: {time_str} UTC (PNR: {pnr})",
                'fields': fields
            }
        else:
            # Fallback för avvikande / korta WRN/PN-meddelanden
            m_pnr = re.search(r'(?:/PNR|\bPNR|/PN|\bPN)\s*([A-Z0-9]+)', clean_text)
            pnr = m_pnr.group(1).strip() if m_pnr else None
            if pnr and pnr.startswith('R') and len(pnr) > 7:
                pnr = pnr[1:]
            m_fb = re.search(r'WRN\/PN(?:R|\b)?([A-Z0-9]+)?(?:\/WN([^\/\r\n\x03\x17]+))?\/?\s*([^\r\n\x03\x17]+)?', clean_text)
            desc = (m_fb.group(3) or '').strip().rstrip('/\x03\x17 ') if m_fb else "ECAM Varning"
            if not desc:
                desc = "ECAM Varning"
            fields = {"Typ": "Airbus ECAM-Varning", "Larm": desc}
            if pnr:
                fields["Artikelnummer (PNR)"] = pnr
            result = {
                'report_type': 'Airbus ECAM-Varning',
                'type_code': 'WRN',
                'is_warning': True,
                'severity': 'warning',
                'pnr': pnr,
                'warning_text': desc,
                'fault_text': desc,
                'summary': f"Larm: {desc}",
                'fields': fields
            }

    # -------------------------------------------------------------------------
    # 5. Airbus Maintenance / Fault Report (FLR / REP003 / ARINC 624 / Label H1):
    # Exempel: "A320,029566,1,1,TB000000/REP003,64,01,1/CCHB-JDF,OCT17,043255,ESSA,LSZH,0001/.../FLR/PNRC12860AA07/FR26101704390034363106MMR 1+2 (40RT1+2)/     ATC 1 (1SH1)/IDATC 1,ATC 2"
    # -------------------------------------------------------------------------
    elif '/FLR/' in stripped or 'FLR/' in stripped or (re.search(r'\bREP[0-9]{3}\b', stripped) and re.search(r'/FR[0-9]{10,25}', stripped)):
        normalized = re.sub(r'[\r\n\x03\x17]+', '', stripped)

        # 1. Flygplanstyp
        ac_type = None
        m_ac = re.search(r'^(A[0-9]{3})\b', normalized)
        if m_ac:
            ac_type = m_ac.group(1)

        # 2. Rapporttyp
        rep_type = None
        m_rep = re.search(r'/REP([0-9]{3})\b', normalized)
        if m_rep:
            rep_type = f"REP{m_rep.group(1)}"

        # 3. Registrering
        reg = None
        m_reg = re.search(r'/CC([A-Z0-9-]+),', normalized)
        if m_reg:
            reg = m_reg.group(1).strip()

        # 4. Rutt och flygtid
        origin = None
        destination = None
        flight_time = None
        m_route = re.search(r',(\d{6}),([A-Z]{4}),([A-Z]{4})\b', normalized)
        if m_route:
            t_raw = m_route.group(1)
            flight_time = f"{t_raw[:2]}:{t_raw[2:4]}:{t_raw[4:6]}"
            origin = m_route.group(2)
            destination = m_route.group(3)

        # 5. CEN bonus-extraktion (Höjd, CAS-fart, Mach)
        alt_raw = None
        alt_fmt = None
        spd_raw = None
        mach_raw = None
        m_cen = re.search(r'\/CEN\d{3},(\d+),(\d+),(\d+)', normalized)
        if m_cen:
            alt_raw = int(m_cen.group(1))
            spd_raw = int(m_cen.group(2))
            mach_raw = m_cen.group(3)
            alt_fmt = f"{alt_raw:,} ft".replace(',', ' ')

        # 6. FLR mönster
        m_flr = re.search(
            r'\/?FLR\/PN(?:R|\b)?([A-Z0-9]+)\/FR(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})([^\/\r\n\x03\x17]+)(?:\/\s*([^\/\r\n\x03\x17]+))?(?:\/ID([^\r\n\x03\x17]+))?',
            normalized
        )

        pnr = None
        date_str = None
        flr_time_str = None
        ata_code, ata_name, ata_desc = "", "", ""
        phase_code, phase_name, phase_desc = "", "", ""
        comp1 = None
        comp2 = None
        aff_id = None
        fel_part = None

        if m_flr:
            pnr = m_flr.group(1).strip()
            if pnr.startswith('R') and len(pnr) > 7:
                pnr = pnr[1:]
            yy, mm, dd = m_flr.group(2), m_flr.group(3), m_flr.group(4)
            date_str = f"20{yy}-{mm}-{dd}"
            hh, mn, ss = m_flr.group(5), m_flr.group(6), m_flr.group(7)
            flr_time_str = f"{hh}:{mn}:{ss}"

            c1, c2, c3 = m_flr.group(8), m_flr.group(9), m_flr.group(10)
            ata_code, ata_name, ata_desc = format_ata_chapter(c1, c2, c3)

            phase_code = m_flr.group(11)
            phase_name, _, phase_desc = format_airbus_flight_phase(phase_code)

            comp1 = m_flr.group(12).strip()
            comp2 = (m_flr.group(13) or '').strip()
            aff_id = (m_flr.group(14) or '').strip()

            if comp2.startswith('ID'):
                if not aff_id:
                    aff_id = comp2[2:].strip()
                comp2 = ''

            if comp2:
                fel_part = f"{comp1} & {comp2}"
            else:
                fel_part = comp1
            if aff_id:
                fel_part += f" [Påverkar: {aff_id}]"

        is_rep003 = bool(rep_type or m_ac)
        rep_label = f"Airbus FDIMU/Systemrapport #{m_rep.group(1) if m_rep else '003'}" if is_rep003 else "Airbus CFDIU-Felrapport"

        fields = {
            "Typ": rep_label
        }
        if fel_part:
            fields["Fel"] = fel_part
        elif comp1:
            fields["Fel"] = comp1
        if ata_desc:
            fields["ATA"] = ata_desc
        if phase_desc:
            fields["Flygfas"] = phase_desc
        if pnr:
            fields["Artikelnummer (PNR)"] = pnr
        if flr_time_str or flight_time:
            fields["Tid"] = f"{flr_time_str or flight_time} UTC"
        if alt_fmt:
            fields["Höjd"] = f"{alt_fmt} ({spd_raw} kt)"
        if ac_type:
            fields["Flygplan"] = f"Airbus {ac_type}"
        if origin and destination:
            fields["Rutt"] = f"{format_airport(origin)} → {format_airport(destination)}"

        result = {
            'report_type': rep_label,
            'type_code': 'FLR',
            'is_fault_report': True,
            'severity': 'fault',
            'aircraft_type': ac_type,
            'report_code': rep_type,
            'reg': reg,
            'origin': origin,
            'destination': destination,
            'route': f"{origin} -> {destination}" if (origin and destination) else None,
            'flight_time_utc': flr_time_str or flight_time,
            'time_utc': flr_time_str or flight_time,
            'pnr': pnr,
            'date': date_str,
            'ata': ata_code,
            'ata_name': ata_name,
            'ata_desc': ata_desc,
            'phase': phase_name,
            'phase_code': phase_code,
            'phase_desc': phase_desc,
            'component1': comp1,
            'component2': comp2,
            'affected_systems': aff_id,
            'affected': [a.strip() for a in aff_id.split(',')] if aff_id else ([comp2] if comp2 else []),
            'fault_desc': comp1 or "Felrapport",
            'fault_text': fel_part or comp1 or "Felrapport",
            'alt_ft': alt_raw,
            'cas_kt': spd_raw,
            'mach': mach_raw,
            'fields': fields
        }

    if result and isinstance(metadata, dict):
        metadata['decoded_fields'] = result
        if result.get('lat') is not None and result.get('lon') is not None:
            metadata['lat'] = result['lat']
            metadata['lon'] = result['lon']
        if result.get('altitude_ft') is not None:
            metadata['alt_ft'] = result['altitude_ft']
        if result.get('eta'):
            metadata['eta'] = result['eta']
        if result.get('destination') and not metadata.get('dst_airport'):
            metadata['dst_airport'] = result['destination']
        if result.get('origin') and not metadata.get('src_airport'):
            metadata['src_airport'] = result['origin']
        if result.get('reg') and not metadata.get('reg'):
            metadata['reg'] = result['reg']

    return result


def rule_fm_flight_report(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Avkodar strukturerade FM-rapporter (FM1, FM2, FM3):
    Exempel: FM3 194836,2147,N 57.686,E 18.017,33186,  399,80
    Presenterande fält:
      - Typ: Flight Report (FM3)
      - Meddelandetid (UTC): 19:48:36
      - ETA: 21:47:00
      - Position: Lat 57.686, Lon 18.017
      - Höjd: 33 186 ft
      - Övrigt: 399, 80
    """
    parsed = parse_acars_payload(text, label=label)
    if not parsed or not parsed.get('type_code', '').startswith('FM'):
        return None

    if isinstance(metadata, dict):
        metadata['decoded_fields'] = parsed
        if parsed.get('lat') is not None and parsed.get('lon') is not None:
            metadata['lat'] = parsed['lat']
            metadata['lon'] = parsed['lon']
        if parsed.get('altitude_ft') is not None:
            metadata['alt_ft'] = parsed['altitude_ft']
        if parsed.get('eta'):
            metadata['eta'] = parsed['eta']

    parts = []
    if parsed.get('msg_time_utc'):
        parts.append(f"Tid: {parsed['msg_time_utc']} UTC")
    if parsed.get('eta'):
        parts.append(f"ETA: {parsed['eta']}")
    if parsed.get('altitude_str'):
        parts.append(f"Höjd: {parsed['altitude_str']}")
    if parsed.get('pos_str'):
        parts.append(f"Position: {parsed['pos_str']}")
    if parsed.get('extra_data'):
        parts.append(f"Övrigt: {parsed['extra_data']}")

    summary = "   ".join(parts)
    return f"{parsed['report_type']}   {summary}\nRådata: {text.strip()}"


def rule_airbus_ecam_warning(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Airbus ECAM Cockpit Warning (WRN / Label H1).
    Exempel: WRN/PNRC12860AA07/WN26101816350034000006NAV ADS-B TRAF FAULT
    """
    if not text or 'WRN/' not in text:
        return None

    clean_text = text.replace('\r', '').replace('\n', ' ').strip('\x03\x17 ')

    # 1. Mönster med 20-siffrig WN-kod:
    # Grupp 1: PNR
    # Grupp 2-4: Datum (20YY-MM-DD)
    # Grupp 5-7: Tid (HH:MM:SS UTC)
    # Grupp 8-10: ATA-kapitel (XX-XX-XX) + namn
    # Grupp 11: Flygfas (Fasnamn (kod))
    # Grupp 12: ECAM-varning
    m = re.search(
        r'WRN\/PN(?:R|\b)?([A-Z0-9]+)\/WN(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\s*([^\r\n\x03\x17]+)',
        clean_text
    )

    if m:
        pnr = m.group(1).strip()
        if pnr.startswith('R') and len(pnr) > 7:
            pnr = pnr[1:]

        yy, mm, dd = m.group(2), m.group(3), m.group(4)
        date_str = f"20{yy}-{mm}-{dd}"

        hh, mn, ss = m.group(5), m.group(6), m.group(7)
        time_str = f"{hh}:{mn}:{ss}"

        c1, c2, c3 = m.group(8), m.group(9), m.group(10)
        ata_code, ata_name, ata_desc = format_ata_chapter(c1, c2, c3)

        phase_code = m.group(11)
        phase_name, _, phase_desc = format_airbus_flight_phase(phase_code)

        ecam_warning = m.group(12).strip().rstrip('/\x03\x17 ')

        if isinstance(metadata, dict):
            metadata['decoded_fields'] = {
                'report_type': 'Airbus ECAM-Varning',
                'type_code': 'WRN',
                'is_warning': True,
                'severity': 'warning',
                'pnr': pnr,
                'date': date_str,
                'flight_time_utc': time_str,
                'time_utc': time_str,
                'ata': ata_code,
                'ata_name': ata_name,
                'ata_desc': ata_desc,
                'phase': phase_name,
                'phase_code': phase_code,
                'phase_desc': phase_desc,
                'warning_text': ecam_warning,
                'fault_text': ecam_warning,
                'summary': f"Larm: {ecam_warning} | ATA: {ata_desc} | Fas: {phase_desc} | Tid: {time_str} UTC (PNR: {pnr})",
                'fields': {
                    "Typ": "Airbus ECAM-Varning",
                    "Larm": ecam_warning,
                    "ATA": ata_desc,
                    "Flygfas": phase_desc,
                    "Tid": f"{time_str} UTC",
                    "Artikelnummer (PNR)": pnr,
                    "Datum": date_str
                }
            }

        summary = f"[Airbus ECAM-Varning] Larm: {ecam_warning} | ATA: {ata_desc} | Fas: {phase_desc} | Tid: {time_str} UTC (PNR: {pnr})"
        return f"{summary}\nRådata: {text.strip()}"

    # 2. Fallback för korta / avvikande WRN/PN-meddelanden så att de aldrig faller igenom till [FMS/Systemtelemetri] Kodat datapaket
    m_fb = re.search(r'WRN\/PN(?:R|\b)?([A-Z0-9]+)?(?:\/WN([^\/\r\n\x03\x17]+))?\/?\s*([^\r\n\x03\x17]+)?', clean_text)
    if m_fb:
        pnr = (m_fb.group(1) or '').strip()
        if pnr.startswith('R') and len(pnr) > 7:
            pnr = pnr[1:]
        wn_raw = (m_fb.group(2) or '').strip()
        desc = (m_fb.group(3) or '').strip().rstrip('/\x03\x17 ')
        if not desc and wn_raw:
            desc = wn_raw
        if not desc:
            desc = "ECAM Varning"

        if isinstance(metadata, dict):
            metadata['decoded_fields'] = {
                'report_type': 'Airbus ECAM-Varning',
                'type_code': 'WRN',
                'is_warning': True,
                'severity': 'warning',
                'pnr': pnr,
                'warning_text': desc,
                'fault_text': desc,
                'summary': f"Larm: {desc}",
                'fields': {"Typ": "Airbus ECAM-Varning", "Larm": desc}
            }

        pnr_part = f" (PNR: {pnr})" if pnr else ""
        summary = f"[Airbus ECAM-Varning] Larm: {desc}{pnr_part}"
        return f"{summary}\nRådata: {text.strip()}"

    return None


def rule_airbus_fault_report(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Airbus Maintenance / Fault Report (FLR / REP003 / ARINC 624 / Label H1).
    Exempel: A320,029566,1,1,TB000000/REP003,64,01,1/CCHB-JDF,OCT17,043255,ESSA,LSZH,0001/.../FLR/PNRC12860AA07/FR26101704390034363106MMR 1+2 (40RT1+2)/     ATC 1 (1SH1)/IDATC 1,ATC 2
    """
    if not text:
        return None

    # Normalisera och rensa bort radbrytningar och kontrolltecken
    normalized = re.sub(r'[\r\n\x03\x17]+', '', text)

    # Kontrollera om meddelandet innehåller felrapport (FLR eller FR)
    has_flr = bool(re.search(r'\/?FLR\/', normalized) or '/FR' in normalized or 'FLR/' in normalized or re.search(r'\bFLR\b', normalized))
    if not has_flr:
        return None

    # 1. Flygplanstyp & rapportnummer från REP-header
    is_rep = bool(re.search(r'\bA\d{3}\b', normalized) or '/REP' in normalized or 'REP00' in normalized)
    ac_type = None
    rep_num = "003"
    orig_icao = None
    dest_icao = None
    time_utc = None
    reg = None

    m_hdr = re.search(
        r'(A\d{3})[^/]*/REP(\d+)[^/]*/CC([A-Z0-9-]+),([A-Z]{3}\d{2}),(\d{6}),([A-Z]{4}),([A-Z]{4})',
        normalized
    )
    if m_hdr:
        ac_type = m_hdr.group(1).strip()
        rep_num = m_hdr.group(2).strip()
        reg = m_hdr.group(3).strip()
        t_raw = m_hdr.group(5).strip()
        orig_icao = m_hdr.group(6).strip().upper()
        dest_icao = m_hdr.group(7).strip().upper()
        time_utc = f"{t_raw[0:2]}:{t_raw[2:4]}:{t_raw[4:6]}" if len(t_raw) == 6 else t_raw
    else:
        m_ac = re.search(r'\b(A\d{3})\b', normalized)
        if m_ac:
            ac_type = m_ac.group(1).strip()
        m_rep = re.search(r'/REP(\d+)', normalized)
        if m_rep:
            rep_num = m_rep.group(1).strip()
        m_route = re.search(r',(\d{6}),([A-Z]{4}),([A-Z]{4})\b', normalized)
        if m_route:
            t_raw = m_route.group(1).strip()
            time_utc = f"{t_raw[0:2]}:{t_raw[2:4]}:{t_raw[4:6]}" if len(t_raw) == 6 else t_raw
            orig_icao = m_route.group(2).strip().upper()
            dest_icao = m_route.group(3).strip().upper()

    if isinstance(metadata, dict):
        if dest_icao and not metadata.get('dst_airport'):
            metadata['dst_airport'] = dest_icao
        if orig_icao and not metadata.get('src_airport'):
            metadata['src_airport'] = orig_icao
        if reg and not metadata.get('reg'):
            metadata['reg'] = reg

    # 2. Bonus-extraktion ur CEN-segmentet (/CENddd,alt,cas,mach)
    alt_fmt = None
    spd_kt = None
    m_cen = re.search(r'\/CEN\d{3},(\d+),(\d+),(\d+)', normalized)
    if m_cen:
        alt_val = int(m_cen.group(1))
        spd_kt = int(m_cen.group(2))
        alt_fmt = f"{alt_val:,} ft".replace(',', ' ')
        if isinstance(metadata, dict):
            metadata['alt_ft'] = alt_val

    # 3. Parsa FLR / FR-delen
    m_flr = re.search(
        r'\/?FLR\/PN(?:R|\b)?([A-Z0-9]+)\/FR(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})([^\/\r\n\x03\x17]+)(?:\/\s*([^\/\r\n\x03\x17]+))?(?:\/ID([^\r\n\x03\x17]+))?',
        normalized
    )

    if not m_flr and not is_rep:
        return None

    pnr = None
    flr_time_str = None
    ata_code, ata_name, ata_desc = "", "", ""
    phase_code, phase_name, phase_desc = "", "", ""
    comp1 = None
    comp2 = None
    aff_id = None
    fel_str = ""

    if m_flr:
        pnr = m_flr.group(1).strip()
        if pnr.startswith('R') and len(pnr) > 7:
            pnr = pnr[1:]

        yy, mm, dd = m_flr.group(2), m_flr.group(3), m_flr.group(4)
        date_str = f"20{yy}-{mm}-{dd}"

        hh, mn, ss = m_flr.group(5), m_flr.group(6), m_flr.group(7)
        flr_time_str = f"{hh}:{mn}:{ss}"

        c1, c2, c3 = m_flr.group(8), m_flr.group(9), m_flr.group(10)
        ata_code, ata_name, ata_desc = format_ata_chapter(c1, c2, c3)

        phase_code = m_flr.group(11)
        phase_name, _, phase_desc = format_airbus_flight_phase(phase_code)

        comp1 = m_flr.group(12).strip()
        comp2 = (m_flr.group(13) or '').strip()
        aff_id = (m_flr.group(14) or '').strip()

        if comp2.startswith('ID'):
            if not aff_id:
                aff_id = comp2[2:].strip()
            comp2 = ''

        if comp2:
            fel_str = f"{comp1} & {comp2}"
        else:
            fel_str = comp1
        if aff_id:
            fel_str += f" [Påverkar: {aff_id}]"

    # Bestäm om det är kombinerad REP-rapport eller fristående FLR-rapport
    if is_rep and (m_hdr or ac_type or orig_icao):
        orig_fmt = format_airport(orig_icao) if orig_icao else ""
        dest_fmt = format_airport(dest_icao) if dest_icao else ""
        route_str = f"Rutt: {orig_fmt} → {dest_fmt}" if (orig_fmt and dest_fmt) else ""

        header_items = [f"Flygplan: {ac_type}" if ac_type else None, route_str or None]
        header_text = " | ".join([h for h in header_items if h])

        ext_parts = []
        if alt_fmt and spd_kt:
            ext_parts.append(f"Höjd: {alt_fmt} ({spd_kt} kt)")
        elif alt_fmt:
            ext_parts.append(f"Höjd: {alt_fmt}")

        if fel_str:
            ext_parts.append(f"Fel: {fel_str}")
        elif comp1:
            ext_parts.append(f"Fel: {comp1}")

        if ata_desc:
            ext_parts.append(f"ATA: {ata_desc}")
        if phase_desc:
            ext_parts.append(f"Fas: {phase_desc}")

        ext_text = (" | " + " | ".join(ext_parts)) if ext_parts else ""
        summary = f"[Airbus FDIMU/Systemrapport #{rep_num}] {header_text}{ext_text}"

        if isinstance(metadata, dict):
            metadata['decoded_fields'] = {
                'report_type': f"Airbus FDIMU/Systemrapport #{rep_num}",
                'type_code': 'FLR',
                'is_fault_report': True,
                'severity': 'fault',
                'aircraft_type': ac_type,
                'report_code': f"REP{rep_num}",
                'origin': orig_icao,
                'destination': dest_icao,
                'route': f"{orig_icao} -> {dest_icao}" if (orig_icao and dest_icao) else None,
                'pnr': pnr,
                'ata': ata_code,
                'ata_name': ata_name,
                'ata_desc': ata_desc,
                'phase': phase_name,
                'phase_code': phase_code,
                'phase_desc': phase_desc,
                'component1': comp1,
                'component2': comp2,
                'affected_systems': aff_id,
                'fault_desc': comp1 or "Systemfel",
                'fault_text': fel_str or comp1 or "Systemfel",
                'summary': summary
            }

        return f"{summary}\nRådata: {text.strip()}"

    elif m_flr:
        # Fristående /FLR/PN utan REP
        summary_fel = fel_str or comp1
        summary = f"[Airbus CFDIU-Felrapport] Fel: {summary_fel} | ATA: {ata_desc} | Fas: {phase_desc} | Tid: {flr_time_str} UTC (PNR: {pnr})"

        if isinstance(metadata, dict):
            metadata['decoded_fields'] = {
                'report_type': 'Airbus CFDIU-Felrapport',
                'type_code': 'FLR',
                'is_fault_report': True,
                'severity': 'fault',
                'pnr': pnr,
                'time_utc': flr_time_str,
                'ata': ata_code,
                'ata_name': ata_name,
                'ata_desc': ata_desc,
                'phase': phase_name,
                'phase_code': phase_code,
                'phase_desc': phase_desc,
                'component1': comp1,
                'component2': comp2,
                'affected_systems': aff_id,
                'fault_desc': comp1 or "Systemfel",
                'fault_text': summary_fel,
                'summary': summary
            }

        return f"{summary}\nRådata: {text.strip()}"

    return None



def rule_libacars_structured(text: str, label: str = None, metadata: dict = None) -> str:
    """Regel som nyttjar färdigtolkad data från libacars i metadata-objektet."""
    if not isinstance(metadata, dict):
        return None
    res = format_libacars_data(acars_dict=metadata)
    return res if res else None


def rule_label_sa_media_advisory(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Label SA: Media Advisory (Länkstatus).
    Avkodar koder som 0E21955032HS till upprättad/förlorad länk och tillgängliga protokoll.
    """
    stripped = text.strip()
    lbl = (label or '').upper()
    if not (lbl == 'SA' or stripped.startswith('0E') or stripped.startswith('0L')):
        return None

    link_names = {
        'V': 'VHF ACARS',
        '2': 'VDL2',
        'H': 'HF',
        'S': 'Satcom',
        'G': 'GlobalStar',
        'I': 'Iridium'
    }

    # Kolla om metadata har strukturerad media_adv
    if isinstance(metadata, dict) and isinstance(metadata.get('media_adv'), dict):
        adv = metadata['media_adv']
        st = str(adv.get('state') or '').lower()
        stat_w = "Länk upprättad" if ("estab" in st or st == 'e') else ("Länk förlorad" if ("lost" in st or st == 'l') else "Länkstatus")
        c_code = str(adv.get('curr_link') or adv.get('current_link') or '').upper()
        c_link = link_names.get(c_code, c_code or 'VDL2')
        tm = adv.get('time') or ''
        tm_part = f" kl {tm} UTC" if tm else ""
        av_list = adv.get('avail_links') or []
        av_names = [link_names.get(str(x).upper(), str(x)) for x in av_list]
        av_part = f"   Tillgängliga: {', '.join(av_names)}" if av_names else ""
        return f"{stat_w} på {c_link}{tm_part}{av_part}".strip()

    m = re.search(r'0([EL])([V2HSGI])(\d{2})(\d{2})(\d{2})([V2HSGI]*)', stripped)
    if m:
        stat_w = "Länk upprättad" if m.group(1).upper() == 'E' else "Länk förlorad"
        curr_link = link_names.get(m.group(2).upper(), m.group(2).upper())
        hh, mm, ss = m.group(3), m.group(4), m.group(5)
        avail_raw = m.group(6).upper()
        avail_names = [link_names.get(c, c) for c in avail_raw]
        avail_part = f"   Tillgängliga: {', '.join(avail_names)}" if avail_names else ""
        return f"{stat_w} på {curr_link} kl {hh}:{mm}:{ss} UTC{avail_part} ({stripped})"

    if lbl == 'SA' and stripped:
        return f"Länkstatus (Media Advisory)\nRådata: {stripped}"
    return None


def rule_label_b6_cpdlc(text: str, label: str = None, metadata: dict = None) -> str:
    """Label B6 / PDC / Clearance / CPDLC anrop."""
    stripped = text.strip()
    lbl = (label or '').upper()
    if not (lbl in ('B6', 'A6', 'BA', 'AA') or stripped.startswith('/')):
        return None

    # Begär starttillstånd (/ESSA.DC1/...)
    m_dc = re.search(r'/([A-Z]{4})\.(DC1|OC1|TI2)/?', stripped, re.IGNORECASE)
    if m_dc:
        icao = m_dc.group(1).upper()
        act = m_dc.group(2).upper()
        ap_disp = format_airport(icao)
        if act == 'DC1':
            return f"Begär starttillstånd (Departure Clearance) för {ap_disp}\nRådata: {stripped}"
        elif act == 'OC1':
            return f"Begär Oceanic Clearance för {ap_disp}\nRådata: {stripped}"
        elif act == 'TI2':
            m_ad = re.search(r'/([A-Z]{4})\.TI2/(?:\d{1,4}\1)?([AD])', stripped, re.IGNORECASE)
            atis_type = (m_ad.group(2).upper()) if m_ad else ''
            if atis_type == 'A':
                if isinstance(metadata, dict):
                    metadata['dst_airport'] = icao
                desc = f"Begär landningsväder (Arrival ATIS) för {ap_disp}"
            elif atis_type == 'D':
                desc = f"Begär avgångsväder (Departure ATIS) för {ap_disp}"
            else:
                desc = f"Begär flygplatsväder (ATIS) för {ap_disp}"
            return f"{desc}\nRådata: {stripped}"

    # Fritext CPDLC med inledande snedstreck
    if stripped.startswith('/') and re.search(r'/(?:CLIMB|DESCEND|MAINTAIN|PROCEED|CONTACT|SQUAWK|DIRECT)', stripped, re.IGNORECASE):
        clean_msg = stripped[1:].strip()
        return f"Flygledningsmeddelande (CPDLC): {clean_msg}"

    if lbl in ('B6', 'A6') and stripped:
        return f"Begäran om färdtillstånd (PDC/DCL)\nRådata: {stripped}"

    return None


def rule_label_5u_weather_request(text: str, label: str = None, metadata: dict = None) -> str:
    """Label 5U, 57, WX: Väderbegäran / METAR."""
    stripped = text.strip()
    lbl = (label or '').upper()
    if lbl not in ('5U', '57', 'WX', '30', '5D', 'B9', 'A9') and not stripped.startswith('/'):
        return None

    # ATIS anrop
    m_atis = re.search(r'/([A-Z]{4})\.TI2/?', stripped, re.IGNORECASE)
    if m_atis:
        icao = m_atis.group(1).upper()
        ap_disp = format_airport(icao)
        m_ad = re.search(r'/([A-Z]{4})\.TI2/(?:\d{1,4}\1)?([AD])', stripped, re.IGNORECASE)
        atis_type = (m_ad.group(2).upper()) if m_ad else ''
        if atis_type == 'A':
            if isinstance(metadata, dict):
                metadata['dst_airport'] = icao
            desc = f"Begär landningsväder (Arrival ATIS) för {ap_disp}"
        elif atis_type == 'D':
            desc = f"Begär avgångsväder (Departure ATIS) för {ap_disp}"
        else:
            desc = f"Begär flygplatsväder (ATIS) för {ap_disp}"
        return f"{desc}\nRådata: {stripped}"

    # ICAO flygplats sökning i väderbegäran
    m_icao = re.search(r'\b([A-Z]{4})\b', stripped)
    if m_icao:
        icao = m_icao.group(1).upper()
        ap_disp = format_airport(icao)
        if lbl == 'B9':
            return f"Begär flygplatsväder (ATIS) för {ap_disp}\nRådata: {stripped}"
        elif lbl == 'A9':
            return f"Flygplatsväder (ATIS) för {ap_disp}\n{stripped}"
        elif lbl in ('5U', '57', 'WX'):
            return f"Begäran om flygplatsväder (METAR) för {ap_disp}\nRådata: {stripped}"

    return None


def rule_mdwxr_weather_and_dispatch(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Avkodar militära och operativa väder- och driftmeddelanden (#MDWXR / #WXR).
    Exempel: . - #MDWXR/ID00172A,RCH241,JMZN2922C285/MR1,44/MTLTAG,0757,TAF LTAG 0757Z VRB02KT CAVOK T21C A3015 REQUEST PIREP AS MISSON PERMITSFC54
    """
    if not text:
        return None
    stripped = text.strip()
    if '#MDWXR' not in stripped and '#WXR' not in stripped and '/MDWXR' not in stripped:
        return None

    m = re.search(
        r'#(?:MD)?WXR/ID(?P<msg_id>[A-Z0-9]+),(?P<callsign>[A-Z0-9]+)(?:,(?P<plan_id>[A-Z0-9]+))?(?:/MR[^/,]+,\d+)?(?:/MT(?P<target_ap>[A-Z]{4})(?:,(?P<target_time>\d{4}))?)?,?(?P<payload>.*)',
        stripped,
        re.IGNORECASE
    )
    if not m:
        return None

    msg_id = m.group('msg_id').upper()
    callsign = m.group('callsign').upper()
    flight_plan = (m.group('plan_id') or '').upper()
    target_ap = (m.group('target_ap') or '').upper()
    target_time = m.group('target_time') or ''
    payload = (m.group('payload') or '').strip()
    payload_clean = re.sub(r'[A-F0-9]{4}$', '', payload).strip()

    airline = lookup_airline(callsign) if callsign else ''
    ap_name = format_airport(target_ap) if target_ap else ''

    wx_type = 'Flygplatsväder (TAF)' if 'TAF' in payload_clean.upper() else ('Väderrapport (METAR)' if 'METAR' in payload_clean.upper() else 'Väderrapport')

    lines = [f"{wx_type} & Driftmeddelande"]
    header_parts = []
    if target_ap:
        header_parts.append(f"Flygplats: {ap_name or target_ap}")
    if target_time and len(target_time) == 4:
        header_parts.append(f"Tid: {target_time[:2]}:{target_time[2:]} UTC")
    if header_parts:
        lines.append("   ".join(header_parts))

    ac_parts = []
    if callsign:
        ac_parts.append(f"Flight: {callsign}" + (f" ({airline})" if airline else ""))
    if flight_plan:
        ac_parts.append(f"Färdplan: {flight_plan}")
    if ac_parts:
        lines.append("   ".join(ac_parts))

    m_wx = re.search(r'((?:TAF|METAR)?\s*[A-Z]{4}\s+\d{4}Z?\s+[^\n]+?)(?:\s+(REQUEST\s+PIREP[^\n]*|\bPIREP\b[^\n]*))?$', payload_clean, re.IGNORECASE)
    wx_raw_str = payload_clean
    instruction = ''
    if m_wx:
        wx_raw_str = (m_wx.group(1) or '').strip()
        instruction = (m_wx.group(2) or '').strip()

    if wx_raw_str:
        lines.append(f"Väder: {wx_raw_str}")
        details = []
        m_wind = re.search(r'\b(VRB|\d{3})(\d{2,3})(?:G(\d{2,3}))?KT\b', wx_raw_str)
        if m_wind:
            wdir, wspd, wgust = m_wind.groups()
            gust_str = f" byar {wgust} kt" if wgust else ""
            if wdir == 'VRB':
                details.append(f"Vind: Varierande {int(wspd)} kt{gust_str}")
            else:
                details.append(f"Vind: {wdir}° / {int(wspd)} kt{gust_str}")

        if 'CAVOK' in wx_raw_str:
            details.append("Sikt: CAVOK (God sikt, molnfritt)")

        m_temp = re.search(r'\bT(-?\d+)C\b', wx_raw_str)
        if m_temp:
            details.append(f"Temperatur: {m_temp.group(1)} C")

        m_alt = re.search(r'\bA(\d{4})\b', wx_raw_str)
        if m_alt:
            a_val = m_alt.group(1)
            inhg = f"{a_val[:2]}.{a_val[2:]}"
            try:
                hpa = round(float(inhg) * 33.8639)
                details.append(f"Lufttryck: {hpa} hPa ({inhg} inHg)")
            except Exception:
                pass
        else:
            m_qnh = re.search(r'\bQ(\d{4})\b', wx_raw_str)
            if m_qnh:
                details.append(f"Lufttryck: {m_qnh.group(1)} hPa")

        if details:
            lines.append("  - " + "   ".join(details))

    if instruction:
        instr_se = instruction
        if 'REQUEST PIREP' in instruction.upper():
            if 'MISSON PERMITS' in instruction.upper() or 'MISSION PERMITS' in instruction.upper():
                instr_se = "Begär pilotrapport (PIREP) så snart uppdraget tillåter"
            else:
                instr_se = "Begär pilotrapport (PIREP)"
        lines.append(f"Instruktion: {instr_se}")

    if isinstance(metadata, dict):
        if callsign and not metadata.get('flight'):
            metadata['flight'] = callsign
        if airline and not metadata.get('airline'):
            metadata['airline'] = airline
        if target_ap and not metadata.get('dst_airport'):
            metadata['dst_airport'] = target_ap
        if target_time and len(target_time) == 4 and not metadata.get('time'):
            metadata['time'] = f"{target_time[:2]}:{target_time[2:]} UTC"

    return "\n".join(lines)


def rule_acars_short_requests_and_sync(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Tolkar korta standardförfrågningar och synkroniseringar (PACEPOSREQ, REQPOS, Ground UTC sync etc.).
    """
    if not text:
        return None
    stripped = text.strip()
    lbl = (label or '').strip().upper()

    # 1. PACEPOSREQ / AOC Position Request (Label 2F m.fl.)
    if stripped == 'PACEPOSREQ' or 'PACEPOSREQ' in stripped:
        return "Begäran om positionsrapport (AOC Position Request)"

    # 2. REQPOS / POSREQ (Label 15, POS, H1 m.fl.)
    if stripped in ('REQPOS', 'POSREQ', 'REQ POS', 'POS REQ') or stripped.startswith('REQPOS'):
        return "Begäran om positionsrapport (REQPOS)"

    # 3. Label 52: Ground UTC Request / Time Synchronisation (t.ex. 2610202061500)
    if lbl == '52' or (len(stripped) in (12, 13, 14) and stripped.isdigit()):
        if len(stripped) == 13:
            # Format: YY MM DD W HH MM SS (W = veckodag 1-7)
            yy, mm, dd, dow, hh, mi, ss = stripped[0:2], stripped[2:4], stripped[4:6], stripped[6], stripped[7:9], stripped[9:11], stripped[11:13]
            days = {'1': 'Mån', '2': 'Tis', '3': 'Ons', '4': 'Tor', '5': 'Fre', '6': 'Lör', '7': 'Sön'}
            d_name = days.get(dow, '')
            day_str = f" ({d_name})" if d_name else ""
            if isinstance(metadata, dict) and not metadata.get('time'):
                metadata['time'] = f"{hh}:{mi}:{ss} UTC"
            return f"Tidssynkronisering (UTC): 20{yy}-{mm}-{dd}{day_str} kl {hh}:{mi}:{ss} UTC"
        elif len(stripped) == 12:
            # Format: YY MM DD HH MM SS
            yy, mm, dd, hh, mi, ss = stripped[0:2], stripped[2:4], stripped[4:6], stripped[6:8], stripped[8:10], stripped[10:12]
            if isinstance(metadata, dict) and not metadata.get('time'):
                metadata['time'] = f"{hh}:{mi}:{ss} UTC"
            return f"Tidssynkronisering (UTC): 20{yy}-{mm}-{dd} kl {hh}:{mi}:{ss} UTC"
        elif len(stripped) == 14:
            # Format: YYYY MM DD HH MM SS
            yyyy, mm, dd, hh, mi, ss = stripped[0:4], stripped[4:6], stripped[6:8], stripped[8:10], stripped[10:12], stripped[12:14]
            if isinstance(metadata, dict) and not metadata.get('time'):
                metadata['time'] = f"{hh}:{mi}:{ss} UTC"
            return f"Tidssynkronisering (UTC): {yyyy}-{mm}-{dd} kl {hh}:{mi}:{ss} UTC"

    return None


def rule_label_q0_link_test(text: str, label: str = None, metadata: dict = None) -> str:
    """Label Q0: Länktest (Link Test Ping)."""
    stripped = text.strip()
    lbl = (label or '').upper()
    if lbl == 'Q0' or stripped == 'PING':
        return "ACARS Länktest (Link Test Ping)"
    return None


def rule_label_h1_fpn_flight_plan(text: str, label: str = None, metadata: dict = None) -> str:
    """Label H1: Färdplan (FPN, ICAO FPL, INI)."""
    stripped = text.strip()
    
    # 1. ICAO FPL block
    if '(FPL-' in stripped:
        m_fpl = re.search(r'\(FPL-([A-Z0-9]+)-', stripped)
        if m_fpl:
            callsign = m_fpl.group(1)
            airports = re.findall(r'-([A-Z]{4})\d{4}', stripped)
            if len(airports) >= 2:
                if isinstance(metadata, dict):
                    metadata['dst_airport'] = airports[1].upper()
                return f"Färdplan (FPL): {callsign}   Rutt: {format_airport(airports[0])} → {format_airport(airports[1])}"
            elif len(airports) == 1:
                return f"Färdplan (FPL): {callsign}   Flygplats: {format_airport(airports[0])}"
            return f"Färdplan (FPL): {callsign}"

    # 2. FPN rutt (FPN/RI...)
    if stripped.startswith('FPN') or stripped.startswith('RI/'):
        m_fpn = re.search(r'(?:FPN/)?(?:RI/)?([A-Z]{4})/([A-Z]{4})(?:/FL(\d+))?', stripped, re.IGNORECASE)
        if m_fpn:
            orig = m_fpn.group(1).upper()
            dest = m_fpn.group(2).upper()
            if isinstance(metadata, dict):
                metadata['dst_airport'] = dest
            fl = m_fpn.group(3)
            fl_str = f"   Höjd: FL{fl}" if fl else ""
            return f"Färdplan (FPN): {format_airport(orig)} → {format_airport(dest)}{fl_str}"

    # 3. INI flight initialization
    if stripped.startswith('INI') or '/INI/' in stripped:
        m_ini = re.search(r'INI[/ ]([A-Z]{4})[/ ]([A-Z]{4})(?:[/ ](\d{4}))?', stripped, re.IGNORECASE)
        if m_ini:
            orig = m_ini.group(1).upper()
            dest = m_ini.group(2).upper()
            if isinstance(metadata, dict):
                metadata['dst_airport'] = dest
            tm = m_ini.group(3)
            tm_str = f"   Tid: {tm[:2]}:{tm[2:]} UTC" if tm else ""
            return f"Färdförberedelse (INI): {format_airport(orig)} → {format_airport(dest)}{tm_str}"

    return None



def format_waypoint_or_coord(wp_raw: str) -> str:
    """
    Om wp_raw är en rå koordinat (t.ex. N59101E020416 eller 58396E019081),
    konvertera den till decimalgrader ('59.1683, 20.6933').
    Annars returnera fix/waypoint-namnet oförändrat (t.ex. 'MC624', 'HAPIS').
    """
    if not wp_raw:
        return ""
    clean = wp_raw.strip().replace(' ', '')
    # Mönster 1: N59101E020416 eller S12345W012345
    m = re.match(r'^([NS])(\d{2})(\d{2})(\d?)([EW])(\d{3})(\d{2})(\d?)$', clean, re.IGNORECASE)
    if not m:
        # Mönster 2: 58396E019081 (saknar inledande N/S)
        m = re.match(r'^([NS]?)(\d{2})(\d{2})(\d?)([EW])(\d{3})(\d{2})(\d?)$', clean, re.IGNORECASE)
    if m:
        try:
            lat_ns = (m.group(1) or 'N').upper()
            lat_d = int(m.group(2))
            lat_m_int = int(m.group(3))
            lat_m_dec = int(m.group(4)) if m.group(4) else 0
            lat_m = lat_m_int + (lat_m_dec / 10.0 if m.group(4) else 0.0)
            lat = (lat_d + lat_m / 60.0) * (-1 if lat_ns == 'S' else 1)

            lon_ew = m.group(5).upper()
            lon_d = int(m.group(6))
            lon_m_int = int(m.group(7))
            lon_m_dec = int(m.group(8)) if m.group(8) else 0
            lon_m = lon_m_int + (lon_m_dec / 10.0 if m.group(8) else 0.0)
            lon = (lon_d + lon_m / 60.0) * (-1 if lon_ew == 'W' else 1)

            return f"{lat:.4f}, {lon:.4f}"
        except Exception:
            pass
    return wp_raw.strip()


def rule_label_h1_posn_fms(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Label H1 POSN: FMS / Färddator-rapport med rutt, waypoint och väder.
    Exempel: POSN58396E019081,N59101E020416,113729,360,N59419E022134,115509,N60027E023477,M54,31445,10132A6
    """
    stripped = text.strip()
    pos_suffix = ""
    if " | " in stripped:
        p = stripped.split(" | ", 1)
        base_text = p[0].strip()
        pos_suffix = p[1].strip()
    elif "\n" in stripped:
        p = stripped.split("\n", 1)
        base_text = p[0].strip()
        pos_suffix = p[1].strip()
    else:
        base_text = stripped

    if not (base_text.startswith("POSN") or base_text.startswith("POS") or base_text.startswith("*POS")):
        return None

    if base_text.startswith("POS -") or ('LAT ' in base_text and 'LON ' in base_text):
        return None

    tokens = [t.strip() for t in base_text.split(',')]
    if len(tokens) < 4:
        return None

    next_wp = tokens[1] if len(tokens) > 1 and tokens[1] else None
    next_time = None
    if len(tokens) > 2 and re.match(r'^\d{6}$', tokens[2]):
        hh, mm, ss = tokens[2][:2], tokens[2][2:4], tokens[2][4:6]
        next_time = f"{hh}:{mm}:{ss} UTC"

    fl_str = None
    alt_ft_val = None
    if len(tokens) > 3 and tokens[3]:
        raw_fl = tokens[3].upper()
        if raw_fl.startswith('FL'):
            fl_str = raw_fl
            try:
                alt_ft_val = int(raw_fl[2:]) * 100
            except Exception:
                pass
        elif re.match(r'^\d{2,3}$', raw_fl):
            fl_str = f"FL{raw_fl}"
            try:
                alt_ft_val = int(raw_fl) * 100
            except Exception:
                pass

    temp_str = None
    temp_idx = -1
    for i, tok in enumerate(tokens[4:], start=4):
        m_temp = re.match(r'^([MP])(\d{2})$', tok)
        if m_temp:
            sign = '-' if m_temp.group(1) == 'M' else '+'
            temp_val = int(m_temp.group(2))
            temp_str = f"{sign}{temp_val}°C"
            temp_idx = i
            break

    wind_str = None
    candidates = tokens[temp_idx + 1:] if temp_idx != -1 else tokens[4:]
    for tok in candidates:
        m_wind = re.match(r'^(\d{3})(\d{2,3})$', tok)
        if m_wind:
            wdir = int(m_wind.group(1))
            wspd = int(m_wind.group(2))
            if 0 <= wdir <= 360 and wspd < 300:
                wind_str = f"{wdir}° / {wspd} kt"
                break

    lines = []

    # Rad 1: [Typ av rapport] + Rutt / Flygplan (om känt)
    row1 = ["[FMS Färddator-rapport]"]
    if isinstance(metadata, dict):
        if metadata.get('route'):
            row1.append(f"Rutt: {metadata['route']}")
        elif metadata.get('flight'):
            row1.append(f"Flight: {metadata['flight']}")
    lines.append(" | ".join(row1))

    # Rad 2: Position: ... / Nästa brytpunkt: ... / ETA: ...
    row2 = []
    pos_val = None
    if pos_suffix:
        p_clean = re.sub(r'\b(?:Lat|Lon):\s*', '', pos_suffix).strip()
        pos_val = p_clean
    elif len(tokens) > 0:
        c_raw = re.sub(r'^\*?POSN?', '', tokens[0])
        parsed_c = format_waypoint_or_coord(c_raw)
        if parsed_c != c_raw:
            pos_val = parsed_c
    if pos_val:
        row2.append(f"Position: {pos_val}")

    if next_wp:
        wp_disp = format_waypoint_or_coord(next_wp)
        if next_time:
            row2.append(f"Nästa brytpunkt: {wp_disp} (kl {next_time})")
        else:
            row2.append(f"Nästa brytpunkt: {wp_disp}")
    if row2:
        lines.append(" | ".join(row2))

    # Rad 3: Höjd: ... | Fart: ... | Temp: ... | Vind: ... | Bränsle: ...
    row3 = []
    if fl_str:
        alt_fmt = f"{alt_ft_val:,} ft".replace(',', ' ') if alt_ft_val else ""
        row3.append(f"Höjd: {fl_str} ({alt_fmt})" if alt_fmt else f"Höjd: {fl_str}")
    if temp_str:
        row3.append(f"Temp: {temp_str}")
    if wind_str:
        row3.append(f"Vind: {wind_str}")
    if row3:
        lines.append(" | ".join(row3))

    summary = "\n".join(lines)
    return f"{summary}\nRådata: {stripped}"



def rule_label_h1_resreq_ack(text: str, label: str = None, metadata: dict = None) -> str:
    """Label H1 RESREQ/AK: Systemkvittens eller resursförfrågan."""
    stripped = text.strip()
    m = re.match(r'^RESREQ/(AK|NAK)(?:,([0-9A-Fa-f]+))?$', stripped, re.IGNORECASE)
    if m:
        status_code = m.group(1).upper()
        status_text = "bekräftad (ACK)" if status_code == "AK" else "nekad (NACK)"
        crc = m.group(2)
        if crc:
            return f"Systemkvittens: Resursförfrågan {status_text} [CRC: {crc}]"
        return f"Systemkvittens: Resursförfrågan {status_text}"

    if stripped.startswith('RESREQ'):
        return f"Systemförfrågan: Resursbegäran (RESREQ)\nRådata: {stripped}"

    return None


def rule_label_h1_mm_telemetry(text: str, label: str = None, metadata: dict = None) -> str:
    """Label H1 MM / DFB / CFB telemetrilogg."""
    clean = text.replace('<br>', '\n').replace('<CR><LF>', '\n').strip()
    lines = [l.strip() for l in clean.splitlines() if l.strip()]

    if lines and (lines[0].startswith('#DFB') or lines[0].startswith('#CFB') or lines[0].startswith('#M1B')):
        prefix_desc = "Flygdata (DFDAU)" if lines[0].startswith('#DFB') else ("Underhållsdata (CMC)" if lines[0].startswith('#CFB') else "Färddatatelemetri (FMS)")
        return f"{prefix_desc}: {lines[0]}"

    if len(lines) >= 2 and lines[0].startswith('MM'):
        header = lines[0]
        data_lines = lines[1:]
        count = len(data_lines)
        m_start = re.match(r'^(\d{2})(\d{2})(\d{2})', data_lines[0])
        m_end = re.match(r'^(\d{2})(\d{2})(\d{2})', data_lines[-1])
        punkt_text = "mätpunkt mottagen" if count == 1 else "mätpunkter mottagna"

        if m_start and m_end:
            t_start = f"{m_start.group(1)}:{m_start.group(2)}:{m_start.group(3)}"
            t_end = f"{m_end.group(1)}:{m_end.group(2)}:{m_end.group(3)}"
            time_span = f"({t_start} - {t_end} UTC)" if t_start != t_end else f"(kl {t_start} UTC)"
            return f"Telemetrilogg ({header}): {count} {punkt_text} {time_span}"
        elif m_start:
            t_start = f"{m_start.group(1)}:{m_start.group(2)}:{m_start.group(3)}"
            return f"Telemetrilogg ({header}): {count} {punkt_text} (kl {t_start} UTC)"
        return f"Telemetrilogg ({header}): {count} {punkt_text}"

    return None


def rule_fms_progress_destination(text: str, label: str = None, metadata: dict = None) -> str:
    """
    FMS Progress & Destination Report (PRG/DT..., INI/DT..., FTX/DT...).
    Exempel: PRG/DTEGLL,27L,65,083100,/PR1479,322,380,147,,0,20,,M56,50,,,P0,P0,36090,,1332,3372A88
    """
    stripped = text.strip()
    m = re.search(r'(?:PRG|INI|FTX)/DT([A-Z]{4}),([0-9]{2}[LRC]?),(\d+),(\d{6})', stripped)
    if not m:
        return None

    dst_code = m.group(1).upper()
    rwy = m.group(2).upper()
    fuel_raw = m.group(3)
    eta_raw = m.group(4)

    # Uppdatera även paketets dst_airport-metadata om metadata skickats in
    if isinstance(metadata, dict):
        metadata['dst_airport'] = dst_code

    dst_desc = format_airport(dst_code)

    rwy_part = f" Bana {rwy}" if rwy else ""
    eta_str = f"{eta_raw[:2]}:{eta_raw[2:4]} UTC"

    try:
        fuel_kg = int(fuel_raw) * 100
        fuel_str = f"{fuel_kg:,}".replace(',', ' ') + " kg"
    except (ValueError, TypeError):
        fuel_str = f"{fuel_raw}00 kg"

    alt_str = None
    temp_str = None

    # Matcha efterföljande /PR-sektion
    m_pr = re.search(r'/PR([^,\s\n\r]*),([^,\s\n\r]*),([1-4]\d{2})\b', stripped)
    if m_pr:
        alt_val = int(m_pr.group(3))
        alt_str = f"FL{alt_val}"

    m_temp = re.search(r'/PR[^\n\r]*\b([MP])(\d{2})\b', stripped)
    if m_temp:
        sign = "-" if m_temp.group(1).upper() == 'M' else "+"
        temp_str = f"{sign}{int(m_temp.group(2))}°C"

    parts = [f"Dest: {dst_desc}{rwy_part}", f"ETA: {eta_str}"]
    if alt_str:
        parts.append(f"Marschhöjd: {alt_str}")
    if temp_str:
        parts.append(f"Temp: {temp_str}")
    parts.append(f"Landningsbränsle: {fuel_str}")

    summary = f"[FMS Färdrapport] {' | '.join(parts)}"
    return f"{summary}\nRådata: {stripped}"


def rule_boeing_dfdau_engine_telemetry(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Boeing DFDAU / ACMS numerisk motortelemetri (Label H1, DF eller prefix #DFB).
    Exempel: 07336019 8991 9536 9158 9204 9700  533131 00 7858 8423 8589 8926...
    """
    stripped = text.strip()
    lbl = (label or '').strip().upper()
    has_dfb_prefix = stripped.startswith('#DFB')

    body = stripped[4:].strip() if has_dfb_prefix else stripped
    if not body:
        return None

    is_target_label = (lbl in ('H1', 'DF', 'H', 'D') or has_dfb_prefix)
    if not is_target_label:
        return None

    if stripped.startswith('MM'):
        return None

    # Minst 85% siffror, mellanslag, minustecken och hex-tecken (A-F)
    telemetry_chars = sum(1 for c in body if c.isdigit() or c.isspace() or c in 'ABCDEFabcdef-')
    if len(body) == 0 or telemetry_chars / len(body) < 0.85:
        return None

    tokens = body.split()
    def is_telemetry_token(t: str) -> bool:
        clean = t.lstrip('-')
        return bool(clean) and all(c.isdigit() or c in 'ABCDEFabcdef' for c in clean)

    telemetry_tokens = [t for t in tokens if is_telemetry_token(t)]
    if len(telemetry_tokens) < 10 and not (len(body) >= 30 and len(telemetry_tokens) >= 3):
        return None

    total_groups = len(telemetry_tokens)

    def scan_quads(min_lim):
        rpm_vals = []
        egt = None
        i = 0
        while i < len(tokens):
            if i + 4 <= len(tokens):
                quad = tokens[i:i+4]
                if all(len(t) == 4 and t.isdigit() and min_lim <= int(t) <= 10500 for t in quad):
                    vals = [int(t) for t in quad]
                    rpm_vals.extend(vals)
                    if i + 4 < len(tokens):
                        nxt = tokens[i+4]
                        if len(nxt) == 3 and nxt.isdigit() and 400 <= int(nxt) <= 850:
                            egt = int(nxt)
                    i += 4
                    continue
            i += 1
        return rpm_vals, egt

    # Skanna först efter cruise/climb varvtal (>= 8500) för att filtrera bort oljetryck/övriga parametrar
    rpm_values, egt_val = scan_quads(min_lim=8500)
    if not rpm_values:
        rpm_values, egt_val = scan_quads(min_lim=7500)

    parts = []
    if rpm_values:
        min_rpm = min(rpm_values) / 100.0
        max_rpm = max(rpm_values) / 100.0
        parts.append(f"N1/N2 Varvtal: {min_rpm:.1f}%–{max_rpm:.1f}%")

    if egt_val is not None:
        parts.append(f"EGT: {egt_val}°C")

    parts.append(f"({total_groups} mätvärden)")

    summary = f"[Boeing Motortelemetri / DFDAU] {' | '.join(parts)}"
    return f"{summary}\nRådata: {stripped}"


def rule_amdar_weather_report(text: str, label: str = None, metadata: dict = None) -> str:
    """AMDAR meteorologisk rapport (Label H2 m.fl.)."""
    stripped = text.strip()
    matches = re.findall(
        r'([NS])(\d{2})(\d{3})([EW])(\d{3})(\d{3})(\d{4})(\d{4})([MP])(\d{3})(\d{3})(\d{3})G',
        stripped
    )
    if not matches:
        return None

    last_pt = matches[-1]
    ns, lat_d, lat_m, ew, lon_d, lon_m, t_str, alt_s, t_sign, temp_s, w_dir, w_spd = last_pt
    try:
        lat_val = int(lat_d) + (int(lat_m) / 600.0)
        if ns.upper() == 'S':
            lat_val = -lat_val
        lon_val = int(lon_d) + (int(lon_m) / 600.0)
        if ew.upper() == 'W':
            lon_val = -lon_val

        alt_ft_val = int(alt_s) * 10
        alt_fmt = f"{alt_ft_val:,} ft".replace(',', ' ')
        temp_val = int(temp_s) / 10.0
        temp_sign_char = '-' if t_sign.upper() == 'M' else '+'
        wind_dir_val = int(w_dir)
        wind_spd_val = int(w_spd)
        time_str = f"{t_str[:2]}:{t_str[2:]} UTC"

        m_hdr = re.search(r'02E\d{2}([A-Z]{4})([A-Z]{4})', stripped)
        if m_hdr:
            orig_icao = m_hdr.group(1).upper()
            dest_icao = m_hdr.group(2).upper()
            orig_fmt = format_airport(orig_icao)
            dest_fmt = format_airport(dest_icao)
            route_part = f"Rutt: {orig_fmt} → {dest_fmt} | "
            if isinstance(metadata, dict):
                metadata['dst_airport'] = dest_icao
        else:
            route_part = ""

        return (
            f"[AMDAR Väderrapport] {route_part}"
            f"Senaste ({time_str}): Pos {lat_val:.4f}, {lon_val:.4f} | "
            f"Höjd: {alt_fmt} | Temp: {temp_sign_char}{temp_val:.1f}°C | "
            f"Vind: {wind_dir_val}° / {wind_spd_val} kt ({len(matches)} mätpunkter)"
        )
    except (ValueError, TypeError):
        return None


def rule_boeing_fms_weather_log(text: str, label: str = None, metadata: dict = None) -> str:
    """Boeing CSV FMS/väder-loggformat (Label H1 m.fl.)."""
    stripped = text.strip()
    lot_matches = re.findall(
        r'([NS])(\d{2})(\d{2}\.\d+),([EW])(\d{3})(\d{2}\.\d+),(\d{6}),(-?\d+),(-?\d+\.\d+),(\d{3}),(\d{3}),([A-Z]{2})',
        stripped
    )
    if not lot_matches:
        return None

    last_pt = lot_matches[-1]
    ns, lat_d, lat_m, ew, lon_d, lon_m, t_str, alt_s, temp_s, w_dir, w_spd, phase = last_pt
    try:
        lat_val = int(lat_d) + (float(lat_m) / 60.0)
        if ns.upper() == 'S':
            lat_val = -lat_val
        lon_val = int(lon_d) + (float(lon_m) / 60.0)
        if ew.upper() == 'W':
            lon_val = -lon_val

        alt_ft_val = int(alt_s)
        alt_fmt = f"{alt_ft_val:,} ft".replace(',', ' ')
        temp_val = float(temp_s)
        wind_dir_val = int(w_dir)
        wind_spd_val = int(w_spd)
        time_str = f"{t_str[2:4]}:{t_str[4:6]} UTC"

        m_hdr = re.search(
            r'[A-Z0-9_]+\s*,\s*([A-Z0-9]+)\s*,\s*(\d{6})\s*,\s*([A-Z0-9]+)\s*,\s*([A-Z]{4})\s*,\s*([A-Z]{4})',
            stripped
        )
        if m_hdr:
            ac_type = m_hdr.group(1).strip()
            callsign = m_hdr.group(3).strip()
            orig_icao = m_hdr.group(4).strip().upper()
            dest_icao = m_hdr.group(5).strip().upper()
            orig_fmt = format_airport(orig_icao)
            dest_fmt = format_airport(dest_icao)
            if isinstance(metadata, dict):
                metadata['dst_airport'] = dest_icao
            header_part = f"Flygplan: {ac_type} | Rutt: {orig_fmt} → {dest_fmt} | "
        else:
            header_part = ""

        return (
            f"[FMS Färd- & Väderlogg] {header_part}"
            f"Senaste ({time_str}): Pos {lat_val:.4f}, {lon_val:.4f} | "
            f"Höjd: {alt_fmt} | Temp: {temp_val:.1f}°C | "
            f"Vind: {wind_dir_val}° / {wind_spd_val} kt ({len(lot_matches)} mätpunkter)"
        )
    except (ValueError, TypeError):
        return None


# ATA-kapitel för flygplansunderhåll och cockpit-varningar (FDE / MSG)
ATA_CHAPTERS = {
    '21': 'Luftkonditionering/Tryck',
    '22': 'Autopilot',
    '23': 'Kommunikation',
    '24': 'Elkraft',
    '26': 'Brandskydd',
    '27': 'Färdstyrning (Flight Controls)',
    '28': 'Bränslesystem',
    '29': 'Hydraulik',
    '30': 'Avisning',
    '31': 'Instrument',
    '32': 'Landningsställ',
    '33': 'Belysning',
    '34': 'Navigation',
    '36': 'Pneumatik',
    '49': 'APU (Hjälpkraftverk)',
    '52': 'Dörrar'
}

def get_ata_description(code: str) -> str:
    """Returnerar formaterad ATA-kapitelbeskrivning (t.ex. 'ATA 34: Navigation')."""
    ch = str(code).strip()[:2]
    if ch in ATA_CHAPTERS:
        return f"ATA {ch}: {ATA_CHAPTERS[ch]}"
    try:
        n = int(ch)
        if 70 <= n <= 80:
            return f"ATA {ch}: Motorer/Framdrivning"
    except Exception:
        pass
    return f"ATA {ch}"

def rule_boeing_plf_fault_report(text: str, label: str = None, metadata: dict = None) -> str:
    """Boeing Central Maintenance / Felkodsrapport (PLF / FDE / MSG)."""
    stripped = text.strip()
    if not (stripped.startswith('PLF ') or '\nPLF ' in stripped or re.search(r'\bPLF\s+\d+\b', stripped)):
        return None

    # Extrahera rutt t.ex. EPWA/ESSA
    m_r = re.search(r'\b([A-Z]{4})/([A-Z]{4})\b', stripped)
    if m_r:
        orig = m_r.group(1).upper()
        dest = m_r.group(2).upper()
        orig_fmt = format_airport(orig)
        dest_fmt = format_airport(dest)
        route_str = f"Rutt: {orig_fmt} → {dest_fmt}"
        if isinstance(metadata, dict):
            metadata['dst_airport'] = dest
    else:
        route_str = ""

    # Hitta FDE (Cockpit-varningar / Flight Deck Effects)
    fde_codes = re.findall(r'\bFDE\s+(\d+)\b', stripped)
    unique_atas = []
    for code in fde_codes:
        ata_desc = get_ata_description(code)
        if ata_desc not in unique_atas:
            unique_atas.append(ata_desc)
    ata_info = f" ({', '.join(unique_atas)})" if unique_atas else ""
    fde_str = f"Cockpit-varningar (FDE): {len(fde_codes)} st{ata_info}"

    # Hitta MSG (Underhållskoder / Maintenance Messages)
    msg_codes = re.findall(r'\bMSG\s+(\d+)\b', stripped)
    msg_str = f"Underhållskoder (MSG): {len(msg_codes)} st"

    parts = [p for p in [route_str, fde_str, msg_str] if p]
    summary = f"[Underhålls-/Felrapport (PLF)] {' | '.join(parts)}"

    return f"{summary}\nRådata: {stripped}"


def rule_airbus_aids_fdimu_report(text: str, label: str = None, metadata: dict = None) -> str:
    """Airbus AIDS / FDIMU systemrapporter (/REP och /CC headers)."""
    if not text:
        return None
    if '/FLR/' in text or 'FLR/' in text or '/FR' in text:
        flr_res = rule_airbus_fault_report(text, label=label, metadata=metadata)
        if flr_res:
            return flr_res

    stripped = text.strip()
    m = re.search(
        r'^(A\d{3})[^/]*/REP(\d+)[^/]*/CC([A-Z0-9-]+),([A-Z]{3}\d{2}),(\d{6}),([A-Z]{4}),([A-Z]{4})',
        stripped
    )
    if not m:
        return None

    ac_type = m.group(1).strip()
    rep_num = m.group(2).strip()
    reg_code = m.group(3).strip()
    date_str = m.group(4).strip()
    t_raw = m.group(5).strip()
    orig_icao = m.group(6).strip().upper()
    dest_icao = m.group(7).strip().upper()

    time_str = f"{t_raw[0:2]}:{t_raw[2:4]}:{t_raw[4:6]} UTC" if len(t_raw) == 6 else t_raw
    orig_fmt = format_airport(orig_icao)
    dest_fmt = format_airport(dest_icao)
    route_str = f"Rutt: {orig_fmt} → {dest_fmt}"

    if isinstance(metadata, dict):
        metadata['dst_airport'] = dest_icao

    parts = [
        f"Flygplan: {ac_type}",
        route_str,
        f"Tid: {time_str}"
    ]

    m_ce = re.search(r'/CE\d{4},(\d{4,5}),(\d{3})', stripped)
    if m_ce:
        alt_val = int(m_ce.group(1))
        spd_val = int(m_ce.group(2))
        alt_fmt = f"{alt_val:,} ft".replace(',', ' ')
        parts.append(f"Höjd: {alt_fmt}")
        parts.append(f"Fart: {spd_val} kt")
        if isinstance(metadata, dict):
            metadata['alt_ft'] = alt_val
            metadata['alt'] = alt_val

    summary = f"[Airbus FDIMU/Systemrapport #{rep_num}] {' | '.join(parts)}"
    return f"{summary}\nRådata: {stripped}"


def rule_aoc_airline_designated(text: str, label: str = None, metadata: dict = None) -> str:
    """Flygbolagens interna AOC-labels (Label 1L, 1A-4Z)."""
    stripped = text.strip()
    lbl = (label or '').strip().upper()
    m_aoc_seq = re.match(r'^(\d{10,12})([A-Z0-9.,\-/]+)$', stripped)
    is_aoc_label = bool(lbl == '1L' or re.match(r'^[1-4][A-Z]$', lbl))
    if lbl == '1L' or (is_aoc_label and m_aoc_seq):
        seq_part = f", Seq: {m_aoc_seq.group(1)[:6]}" if m_aoc_seq else ""
        return f"[AOC Flygbolagsdata] Intern kodad drift-/telemetrirapport (Lufthansa Group{seq_part})\nRådata: {stripped}"
    return None


def rule_label_38_finnair_weather(text: str, label: str = None, metadata: dict = None) -> str:
    """Label 38: Finnair väder- och positionsrapport."""
    stripped = text.strip()
    if not (stripped.startswith('/') or (label and label.upper() == '38')):
        return None

    raw_tokens = [tok.strip() for tok in stripped.split('/') if tok.strip()]
    if len(raw_tokens) < 4:
        return None

    flight = None
    lat = None
    lon = None
    alt = None
    temp = None
    wind_dir = None
    wind_spd = None

    for i, tok in enumerate(raw_tokens):
        if i == 0 and re.match(r'^[A-Z0-9]{3,8}$', tok, re.IGNORECASE):
            flight = tok.upper()
            continue
        if i == 1 and re.match(r'^\d{6}$', tok):
            continue
        m_lat = re.match(r'^([NS])\s*(\d+\.?\d*)$', tok, re.IGNORECASE)
        if m_lat and not lat:
            lat = f"{m_lat.group(1).upper()} {m_lat.group(2)}"
            continue
        m_lon = re.match(r'^([EW])\s*(\d+\.?\d*)$', tok, re.IGNORECASE)
        if m_lon and not lon:
            lon = f"{m_lon.group(1).upper()} {m_lon.group(2)}"
            continue
        if re.match(r'^\d{4,5}$', tok) and not alt:
            val = int(tok)
            if 1000 <= val <= 65000:
                alt = str(val)
                continue
        m_temp = re.match(r'^([+-])\s*(\d{1,2})$', tok)
        if m_temp and not temp:
            temp = f"{m_temp.group(1)}{m_temp.group(2)}"
            continue
        m_wind = re.match(r'^(\d{3})(\d{2})$', tok)
        if m_wind and not wind_dir and i > 2:
            wdir = int(m_wind.group(1))
            wspd = int(m_wind.group(2))
            if 0 <= wdir <= 360 and wspd < 300:
                wind_dir = wdir
                wind_spd = wspd
                continue

    if not (lat or lon or flight):
        return None

    lines = []
    if flight:
        lines.append(f"Flight: {flight}")

    if lat and lon:
        lines.append(f"Position: {lat}, {lon}")
    elif lat or lon:
        lines.append(f"Position: {lat or lon}")

    w_items = []
    if alt:
        w_items.append(f"Höjd: {alt} ft")
    if temp:
        w_items.append(f"Temp: {temp}°C")
    if wind_dir is not None and wind_spd is not None:
        w_items.append(f"Vind: {wind_dir}° / {wind_spd} kt")
    if w_items:
        lines.append(" | ".join(w_items))

    summary = "\n".join(lines)
    stripped = text.strip()
    return f"{summary}\nRådata: {stripped}"


def rule_label_83_csv_position(text: str, label: str = None, metadata: dict = None) -> str:
    """Label 83: 9-fälts CSV positionsrapport (Ethiopian Airlines, ANA m.fl.)."""
    stripped = text.strip()
    if ',' not in stripped:
        return None

    tokens = [t.strip() for t in stripped.split(',')]
    if len(tokens) < 9:
        return None

    dep = tokens[0].upper()
    dest = tokens[1].upper()
    time_raw = tokens[2]
    lat_str = tokens[3]
    lon_str = tokens[4]
    alt_str = tokens[5]
    spd_str = tokens[6]
    hdg_str = tokens[7]
    fuel_str = tokens[8]

    if not (re.match(r'^[A-Z]{3,4}$', dep) and re.match(r'^[A-Z]{3,4}$', dest)):
        return None
    if not re.match(r'^\d{6}$', time_raw):
        return None

    hh = time_raw[2:4]
    mm = time_raw[4:6]
    time_fmt = f"{hh}:{mm} UTC"

    try:
        lat_val = float(lat_str)
        lon_val = float(lon_str)
        if not (-90 <= lat_val <= 90 and -180 <= lon_val <= 180):
            return None
        _alt_val = int(float(alt_str))
    except ValueError:
        return None

    if isinstance(metadata, dict):
        metadata['dst_airport'] = dest

    dep_fmt = format_airport(dep)
    dest_fmt = format_airport(dest)

    line1 = f"Rutt: {dep_fmt} → {dest_fmt}   Tid: {time_fmt}"
    line2 = f"Höjd: {alt_str} ft   Fart: {spd_str} kt   Kurs: {hdg_str} deg   Bränsle: {fuel_str}"
    line3 = f"Position: {lat_str}, {lon_str}"

    return f"{line1}\n{line2}\n{line3}"


def rule_label_83_eta_report(text: str, label: str = None, metadata: dict = None) -> str:
    """Label 83: ETA-rapport (SAS m.fl. eller 4DH3 ETAT2)."""
    stripped = text.strip()

    # Variant 1: V09CA032/ETA-30/2046/
    m = re.match(r'^([A-Z0-9]+)/(ETA(?:-?\d*))/(\d{2})(\d{2})/?$', stripped, re.IGNORECASE)
    if m:
        code = m.group(1).upper()
        status = m.group(2).upper()
        hh = m.group(3)
        mm = m.group(4)
        return f"Ankomststatus: Beräknad ankomst (ETA) kl {hh}:{mm} UTC (Status: {status}, Kod: {code})"

    # Variant 2: 4DH3 ETAT2 ...
    if stripped.startswith('4DH3 ETAT2'):
        tokens = stripped.split()
        if len(tokens) >= 7 and '/' in tokens[3]:
            orig, dest = tokens[3].split('/', 1)
            orig = orig.upper()
            dest = dest.upper()
            if isinstance(metadata, dict):
                metadata['dst_airport'] = dest
            eta_raw = tokens[6]
            eta_fmt = f"{eta_raw[:2]}:{eta_raw[2:4]} UTC" if len(eta_raw) >= 4 else eta_raw
            orig_fmt = format_airport(orig)
            dest_fmt = format_airport(dest)
            return f"Ankomstrapport: Rutt {orig_fmt} → {dest_fmt}   ETA: {eta_fmt}"

    return None



def rule_pos_key_value_report(text: str, label: str = None, metadata: dict = None) -> str:
    """
    POS-rapporter med nyckel/värdepar (t.ex. China Eastern Label 11).
    Exempel: POS - CAS 274,LAT N058.32,LON E016.90,ALT 37002,FOB 137088,UTC 115155,PD 41.15,WD -60,WS 50,TAT -56
    """
    stripped = text.strip()
    m_lat = re.search(r'\bLAT\s*([NS])(\d+\.?\d*)', stripped, re.IGNORECASE)
    m_lon = re.search(r'\bLON\s*([EW])(\d+\.?\d*)', stripped, re.IGNORECASE)
    if not (m_lat and m_lon):
        return None

    try:
        ns = m_lat.group(1).upper()
        lat_f = float(m_lat.group(2))
        lat = -lat_f if ns == 'S' else lat_f

        ew = m_lon.group(1).upper()
        lon_f = float(m_lon.group(2))
        lon = -lon_f if ew == 'W' else lon_f

        m_alt = re.search(r'\bALT\s*(-?\d+)', stripped, re.IGNORECASE)
        alt_val = int(m_alt.group(1)) if m_alt else None

        m_cas = re.search(r'\bCAS\s*(\d+)', stripped, re.IGNORECASE)
        cas_val = m_cas.group(1) if m_cas else None

        m_fob = re.search(r'\bFOB\s*(\d+)', stripped, re.IGNORECASE)
        fob_val = int(m_fob.group(1)) if m_fob else None

        m_utc = re.search(r'\bUTC\s*(\d{2})(\d{2})(\d{2})', stripped, re.IGNORECASE)
        time_str = f"{m_utc.group(1)}:{m_utc.group(2)}:{m_utc.group(3)} UTC" if m_utc else ""

        m_wd = re.search(r'\bWD\s*(-?\d+)', stripped, re.IGNORECASE)
        m_ws = re.search(r'\bWS\s*(\d+)', stripped, re.IGNORECASE)
        wind_dir = None
        if m_wd:
            wd_raw = int(m_wd.group(1))
            wind_dir = (360 + wd_raw) % 360
        ws_val = m_ws.group(1) if m_ws else None

        m_tat = re.search(r'\bTAT\s*(-?\d+)', stripped, re.IGNORECASE)
        tat_val = m_tat.group(1) if m_tat else None

        row1 = ["[Positionsrapport]", f"Position: {lat:.4f}, {lon:.4f}"]
        if time_str:
            row1.append(f"Tid: {time_str}")

        row2 = []
        if alt_val is not None:
            alt_fmt = f"{alt_val:,} ft".replace(',', ' ')
            row2.append(f"Höjd: {alt_fmt}")
        if cas_val:
            row2.append(f"Fart: {cas_val} kt")
        if tat_val:
            row2.append(f"Temp: {tat_val}°C")
        if wind_dir is not None and ws_val:
            row2.append(f"Vind: {wind_dir}° / {ws_val} kt")
        elif ws_val:
            row2.append(f"Vind: {ws_val} kt")
        if fob_val is not None:
            fob_fmt = f"{fob_val:,} lbs".replace(',', ' ')
            row2.append(f"Bränsle (FOB): {fob_fmt}")

        lines = [" | ".join(row1)]
        if row2:
            lines.append(" | ".join(row2))

        summary = "\n".join(lines)
        return f"{summary}\nRådata: {stripped}"
    except Exception:
        return None


def rule_icao_klm_pos_report(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Avkodar ICAO / KLM Positionsrapporter (POS-...):
    Exempel:
      (POS-KLM20H-5834N01553E/101429 F310
      RMK/FUEL 5.4 M0.80)
    """
    stripped = text.strip()
    m = re.search(
        r'\(POS-([A-Z0-9]+)-(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])/(\d{2})(\d{2})(\d{2})\s+F(\d{3})'
        r'(?:[\s\S]*?RMK/FUEL\s+(\d+(?:\.\d+)?))?'
        r'(?:[\s\S]*?M(0\.\d+))?',
        stripped,
        re.IGNORECASE
    )
    if not m:
        return None

    callsign = m.group(1).upper()
    lat_d = int(m.group(2))
    lat_m = int(m.group(3))
    lat_ns = m.group(4).upper()
    lat = lat_d + (lat_m / 60.0)
    if lat_ns == 'S':
        lat = -lat

    lon_d = int(m.group(5))
    lon_m = int(m.group(6))
    lon_ew = m.group(7).upper()
    lon = lon_d + (lon_m / 60.0)
    if lon_ew == 'W':
        lon = -lon

    hh, mm, ss = m.group(8), m.group(9), m.group(10)
    time_str = f"{hh}:{mm}:{ss} UTC"

    fl_num = int(m.group(11))
    alt_ft = fl_num * 100
    alt_fmt = f"{alt_ft:,} ft".replace(',', ' ')
    alt_str = f"FL{fl_num} ({alt_fmt})"

    fuel_raw = m.group(12)
    mach_raw = m.group(13)

    if isinstance(metadata, dict):
        metadata['lat'] = round(lat, 4)
        metadata['lon'] = round(lon, 4)
        metadata['alt'] = alt_ft
        metadata['alt_ft'] = alt_ft
        if not metadata.get('flight'):
            metadata['flight'] = callsign
        if callsign.startswith('KLM') and not metadata.get('airline'):
            metadata['airline'] = 'KLM Royal Dutch Airlines'

    parts = [f"Flight: {callsign}", f"Position: {lat:.4f}, {lon:.4f}", f"Höjd: {alt_str}", f"Tid: {time_str}"]
    if fuel_raw:
        fuel_ton = float(fuel_raw)
        fuel_kg = int(fuel_ton * 1000)
        fuel_kg_fmt = f"{fuel_kg:,} kg".replace(',', ' ')
        parts.append(f"Bränsle (FOB): {fuel_raw} ton ({fuel_kg_fmt})")
    if mach_raw:
        parts.append(f"Fart: Mach {mach_raw}")

    prefix = "[Positionsrapport / KLM]" if callsign.startswith('KLM') else "[Positionsrapport / ICAO]"
    summary = f"{prefix} " + " | ".join(parts)
    return f"{summary}\nRådata: {stripped}"


def rule_fms_telemetry_continuation_block(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Avkodar Airbus/Finnair/Lufthansa fortsättningsblock i Label: H1 (eller DF/H2)
    som börjar med komma (,), bindestreck (-,) eller innehåller /X\\d+, /V\\d+, /2[NS]\\d+.
    Exempel:
      ,0305/X72353,E0175,N577,057,321,0030,XXXX/
      ,182,006,000,038,0/2N0858,0913,53,092,006,000,035,0/2S3956...
      -,----/X30000,0802,0088,0005,N008,N003,N000/X40000...
    """
    lbl = (label or '').strip().upper()
    stripped = text.strip()
    if not stripped:
        return None

    # Kontrollera om det är ett fortsättningsblock
    is_cont_pattern = bool(
        stripped.startswith((',', '-,')) or
        re.search(r'/(?:X\d+|V\d+|2[NSTV]\d+|T\d+)', stripped) or
        (lbl in ('H1', 'H2', 'DF') and (stripped.startswith(',') or stripped.endswith('XXXX/')))
    )
    if not is_cont_pattern:
        return None

    # Sök efter koordinatpar som E0175,N577 i blocket
    # Mönster: ,([EW])(\d{3})(\d),([NS])(\d{2})(\d),
    coord_matches = list(re.finditer(r',([EW])(\d{3})(\d),([NS])(\d{2})(\d),', stripped))
    pos_str = ""
    if coord_matches:
        last_m = coord_matches[-1]
        ew = last_m.group(1).upper()
        lon_deg = int(last_m.group(2))
        lon_dec = int(last_m.group(3))
        lon = lon_deg + (lon_dec / 10.0)
        if ew == 'W':
            lon = -lon

        ns = last_m.group(4).upper()
        lat_deg = int(last_m.group(5))
        lat_dec = int(last_m.group(6))
        lat = lat_deg + (lat_dec / 10.0)
        if ns == 'S':
            lat = -lat

        if isinstance(metadata, dict):
            metadata['lat'] = round(lat, 4)
            metadata['lon'] = round(lon, 4)

        pos_str = f" (Position: {lat:.2f}, {lon:.2f})"

    summary = f"[FMS Telemetri / Delblock] Kompletterande färd- och sensordata{pos_str}"
    return f"{summary}\nRådata: {stripped}"


def rule_lsconf_loadsheet(text: str, label: str = None, metadata: dict = None) -> str:
    """
    LSCONF (Loadsheet Confirmation / Lastbesked)
    Matchar mönstret (?:[A-Z0-9]+/)?LSCONF/([A-Z0-9]+)/([A-Z]{4})/([A-Z]{4})/(\d+|--)
    Exempel: V09CA032/LSCONF/SK1423/ESSA/EKCH/11859/--/
    """
    stripped = text.strip()
    m = re.search(r'(?:[A-Z0-9]+/)?LSCONF/([A-Z0-9]+)/([A-Z]{4})/([A-Z]{4})/(\d+|--)', stripped, re.IGNORECASE)
    if not m:
        return None

    flight_no = m.group(1).upper()
    dep_icao = m.group(2).upper()
    arr_icao = m.group(3).upper()

    dep_fmt = format_airport(dep_icao)
    arr_fmt = format_airport(arr_icao)

    if isinstance(metadata, dict):
        metadata['dst_airport'] = arr_icao
        if not metadata.get('flight'):
            metadata['flight'] = flight_no

    summary = (
        f"[Lastbesked / Loadsheet (LSCONF)] Kvittens av last- och viktbesked för flight {flight_no} | "
        f"Rutt: {dep_fmt} → {arr_fmt}"
    )
    return f"{summary}\nRådata: {stripped}"


def rule_free_text_header(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Hanterar .FREE-headers (t.ex. /HAKDPHU.FREE\nETP WX COPIED THX från Hainan Airlines Label 80).
    Första raden matchar ^/[A-Z0-9]+\.FREE\s*$
    Tolkar efterföljande rad(er) som Pilotmeddelande: "..."
    """
    stripped = text.strip()
    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    if len(lines) < 2:
        return None

    first_line = lines[0]
    if not re.match(r'^/[A-Z0-9]+\.FREE\s*$', first_line, re.IGNORECASE):
        return None

    content_lines = lines[1:]
    joined_msg = " — ".join(content_lines)
    summary = f'Pilotmeddelande: "{joined_msg}"'
    return f"{summary}\nRådata: {stripped}"


def rule_ground_handling_fuel_assistance(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Marktjänst & Markoperationer: Ground Handling, Bränslebeställning (Fuel Uplift)
    och Special Assistance / PRM (t.ex. WCHC, WCHS, WCHR, BLND/DEAF).
    Vanligt hos flygbolag som Wizz Air, Ryanair, easyJet m.fl. under Label H1, 16, 80 etc.
    Döljer ALDRIG läsbar fritext bakom Rådata!
    """
    stripped = text.strip()
    gh_patterns = [
        r'\bDear\s+[A-Z0-9]{3,4}\s+GH\b',
        r'\bSpecial\s+Assistance\b',
        r'\bFUEL\s+UPLIFT\b',
        r'\b(?:BLOCK|TAXI|TRIP)\s+FUEL\s+QTY\b',
        r'\b(?:WCHC|WCHS|WCHR):\s*\d+',
        r'\bneed\s+the\s+below\s+Fuel\s+Qty\b',
        r'\bGround\s+Handling\b'
    ]
    if not any(re.search(p, stripped, re.IGNORECASE) for p in gh_patterns):
        return None

    # 1. Rutt: Sök efter giltigt ICAO-ruttpar och ignorera falska som BLND/DEAF
    route_pair = find_valid_route_pair(stripped)
    route_str = ""
    if route_pair:
        orig, dest = route_pair
        route_str = f"Rutt: {format_airport(orig)} → {format_airport(dest)}"
        if isinstance(metadata, dict):
            metadata['dst_airport'] = dest

    # 2. Flight och registrering
    m_flt = re.search(r'\b([A-Z0-9]{2,3}\d{1,4}[A-Z]?)\s*,\s*([A-Z]{4}[-/][A-Z]{4})', stripped)
    if m_flt:
        flt_code = m_flt.group(1).upper()
        if isinstance(metadata, dict) and not metadata.get('flight'):
            metadata['flight'] = flt_code

    m_reg = re.search(r'A/C:\s*([A-Z0-9-]+)', stripped, re.IGNORECASE)
    if m_reg and isinstance(metadata, dict) and not metadata.get('reg'):
        metadata['reg'] = m_reg.group(1).upper()

    # 3. ETA
    eta_str = ""
    m_eta = re.search(r'\bETA[:\s]*([01]\d|2[0-3])([0-5]\d)z?\b', stripped, re.IGNORECASE)
    if m_eta:
        eta_str = f"ETA: {m_eta.group(1)}:{m_eta.group(2)} UTC"

    summary_items = ["Marktjänst / PRM & Bränsle"]
    if route_str:
        summary_items.append(route_str)
    if eta_str:
        summary_items.append(eta_str)

    summary_header = " | ".join(summary_items)

    # 4. Separera teknisk inledningsrad och bevara den fullständiga läsbara brödtexten synlig i tabellen
    lines = stripped.splitlines()
    body_lines = []
    header_raw = []
    in_body = False

    for l in lines:
        l_s = l.strip()
        if not l_s:
            if in_body:
                body_lines.append("")
            continue
        # Känn igen starten på läsbart innehåll (flight/rutt eller Dear ...)
        if re.search(r'\b(?:Dear\s+[A-Z0-9]{3,4}\s+GH|[A-Z0-9]{2,4}\s*,\s*[A-Z]{4}[-/][A-Z]{4})\b', l_s, re.IGNORECASE):
            in_body = True
        if in_body:
            body_lines.append(l)
        else:
            header_raw.append(l)

    if not body_lines:
        body_lines = lines

    readable_body = "\n".join(body_lines).strip()
    raw_part = "\n".join(header_raw).strip()

    if raw_part:
        return f"{summary_header}\n\n{readable_body}\nRådata: {raw_part}"
    return f"{summary_header}\n\n{readable_body}"


def rule_operational_eta_fob_freetext(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Operativa meddelanden (Label 80, RA, 10–4Z m.fl.) med rutt, /ETA, /FOB och pilotfritext.
    Exempel:
      3401 ETA 4505/15 ESSA/EDDB .SE-RYC
      /ETA 0925/FOB 0428
      HI BER
      REQ FUEL 5.6T
    """
    stripped = text.strip()
    has_eta_fob = bool(re.search(r'/(?:ETA|FOB)\s*\d+', stripped) or re.search(r'\bFOB\s*\d+', stripped))
    route_pair = find_valid_route_pair(stripped)
    has_route = bool(route_pair)

    # Krav 1: Begränsa Pilotmeddelande: till ENDAST konversations-labels (eller .FREE / FTX/)
    PILOT_ALLOWED_LABELS = {"80", "81", "82", "83", "RA", "AA", "10", "12", "13", "15"}
    lbl_clean = (label or '').strip().upper()
    is_freetext_allowed = (lbl_clean in PILOT_ALLOWED_LABELS) or ('.FREE' in stripped.upper()) or ('FTX/' in stripped.upper())

    if not (has_eta_fob or (is_freetext_allowed and (has_route or 'ETA' in stripped or len(stripped.splitlines()) > 0))):
        return None

    # 1. Rutt (använd validerat par för att undvika falska positiva som BLND/DEAF)
    route_str = ""
    if route_pair:
        orig, dest = route_pair
        orig_fmt = format_airport(orig)
        dest_fmt = format_airport(dest)
        route_str = f"Rutt: {orig_fmt} → {dest_fmt}"
        if isinstance(metadata, dict):
            metadata['dst_airport'] = dest

    # 2. Giltig ETA (HHMM med 00-23 och 00-59)
    eta_str = ""
    m_eta = re.search(r'(?:/ETA\s*|\bETA\s*[:=]?\s*)([01]\d|2[0-3])([0-5]\d)\b', stripped)
    if m_eta:
        eta_str = f"ETA: {m_eta.group(1)}:{m_eta.group(2)} UTC"

    # 3. FOB (Bränsle ombord)
    fob_str = ""
    m_fob = re.search(r'(?:/FOB\s*|\bFOB\s*[:=]?\s*)(\d{3,5})\b', stripped)
    if m_fob:
        fob_raw = m_fob.group(1)
        val = int(fob_raw)
        if len(fob_raw) == 3:
            fob_kg = val * 100
        elif len(fob_raw) == 4:
            fob_kg = val * 10
        else:
            fob_kg = val
        fob_formatted = f"{fob_kg:,} kg".replace(',', ' ')
        fob_str = f"Bränsle (FOB): {fob_formatted}"

    # 4. Extrahera pilot-fritext med skärpta filterregler (endast på tillåtna labels eller .FREE / FTX/)
    freetext_lines = []
    if is_freetext_allowed:
        TECH_PREFIXES = (
            'V09', 'PLF ', 'FDE ', 'MSG ', '/ETA', '/FOB', 'PRG/', 'INI/', 'FTX/',
            'POS', 'REP', '02E', '#DFB', '#CFB', '#M1B'
        )
        lines = [l.strip() for l in stripped.splitlines() if l.strip()]
        for l in lines:
            if re.search(r'\b[A-Z]{4}[-/][A-Z]{4}\b', l) and (re.search(r'\bETA\b', l) or re.search(r'\.[A-Z0-9-]{3,}', l)):
                continue
            if l.startswith('/') or l.startswith('#') or l.startswith(';'):
                continue
            if re.match(r'^(?:OUT|OFF|ON|IN)\b', l, re.IGNORECASE):
                continue

            # Krav 1: Måste innehålla minst ett mellanslag mellan ord
            if ' ' not in l:
                continue

            # Krav 2: Inte fler än 1 snedstreck per 15 tecken, och ej strukturerad kommaseparerad telemetri
            slash_count = l.count('/')
            comma_count = l.count(',')
            if slash_count > 1 and (slash_count / len(l) > 1.0 / 15.0):
                continue
            if comma_count > 1 and (comma_count / len(l) > 1.0 / 15.0):
                continue
            if slash_count >= 3 or comma_count >= 3:
                continue

            # Krav 3: Får inte börja med kända tekniska prefix
            if any(l.upper().startswith(p.upper()) for p in TECH_PREFIXES):
                continue

            # Krav 4: Exkluderingsregler mot telemetri och nyckel/värdepar (POS, LAT, LON etc.)
            l_upper = l.upper()
            if l_upper.startswith('POS') or re.search(r'\b(?:LAT|LON|ALT|FOB|CAS|UTC|TAT)\s+[A-Z0-9\-]', l_upper):
                continue

            if comma_count >= 2 and re.search(r',\s*[A-Z0-9_\-]*\d+', l):
                continue

            digit_count = sum(1 for c in l if c.isdigit())
            if (digit_count / max(len(l), 1)) > 0.25:
                continue

            freetext_lines.append(l)

    pilot_msg = ""
    if freetext_lines:
        joined_free = " — ".join(freetext_lines)
        pilot_msg = f'Pilotmeddelande: "{joined_free}"'

    summary_items = [item for item in [route_str, eta_str, fob_str] if item]
    if not summary_items and not pilot_msg:
        return None

    summary_line = " | ".join(summary_items) if summary_items else "Operativ rapport"
    if pilot_msg:
        full_summary = f"{summary_line}\n{pilot_msg}"
    else:
        full_summary = summary_line

    return f"{full_summary}\nRådata: {stripped}"


def rule_label_80_oooi_report(text: str, label: str = None, metadata: dict = None) -> str:
    """Label 80-82 / OOOI: Avgångs- och ankomstrapport (OUT, OFF, ON, IN)."""
    stripped = text.strip()
    lbl = (label or '').upper()

    m_oooi = re.match(r'^(OUT|OFF|ON|IN)(?:[/ ]([A-Z]{4}))?(?:[/ ](\d{4,6}))?', stripped, re.IGNORECASE)
    if m_oooi:
        phase = m_oooi.group(1).upper()
        ap = m_oooi.group(2)
        tm = m_oooi.group(3)
        desc_map = {
            'OUT': 'Pushback från gate (OUT)',
            'OFF': 'Startat från bana (OFF)',
            'ON': 'Landat på bana (ON)',
            'IN': 'Parkering vid gate (IN)'
        }
        desc = desc_map.get(phase, phase)
        parts = [f"Flygstatus: {desc}"]
        if ap:
            parts.append(f"Flygplats: {ap.upper()}")
        if tm and len(tm) >= 4:
            parts.append(f"Tid: {tm[:2]}:{tm[2:4]} UTC")
        return "   ".join(parts)

    return None


def rule_miam_airbus_telemetry(text: str, label: str = None, metadata: dict = None) -> str:
    """MIAM Airbus telemetri (PAALT, PALAT, PALONG, PAFMSAWID etc.)."""
    stripped = text.strip()
    if 'PAALT,' not in stripped and 'PALAT,' not in stripped:
        return None

    kv = {}
    for item in re.split(r'[;:]', stripped):
        parts = item.split(',')
        if len(parts) >= 2:
            k = parts[0].strip().upper()
            v = parts[1].strip()
            kv[k] = v

    lines = []
    # Rad 1: [Typ av rapport]
    lines.append("[Airbus FDIMU Färdtelemetri]")

    # Rad 2: Position & Nästa brytpunkt
    row2 = []
    if 'PALAT' in kv and 'PALONG' in kv:
        try:
            lat = float(kv['PALAT'])
            lon = float(kv['PALONG'])
            row2.append(f"Position: {lat:.4f}, {lon:.4f}")
        except (ValueError, TypeError):
            pass
    if 'PAFMSAWID' in kv and kv['PAFMSAWID'].strip():
        wp_name = kv['PAFMSAWID'].strip()
        wp_fmt = format_waypoint_or_coord(wp_name)
        row2.append(f"Nästa brytpunkt: {wp_fmt}")
    if row2:
        lines.append(" | ".join(row2))

    # Rad 3: Höjd, Temp, Vind, Kurs, Mach, Bränsle
    row3 = []
    if 'PAALT' in kv:
        try:
            alt_ft = int(float(kv['PAALT']))
            fl = round(alt_ft / 100)
            alt_fmt = f"{alt_ft:,} ft".replace(',', ' ')
            row3.append(f"Höjd: FL{fl} ({alt_fmt})")
        except (ValueError, TypeError):
            pass

    if 'PASAT' in kv:
        try:
            sat = round(float(kv['PASAT']))
            row3.append(f"Temp: {sat}°C")
        except (ValueError, TypeError):
            pass

    if 'PAWS' in kv:
        try:
            ws = round(float(kv['PAWS']))
            row3.append(f"Vind: {ws} kt")
        except (ValueError, TypeError):
            pass

    if 'PATHDG' in kv:
        try:
            hdg = round(float(kv['PATHDG']))
            row3.append(f"Kurs: {hdg}°")
        except (ValueError, TypeError):
            pass
    if 'PAMN' in kv:
        try:
            mach = float(kv['PAMN'])
            row3.append(f"Mach: {mach:.2f}")
        except (ValueError, TypeError):
            pass
    if 'PAFOB' in kv:
        try:
            fob = int(float(kv['PAFOB']))
            row3.append(f"Bränsle: {fob:,} kg".replace(',', ' '))
        except (ValueError, TypeError):
            pass

    if row3:
        lines.append(" | ".join(row3))

    summary = "\n".join(lines)
    stripped = text.strip()
    return f"{summary}\nRådata: {stripped}"


def rule_label_10_through_22_pos(text: str, label: str = None, metadata: dict = None) -> str:
    """Label 10, 15, 16, 20, 21, 22: Positionsrapporter."""
    stripped = text.strip()
    lbl = (label or '').upper()

    # 1. Kompakt format Nddmm[m], Wdddmm[m] (t.ex. N66000, W020000 eller N66000 W020000)
    m_dm_comp = re.search(r'\b([NS])(\d{2})(\d{2,3})[,\s/]+([EW])(\d{3})(\d{2,3})\b', stripped, re.IGNORECASE)
    if m_dm_comp:
        try:
            ns, lat_deg, lat_min_raw, ew, lon_deg, lon_min_raw = m_dm_comp.groups()
            lat_min = int(lat_min_raw) / (10.0 if len(lat_min_raw) == 3 else 1.0)
            lon_min = int(lon_min_raw) / (10.0 if len(lon_min_raw) == 3 else 1.0)
            lat = int(lat_deg) + (lat_min / 60.0)
            lon = int(lon_deg) + (lon_min / 60.0)
            if ns.upper() == 'S':
                lat = -lat
            if ew.upper() == 'W':
                lon = -lon
            f_lat = round(lat, 4)
            f_lon = round(lon, 4)
            if isinstance(metadata, dict):
                metadata['lat'] = f_lat
                metadata['lon'] = f_lon

            alt_match = re.search(r'\b(?:FL|ALT)?\s*(\d{4,5})\b', stripped)
            alt_part = ""
            if alt_match:
                alt_val = int(alt_match.group(1))
                if isinstance(metadata, dict) and not metadata.get('alt_ft'):
                    metadata['alt_ft'] = alt_val
                fl = round(alt_val / 100)
                alt_part = f"   Höjd: FL{fl} ({alt_val} ft)"

            return f"Positionsrapport: Position: {f_lat:.4f}, {f_lon:.4f} ({ns.upper()} {lat_deg}°{lat_min:04.1f}', {ew.upper()} {lon_deg}°{lon_min:04.1f}'){alt_part}"
        except Exception:
            pass

    # 2. Exempel: 191331,37012,1946, 74,N 56.955 E 17.322
    m_pos = re.search(r'([NS]\s*\d+\.?\d*)\s*([EW]\s*\d+\.?\d*)', stripped, re.IGNORECASE)
    if m_pos and (lbl in ('10', '15', '16', '20', '21', '22', 'POS') or ',' in stripped):
        lat_txt = m_pos.group(1).strip()
        lon_txt = m_pos.group(2).strip()

        # Försök beräkna decimala koordinater
        m_dec = re.search(r'([NS])\s*(\d+\.?\d*)\s*([EW])\s*(\d+\.?\d*)', stripped, re.IGNORECASE)
        if m_dec and isinstance(metadata, dict):
            try:
                ns, l1, ew, l2 = m_dec.groups()
                lat_v = float(l1) * (-1 if ns.upper() == 'S' else 1)
                lon_v = float(l2) * (-1 if ew.upper() == 'W' else 1)
                metadata['lat'] = round(lat_v, 4)
                metadata['lon'] = round(lon_v, 4)
            except Exception:
                pass

        # Försök hitta altitud
        alt_match = re.search(r'\b(\d{4,5})\b', stripped)
        if alt_match:
            alt_val = int(alt_match.group(1))
            if isinstance(metadata, dict) and not metadata.get('alt_ft'):
                metadata['alt_ft'] = alt_val
            fl = round(alt_val / 100)
            alt_part = f"   Höjd: FL{fl} ({alt_val} ft)"
        else:
            alt_part = ""
        return f"Positionsrapport: {lat_txt}, {lon_txt}{alt_part}"

    return None


def rule_label_44_eta_pos(text: str, label: str = None, metadata: dict = None) -> str:
    """Label 44: ETA eller positionsmeddelande."""
    stripped = text.strip()
    lbl = (label or '').upper()
    if lbl != '44' and not stripped.startswith('ETA/'):
        return None

    m_eta = re.search(r'ETA[/ ]([A-Z]{4})[/ ](\d{2})(\d{2})', stripped, re.IGNORECASE)
    if m_eta:
        ap = m_eta.group(1).upper()
        hh = m_eta.group(2)
        mm = m_eta.group(3)
        return f"Beräknad ankomst (ETA): {ap} kl {hh}:{mm} UTC"

    return None


def rule_generic_fallback_telemetry(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Generell fallback: extraherar rutt, ETA, flygnivå eller koordinater om de finns
    och sammanfattar före råtexten.
    """
    stripped = text.strip()
    if any(k in stripped for k in ('Färddator-rutt', 'Positionsrapport', 'Rutt:', 'Länkstatus', 'Flygstatus', 'Flygledningsmeddelande', 'Ankomststatus', 'Telemetrilogg', 'Systemkvittens', 'Färdplan', 'Färdförberedelse')):
        return None

    extracted = []

    # 1. Rutt: ICAO/ICAO eller ICAO -> ICAO (t.ex. ESSA/ENGM eller ARN-OSL)
    m_route = re.search(r'\b([A-Z]{4})[/->]([A-Z]{4})\b', stripped)
    if m_route:
        extracted.append(f"Rutt: {format_airport(m_route.group(1))} → {format_airport(m_route.group(2))}")
    else:
        m_route3 = re.search(r'\b([A-Z]{3})[/->]([A-Z]{3})\b', stripped)
        if m_route3:
            extracted.append(f"Rutt: {format_airport(m_route3.group(1))} → {format_airport(m_route3.group(2))}")

    # 2. ETA: Giltig tid (timmar 00-23 och minuter 00-59, undvik flightnummer som ETA 4505)
    m_eta = re.search(r'(?:/ETA\s*|\bETA\s*[:=]?\s*)([01]\d|2[0-3])([0-5]\d)\b', stripped, re.IGNORECASE)
    if m_eta:
        extracted.append(f"ETA: {m_eta.group(1)}:{m_eta.group(2)} UTC")

    # 2b. FOB (Bränsle ombord)
    m_fob = re.search(r'(?:/FOB\s*|\bFOB\s*[:=]?\s*)(\d{3,5})\b', stripped, re.IGNORECASE)
    if m_fob:
        fob_raw = m_fob.group(1)
        val = int(fob_raw)
        fob_kg = val * 100 if len(fob_raw) == 3 else (val * 10 if len(fob_raw) == 4 else val)
        extracted.append(f"Bränsle (FOB): {fob_kg:,} kg".replace(',', ' '))

    # 3. Höjd / Flygnivå: t.ex. FL360 eller FL 360
    m_fl = re.search(r'\bFL\s*(\d{2,3})\b', stripped, re.IGNORECASE)
    if m_fl:
        extracted.append(f"Höjd: FL{m_fl.group(1)}")

    # 4. Koordinater: t.ex. 58.54N 18.94E eller N58.54 E18.94 eller N5611.4, E01728.9
    # Om DDMM.M, konvertera till decimalgrader och välj sista punkten
    m_dm = re.findall(r'([NS])\s*([0-9]{2})([0-9]{2}\.[0-9]+)\s*[/,\s]?\s*([EW])\s*([0-9]{3})([0-9]{2}\.[0-9]+)', stripped, re.IGNORECASE)
    if m_dm:
        last_c = m_dm[-1]
        try:
            lat = (int(last_c[1]) + float(last_c[2]) / 60.0) * (-1 if last_c[0].upper() == 'S' else 1)
            lon = (int(last_c[4]) + float(last_c[5]) / 60.0) * (-1 if last_c[3].upper() == 'W' else 1)
            extracted.append(f"Position: {lat:.4f}, {lon:.4f}")
        except Exception:
            pass
    else:
        m_coord = re.findall(r'([NS]\s*\d+\.?\d*)\s*[,/ ]\s*([EW]\s*\d+\.?\d*)', stripped, re.IGNORECASE)
        if m_coord:
            last_c = m_coord[-1]
            extracted.append(f"Position: {last_c[0]}, {last_c[1]}")

    if extracted:
        summary = "   ".join(extracted)
        return f"{summary}\nRådata: {stripped}"

    return None


def rule_h1_h2_df_fallback(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Generell fallback för oidentifierad maskindata under Label: H1, H2, DF eller 5Z.
    Garanterar att rådata alltid döljs bakom Rådata:
    Exempel: *,82:8YYB3 )RE 13J/ )1,,Y
    """
    lbl = (label or '').strip().upper()
    if lbl not in ('H1', 'H2', 'DF', '5Z'):
        return None
    stripped = text.strip()
    if not stripped:
        return None
    if '\nRådata:' in stripped:
        return stripped

    return f"[FMS/Systemtelemetri] Kodat datapaket ({len(stripped)} tecken)\nRådata: {stripped}"


# Lista av regler som exekveras i prioritetsordning
PARSER_RULES = [
    rule_libacars_structured,
    rule_mdwxr_weather_and_dispatch,
    rule_acars_short_requests_and_sync,
    rule_fm_flight_report,
    rule_airbus_ecam_warning,
    rule_airbus_fault_report,
    rule_miam_airbus_telemetry,
    rule_label_sa_media_advisory,
    rule_label_b6_cpdlc,
    rule_label_5u_weather_request,
    rule_label_q0_link_test,
    rule_fms_progress_destination,
    rule_boeing_dfdau_engine_telemetry,
    rule_boeing_plf_fault_report,
    rule_airbus_aids_fdimu_report,
    rule_amdar_weather_report,
    rule_boeing_fms_weather_log,
    rule_aoc_airline_designated,
    rule_label_h1_fpn_flight_plan,
    rule_icao_klm_pos_report,
    rule_pos_key_value_report,
    rule_fms_telemetry_continuation_block,
    rule_label_h1_posn_fms,
    rule_label_h1_resreq_ack,
    rule_label_h1_mm_telemetry,
    rule_label_38_finnair_weather,
    rule_label_83_csv_position,
    rule_label_83_eta_report,
    rule_lsconf_loadsheet,
    rule_ground_handling_fuel_assistance,
    rule_free_text_header,
    rule_operational_eta_fob_freetext,
    rule_label_80_oooi_report,
    rule_label_10_through_22_pos,
    rule_label_44_eta_pos,
    rule_generic_fallback_telemetry,
]

def parse_human_acars(message: str, label: str = None, metadata: dict = None, strip_prefix: bool = False) -> str:
    """
    Huvudfunktion för ACARS Human Readable Parser.
    Tar emot ett meddelande, bevarar eventuella inledande prefix (t.ex. [H1: ...] eller [38]) om strip_prefix=False,
    testar mot de modulära reglerna, och returnerar en översatt text om träff finns.
    Om strip_prefix=True returneras ren meddelandetext utan inledande [Label]-prefix.
    Om ingen regel matchar returneras meddelandet (eller dess kärntext) oförändrad.
    """
    if not message:
        return ""

    # Behåll redan formaterade informativa taggar som [MIAM ...]
    if message.startswith('[MIAM'):
        return message

    # Separera eventuella inledande prefix i hakparenteser
    prefix = ""
    core_text = message
    prefix_match = re.match(r'^((?:\[[^\]]+\]\s*)+)(.*)$', message, re.DOTALL)
    if prefix_match:
        prefix = prefix_match.group(1)
        core_text = prefix_match.group(2)

    # Om ingen label skickades in explicit, härled den ur prefixet om möjligt
    if not label and prefix:
        m_lbl = re.search(r'\[([A-Z0-9_]{1,4})(?::|\])', prefix)
        if m_lbl:
            label = m_lbl.group(1)

    # Om metadata skickades in, prova att extrahera strukturerad payload om ej redan gjorts
    if isinstance(metadata, dict) and not metadata.get('decoded_fields'):
        payload_sub = parse_acars_payload(core_text, label=label)
        if payload_sub:
            metadata['decoded_fields'] = payload_sub
            if payload_sub.get('lat') is not None and payload_sub.get('lon') is not None and not metadata.get('lat'):
                metadata['lat'] = payload_sub['lat']
                metadata['lon'] = payload_sub['lon']
            if payload_sub.get('altitude_ft') is not None and not metadata.get('alt_ft'):
                metadata['alt_ft'] = payload_sub['altitude_ft']
            if payload_sub.get('eta') and not metadata.get('eta'):
                metadata['eta'] = payload_sub['eta']

    # Kör kärntexten mot samtliga regler
    out_msg = None
    for rule in PARSER_RULES:
        try:
            res = rule(core_text, label=label, metadata=metadata)
            if res:
                if strip_prefix:
                    out_msg = res.strip()
                else:
                    out_msg = f"{prefix}{res}".strip()
                break
        except Exception:
            continue

    if out_msg is None:
        # Fallback: Originaltext oförändrad (eller core_text om strip_prefix)
        if strip_prefix and core_text.strip():
            out_msg = core_text.strip()
        else:
            out_msg = message

    # Global säkerhetsspärr: Säkerställ att inga oöversatta ICAO-rutter slinker igenom
    return fix_untranslated_routes(out_msg, metadata=metadata)

