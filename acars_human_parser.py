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
    'Q0': 'Länktest (ACARS Link Test)',
    'Q1': 'Avgångsrapport (OOOI)',
    'Q2': 'Ankomstrapport (OOOI)',
    '_d': 'Kvittens (ACK)',
    'SQ': 'Transponder / Squawk',
    '_': 'Flygledning (ATC)'
}

FALLBACK_AIRPORTS = {
    'ESSA': 'Stockholm/Arlanda',
    'ESSB': 'Stockholm/Bromma',
    'ESKN': 'Stockholm/Skavsta',
    'ESGG': 'Göteborg/Landvetter',
    'ESMS': 'Malmö',
    'ESSV': 'Visby',
    'ESOW': 'Västerås',
    'ESCF': 'Linköping/Malmen',
    'ESNN': 'Sundsvall',
    'ESNU': 'Umeå',
    'ESPA': 'Luleå',
    'ESNZ': 'Åre/Östersund',
    'ESMQ': 'Kalmar',
    'ESNX': 'Arvidsjaur',
    'ESOE': 'Örebro',
    'ESOK': 'Karlstad',
    'ESDF': 'Ronneby/Kallinge',
    'EKCH': 'Köpenhamn/Kastrup',
    'EKBI': 'Billund',
    'EKYT': 'Aalborg',
    'ENGM': 'Oslo/Gardermoen',
    'ENBR': 'Bergen/Flesland',
    'ENZV': 'Stavanger/Sola',
    'ENVA': 'Trondheim/Værnes',
    'EFHK': 'Helsingfors/Vanda',
    'EFOU': 'Uleåborg',
    'EFRO': 'Rovaniemi',
    'EFTU': 'Åbo/Turku',
    'EETN': 'Tallinn',
    'EVRA': 'Riga',
    'EYVI': 'Vilnius',
    'EPWA': 'Warszawa/Chopin',
    'EPGD': 'Gdansk',
    'EDDF': 'Frankfurt',
    'EDDM': 'München',
    'EDDB': 'Berlin',
    'EDDH': 'Hamburg',
    'EHAM': 'Amsterdam/Schiphol',
    'EBBR': 'Bryssel',
    'EGLL': 'London/Heathrow',
    'EGKK': 'London/Gatwick',
    'EGSS': 'London/Stansted',
    'EGGW': 'London/Luton',
    'EGCC': 'Manchester',
    'EIDW': 'Dublin',
    'LFPG': 'Paris/CDG',
    'LFPO': 'Paris/Orly',
    'LFMN': 'Nice',
    'LSZH': 'Zürich',
    'LSGG': 'Genève',
    'LOWW': 'Wien',
    'LIRF': 'Rom/Fiumicino',
    'LIMC': 'Milano/Malpensa',
    'LEMD': 'Madrid/Barajas',
    'LEBL': 'Barcelona',
    'LEPA': 'Palma de Mallorca',
    'LPPT': 'Lissabon',
    'LGAV': 'Aten',
    'LTFM': 'Istanbul'
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
    return f"{code} ({name})" if name else code

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
    Extraherar strukturerad data som libacars i dumpvdl2 redan har avkodat
    (t.ex. ARINC-622 ADS-C, ATS, CPDLC, FPN och VDL2 XID).
    """
    parts = []

    # 1. ARINC-622 struktur
    if isinstance(acars_dict, dict):
        arinc = acars_dict.get('arinc622')
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
                        pos_str = f"Position: {float(lat):.4f}, {float(lon):.4f}"
                        alt_str = f"Höjd: {int(float(alt))} ft" if alt else ""
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
                return f"Färdplan (FPL): {callsign}   Rutt: {airports[0]} -> {airports[1]}"
            elif len(airports) == 1:
                return f"Färdplan (FPL): {callsign}   Flygplats: {airports[0]}"
            return f"Färdplan (FPL): {callsign}"

    # 2. FPN rutt (FPN/RI...)
    if stripped.startswith('FPN') or stripped.startswith('RI/'):
        m_fpn = re.search(r'(?:FPN/)?(?:RI/)?([A-Z]{4})/([A-Z]{4})(?:/FL(\d+))?', stripped, re.IGNORECASE)
        if m_fpn:
            orig = m_fpn.group(1).upper()
            dest = m_fpn.group(2).upper()
            fl = m_fpn.group(3)
            fl_str = f"   Höjd: FL{fl}" if fl else ""
            return f"Färdplan (FPN): {orig} -> {dest}{fl_str}"

    # 3. INI flight initialization
    if stripped.startswith('INI') or '/INI/' in stripped:
        m_ini = re.search(r'INI[/ ]([A-Z]{4})[/ ]([A-Z]{4})(?:[/ ](\d{4}))?', stripped, re.IGNORECASE)
        if m_ini:
            orig = m_ini.group(1).upper()
            dest = m_ini.group(2).upper()
            tm = m_ini.group(3)
            tm_str = f"   Tid: {tm[:2]}:{tm[2:]} UTC" if tm else ""
            return f"Färdförberedelse (INI): {orig} -> {dest}{tm_str}"

    return None


def rule_label_h1_posn_fms(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Label H1 POSN: FMS / Färddator-rapport med rutt och väder.
    Exempel: POSN59197E017265,N55208E004569,201749,380,N60045E021311,203531,N60157E022414,M58,33488,10132A6
    """
    stripped = text.strip()
    pos_suffix = ""
    if " | " in stripped:
        p = stripped.split(" | ", 1)
        base_text = p[0].strip()
        pos_suffix = p[1].strip().replace(" | ", "  ")
    elif "\n" in stripped:
        p = stripped.split("\n", 1)
        base_text = p[0].strip()
        pos_suffix = p[1].strip()
    else:
        base_text = stripped

    if not (base_text.startswith("POSN") or base_text.startswith("POS") or base_text.startswith("*POS")):
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
    if len(tokens) > 3 and tokens[3]:
        raw_fl = tokens[3].upper()
        if raw_fl.startswith('FL'):
            fl_str = raw_fl
        elif re.match(r'^\d{2,3}$', raw_fl):
            fl_str = f"FL{raw_fl}"

    temp_str = None
    temp_idx = -1
    for i, tok in enumerate(tokens[4:], start=4):
        m_temp = re.match(r'^([MP])(\d{2})$', tok)
        if m_temp:
            sign = '-' if m_temp.group(1) == 'M' else '+'
            temp_str = f"{sign}{m_temp.group(2)} C"
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
                wind_str = f"{wdir} deg ({wspd} kt)"
                break

    lines = []
    line1_items = []
    if fl_str:
        line1_items.append(f"Höjd: {fl_str}")
    if temp_str:
        line1_items.append(f"Temperatur: {temp_str}")
    if wind_str:
        line1_items.append(f"Vind: {wind_str}")

    if line1_items:
        lines.append("   ".join(line1_items))

    if next_wp and next_time:
        lines.append(f"Nästa brytpunkt: {next_wp} (kl {next_time})")
    elif next_wp:
        lines.append(f"Nästa brytpunkt: {next_wp}")

    if pos_suffix:
        clean_p = pos_suffix.replace('Lat: ', '').replace('Lon: ', '')
        lines.append(f"Position: {clean_p}")

    return "\n".join(lines) if lines else None


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

    raw_preview = (stripped[:35].strip() + '...') if len(stripped) > 35 else stripped
    parts.append(f"Rådata: {raw_preview}")

    return f"[FMS Färdrapport] {' | '.join(parts)}"


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

    # Minst 85% siffror och mellanslag
    digits_and_spaces = sum(1 for c in body if c.isdigit() or c.isspace())
    if digits_and_spaces / len(body) < 0.85:
        return None

    tokens = body.split()
    num_tokens = [t for t in tokens if t.isdigit()]
    if len(num_tokens) < 10:
        return None

    total_groups = len(num_tokens)

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

    raw_preview = (stripped[:35].strip() + '...') if len(stripped) > 35 else stripped
    parts.append(f"Rådata: {raw_preview}")

    return f"[Boeing Motortelemetri / DFDAU] {' | '.join(parts)}"


def rule_aoc_airline_designated(text: str, label: str = None, metadata: dict = None) -> str:
    """Flygbolagens interna AOC-labels (Label 1L, 1A-4Z)."""
    stripped = text.strip()
    lbl = (label or '').strip().upper()
    m_aoc_seq = re.match(r'^(\d{10,12})([A-Z0-9.,\-/]+)$', stripped)
    is_aoc_label = bool(lbl == '1L' or re.match(r'^[1-4][A-Z]$', lbl))
    if lbl == '1L' or (is_aoc_label and m_aoc_seq):
        seq_part = f", Seq: {m_aoc_seq.group(1)[:6]}" if m_aoc_seq else ""
        return f"[AOC Flygbolagsdata] Intern kodad drift-/telemetrirapport (Lufthansa Group{seq_part}) | Rådata: {stripped}"
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

    w_items = []
    if alt:
        w_items.append(f"Höjd: {alt} ft")
    if temp:
        w_items.append(f"Temperatur: {temp} C")
    if wind_dir is not None and wind_spd is not None:
        w_items.append(f"Vind: {wind_dir} deg ({wind_spd} kt)")
    if w_items:
        lines.append("   ".join(w_items))

    if lat and lon:
        lines.append(f"Position: {lat}, {lon}")
    elif lat or lon:
        lines.append(f"Position: {lat or lon}")

    return "\n".join(lines)


def rule_label_83_csv_position(text: str, label: str = None, metadata: dict = None) -> str:
    """Label 83: 9-fälts CSV positionsrapport (Ethiopian Airlines m.fl.)."""
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

    line1 = f"Rutt: {dep} -> {dest} (Avgång/Ankomst)   Tid: {time_fmt}"
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
            eta_raw = tokens[6]
            eta_fmt = f"{eta_raw[:2]}:{eta_raw[2:4]} UTC" if len(eta_raw) >= 4 else eta_raw
            return f"Ankomstrapport: Rutt {orig} -> {dest}   ETA: {eta_fmt}"

    return None


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
    # Rad 1: Höjd, Temp, Vind
    row1 = []
    if 'PAALT' in kv:
        try:
            alt_ft = int(float(kv['PAALT']))
            fl = round(alt_ft / 100)
            row1.append(f"Höjd: FL{fl} ({alt_ft} ft)")
        except (ValueError, TypeError):
            pass

    if 'PASAT' in kv:
        try:
            sat = round(float(kv['PASAT']))
            row1.append(f"Temperatur: {sat} C")
        except (ValueError, TypeError):
            pass

    if 'PAWS' in kv:
        try:
            ws = round(float(kv['PAWS']))
            row1.append(f"Vind: {ws} kt")
        except (ValueError, TypeError):
            pass

    if row1:
        lines.append("   ".join(row1))

    # Rad 2: Nästa brytpunkt, Kurs, Mach, Bränsle
    row2 = []
    if 'PAFMSAWID' in kv and kv['PAFMSAWID'].strip():
        row2.append(f"Nästa brytpunkt: {kv['PAFMSAWID'].strip()}")
    if 'PATHDG' in kv:
        try:
            hdg = round(float(kv['PATHDG']))
            row2.append(f"Kurs: {hdg} deg")
        except (ValueError, TypeError):
            pass
    if 'PAMN' in kv:
        try:
            mach = float(kv['PAMN'])
            row2.append(f"Mach: {mach:.2f}")
        except (ValueError, TypeError):
            pass
    if 'PAFOB' in kv:
        try:
            fob = int(float(kv['PAFOB']))
            row2.append(f"Bränsle: {fob} kg")
        except (ValueError, TypeError):
            pass

    if row2:
        lines.append("   ".join(row2))

    # Rad 3: Position
    if 'PALAT' in kv and 'PALONG' in kv:
        try:
            lat = float(kv['PALAT'])
            lon = float(kv['PALONG'])
            lines.append(f"Position: {lat:.4f}, {lon:.4f}")
        except (ValueError, TypeError):
            pass

    return "\n".join(lines) if lines else None


def rule_label_10_through_22_pos(text: str, label: str = None, metadata: dict = None) -> str:
    """Label 10, 15, 16, 20, 21, 22: Positionsrapporter."""
    stripped = text.strip()
    lbl = (label or '').upper()

    # Exempel: 191331,37012,1946, 74,N 56.955 E 17.322
    m_pos = re.search(r'([NS]\s*\d+\.?\d*)\s*([EW]\s*\d+\.?\d*)', stripped, re.IGNORECASE)
    if m_pos and (lbl in ('10', '15', '16', '20', '21', '22', 'POS') or ',' in stripped):
        lat_txt = m_pos.group(1).strip()
        lon_txt = m_pos.group(2).strip()
        # Försök hitta altitud
        alt_match = re.search(r'\b(\d{4,5})\b', stripped)
        if alt_match:
            alt_val = int(alt_match.group(1))
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
        extracted.append(f"Rutt: {m_route.group(1)} -> {m_route.group(2)}")
    else:
        m_route3 = re.search(r'\b([A-Z]{3})[/->]([A-Z]{3})\b', stripped)
        if m_route3:
            extracted.append(f"Rutt: {m_route3.group(1)} -> {m_route3.group(2)}")

    # 2. ETA: t.ex. ETA 1234 eller ETA:1234
    m_eta = re.search(r'\bETA\s*[:=]?\s*(\d{2})(\d{2})\b', stripped, re.IGNORECASE)
    if m_eta:
        extracted.append(f"ETA: {m_eta.group(1)}:{m_eta.group(2)} UTC")

    # 3. Höjd / Flygnivå: t.ex. FL360 eller FL 360
    m_fl = re.search(r'\bFL\s*(\d{2,3})\b', stripped, re.IGNORECASE)
    if m_fl:
        extracted.append(f"Höjd: FL{m_fl.group(1)}")

    # 4. Koordinater: t.ex. 58.54N 18.94E eller N58.54 E18.94
    m_coord = re.search(r'([NS]\s*\d+\.?\d*)\s*[,/ ]\s*([EW]\s*\d+\.?\d*)', stripped, re.IGNORECASE)
    if m_coord:
        extracted.append(f"Position: {m_coord.group(1)}, {m_coord.group(2)}")

    if extracted:
        summary = "   ".join(extracted)
        return f"{summary}\n{stripped}"

    return None


# Lista av regler som exekveras i prioritetsordning
PARSER_RULES = [
    rule_libacars_structured,
    rule_miam_airbus_telemetry,
    rule_label_sa_media_advisory,
    rule_label_b6_cpdlc,
    rule_label_5u_weather_request,
    rule_label_q0_link_test,
    rule_fms_progress_destination,
    rule_boeing_dfdau_engine_telemetry,
    rule_aoc_airline_designated,
    rule_label_h1_fpn_flight_plan,
    rule_label_h1_posn_fms,
    rule_label_h1_resreq_ack,
    rule_label_h1_mm_telemetry,
    rule_label_38_finnair_weather,
    rule_label_83_csv_position,
    rule_label_83_eta_report,
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

    # Kör kärntexten mot samtliga regler
    for rule in PARSER_RULES:
        try:
            res = rule(core_text, label=label, metadata=metadata)
            if res:
                if strip_prefix:
                    return res.strip()
                return f"{prefix}{res}".strip()
        except Exception:
            continue

    # Fallback: Originaltext oförändrad (eller core_text om strip_prefix)
    if strip_prefix and core_text.strip():
        return core_text.strip()
    return message
