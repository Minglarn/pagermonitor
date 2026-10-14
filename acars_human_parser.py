import re

# Modulär parser för att översätta råa ACARS/VDL2-meddelanden till läsbar svensk text (Human Readable).
# Inga emojis får förekomma i denna modul eller dess formaterade utdata.

def rule_label_38_finnair_weather(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Mönster 1: Label 38 (Finnair väder- och positionsrapport)
    Exempel: /AY8892/141026/E 17.655/N 59.387/37969/-------/      /- 57/33535/ 88 /46/
    Utformat: Flight: AY8892 | Position: N 59.387, E 17.655 | Höjd: 37969 ft | Temp: -57 C | Vind: 335 deg (35 kt)
    """
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
        # 1. Flight identifierare (t.ex. AY8892)
        if i == 0 and re.match(r'^[A-Z0-9]{3,8}$', tok, re.IGNORECASE):
            flight = tok.upper()
            continue

        # 1b. Datumstämpel (t.ex. 141026 -> 14 okt 2026), hoppa över
        if i == 1 and re.match(r'^\d{6}$', tok):
            continue

        # 2. Latitud (N 59.387 / S 12.345)
        m_lat = re.match(r'^([NS])\s*(\d+\.?\d*)$', tok, re.IGNORECASE)
        if m_lat and not lat:
            lat = f"{m_lat.group(1).upper()} {m_lat.group(2)}"
            continue

        # 3. Longitud (E 17.655 / W 004.123)
        m_lon = re.match(r'^([EW])\s*(\d+\.?\d*)$', tok, re.IGNORECASE)
        if m_lon and not lon:
            lon = f"{m_lon.group(1).upper()} {m_lon.group(2)}"
            continue

        # 4. Altitud i fot (4 eller 5 siffror, t.ex. 37969)
        if re.match(r'^\d{4,5}$', tok) and not alt:
            val = int(tok)
            if 1000 <= val <= 65000:
                alt = str(val)
                continue

        # 5. Temperatur (- 57 eller +12)
        m_temp = re.match(r'^([+-])\s*(\d{1,2})$', tok)
        if m_temp and not temp:
            temp = f"{m_temp.group(1)}{m_temp.group(2)}"
            continue

        # 6. Vind (5 siffror: DDDSS t.ex. 33535 -> 335 deg, 35 kt)
        m_wind = re.match(r'^(\d{3})(\d{2})$', tok)
        if m_wind and not wind_dir and i > 2:
            wdir = int(m_wind.group(1))
            wspd = int(m_wind.group(2))
            if 0 <= wdir <= 360 and wspd < 300:
                wind_dir = wdir
                wind_spd = wspd
                continue

    # Kräver att minst flight eller position kunde identifieras
    if not (lat or lon or flight):
        return None

    parts = []
    if flight:
        parts.append(f"Flight: {flight}")
    if lat and lon:
        parts.append(f"Position: {lat}, {lon}")
    elif lat:
        parts.append(f"Position: {lat}")
    elif lon:
        parts.append(f"Position: {lon}")
    if alt:
        parts.append(f"Höjd: {alt} ft")
    if temp:
        parts.append(f"Temp: {temp} C")
    if wind_dir is not None and wind_spd is not None:
        parts.append(f"Vind: {wind_dir} deg ({wind_spd} kt)")

    return " | ".join(parts)


def rule_label_h1_posn_fms(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Mönster 2: Label H1 POSN (FMS / Färddator-rapport med rutt och väder)
    Exempel: POSN59197E017265,N55208E004569,201749,380,N60045E021311,203531,N60157E022414,M58,33488,10132A6 | Lat: 59.3283, Lon: 17.4417
    Utformat: Färddator-rutt | Höjd: FL380 | Temp: -58 C | Vind: 334 deg (88 kt) | Nästa WP: N55208E004569 (kl 20:17:49 UTC) | Lat: 59.3283, Lon: 17.4417
    """
    stripped = text.strip()
    suffix = ""
    if " | " in stripped:
        p = stripped.split(" | ", 1)
        base_text = p[0].strip()
        suffix = " | " + p[1].strip()
    else:
        base_text = stripped

    if not (base_text.startswith("POSN") or base_text.startswith("POS")):
        return None

    tokens = [t.strip() for t in base_text.split(',')]
    if len(tokens) < 4:
        return None

    # Fält 1: Nästa waypoint (t.ex. N55208E004569)
    next_wp = tokens[1] if len(tokens) > 1 and tokens[1] else None

    # Fält 2: Tidpunkt för nästa waypoint (t.ex. 201749 -> 20:17:49 UTC)
    next_time = None
    if len(tokens) > 2 and re.match(r'^\d{6}$', tokens[2]):
        hh, mm, ss = tokens[2][:2], tokens[2][2:4], tokens[2][4:6]
        next_time = f"{hh}:{mm}:{ss} UTC"

    # Fält 3: Flygnivå / Höjd (t.ex. 380 -> FL380)
    fl_str = None
    if len(tokens) > 3 and tokens[3]:
        raw_fl = tokens[3].upper()
        if raw_fl.startswith('FL'):
            fl_str = raw_fl
        elif re.match(r'^\d{2,3}$', raw_fl):
            fl_str = f"FL{raw_fl}"

    # Fält med temperatur (t.ex. M58 -> -58 C, P12 -> +12 C)
    temp_str = None
    temp_idx = -1
    for i, tok in enumerate(tokens[4:], start=4):
        m_temp = re.match(r'^([MP])(\d{2})$', tok)
        if m_temp:
            sign = '-' if m_temp.group(1) == 'M' else '+'
            temp_str = f"{sign}{m_temp.group(2)} C"
            temp_idx = i
            break

    # Fält med vind (5 siffror t.ex. 33488 -> 334 deg, 88 kt)
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

    parts = ["Färddator-rutt"]
    if fl_str:
        parts.append(f"Höjd: {fl_str}")
    if temp_str:
        parts.append(f"Temp: {temp_str}")
    if wind_str:
        parts.append(f"Vind: {wind_str}")
    if next_wp and next_time:
        parts.append(f"Nästa WP: {next_wp} (kl {next_time})")
    elif next_wp:
        parts.append(f"Nästa WP: {next_wp}")

    return " | ".join(parts) + suffix


def rule_label_h1_resreq_ack(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Mönster 3: Label H1 RESREQ/AK (Systemkvittens)
    Exempel: RESREQ/AK,1158AF6
    Utformat: Systemkvittens: Resursförfrågan bekräftad (ACK) [CRC: 1158AF6]
    """
    stripped = text.strip()
    m = re.match(r'^RESREQ/(AK|NAK)(?:,([0-9A-Fa-f]+))?$', stripped, re.IGNORECASE)
    if not m:
        return None

    status_code = m.group(1).upper()
    status_text = "bekräftad (ACK)" if status_code == "AK" else "nekad (NACK)"
    crc = m.group(2)

    if crc:
        return f"Systemkvittens: Resursförfrågan {status_text} [CRC: {crc}]"
    return f"Systemkvittens: Resursförfrågan {status_text}"


def rule_label_83_eta_report(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Mönster 4: Label 83 ETA-rapport (Gate/Ankomst)
    Exempel: V09CA032/ETA-30/2046/
    Utformat: Ankomststatus: Beräknad ankomst (ETA) kl 20:46 UTC (Status: ETA-30, Kod: V09CA032)
    """
    stripped = text.strip()
    m = re.match(r'^([A-Z0-9]+)/(ETA(?:-?\d*))/(\d{2})(\d{2})/?$', stripped, re.IGNORECASE)
    if not m:
        return None

    code = m.group(1).upper()
    status = m.group(2).upper()
    hh = m.group(3)
    mm = m.group(4)

    return f"Ankomststatus: Beräknad ankomst (ETA) kl {hh}:{mm} UTC (Status: {status}, Kod: {code})"


def rule_label_h1_mm_telemetry(text: str, label: str = None, metadata: dict = None) -> str:
    """
    Mönster 5: Label H1 MM-telemetrilogg (Fler-radig matrislogg)
    Exempel:
      MM2014241014ACD
      20122316 340 215
      20124316 1282826
    Utformat: Telemetrilogg (MM2014241014ACD): 2 mätpunkter mottagna (20:12:23 - 20:12:43 UTC)
    """
    clean = text.replace('<br>', '\n').replace('<CR><LF>', '\n').strip()
    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    if len(lines) < 2:
        return None

    if not lines[0].startswith('MM'):
        return None

    header = lines[0]
    data_lines = lines[1:]
    count = len(data_lines)

    # Försök extrahera första tidsstämpeln ur första datamätpunkten (HHMMSS)
    m_start = re.match(r'^(\d{2})(\d{2})(\d{2})', data_lines[0])
    # Försök extrahera sista tidsstämpeln ur sista datamätpunkten
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


# Lista av regler som exekveras i prioritetsordning
PARSER_RULES = [
    rule_label_38_finnair_weather,
    rule_label_h1_posn_fms,
    rule_label_h1_resreq_ack,
    rule_label_83_eta_report,
    rule_label_h1_mm_telemetry,
]

def parse_human_acars(message: str, label: str = None, metadata: dict = None) -> str:
    """
    Huvudfunktion för ACARS Human Readable Parser.
    Tar emot ett meddelande, bevarar eventuella inledande prefix (t.ex. [H1: ...] eller [38]),
    testar mot de modulära reglerna, och returnerar en översatt svensk text om träff finns.
    Om ingen regel matchar returneras originaltexten oförändrad (fallback).
    """
    if not message:
        return ""

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
                return f"{prefix}{res}".strip()
        except Exception:
            continue

    # Fallback: Originaltext oförändrad
    return message
