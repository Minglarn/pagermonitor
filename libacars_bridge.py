"""
libacars_bridge.py - ctypes-brygga till libacars (libacars-2.so)
Möjliggör direkt C-avkodning av binära och komprimerade ACARS-protokoll
(t.ex. ARINC 622 ADS-C och CPDLC, MIAM) för datakällor som saknar inbyggd
libacars-avkodning (såsom SatDump inmarsat_aero eller enkla VHF ACARS-flöden).
"""

import ctypes
import ctypes.util
import json
import logging
import os
import re
import sys

logger = logging.getLogger(__name__)

def clean_fans_payload(message: str) -> str:
    """Rensar bort ACARS-routing-headers för att ge libacars ren hex-data."""
    if not message or not isinstance(message, str):
        return message

    trimmed = message.strip()
    match = re.search(r'^.*?(?:[A-Z0-9/]+)?\.AT\d+\.([0-9A-Fa-f]+)$', trimmed, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    return message

# ctypes definitioner för libacars interna datatyper
class LaVString(ctypes.Structure):
    _fields_ = [
        ("str", ctypes.c_char_p),
        ("len", ctypes.c_size_t),
        ("allocated_size", ctypes.c_size_t)
    ]

LaProtoNodePtr = ctypes.c_void_p
LaVStringPtr = ctypes.POINTER(LaVString)

# Riktning för ACARS-meddelanden (la_msg_dir enum)
LA_MSG_DIR_UNKNOWN = 0
LA_MSG_DIR_GND2AIR = 1
LA_MSG_DIR_AIR2GND = 2

# Global referens till laddat C-bibliotek
_libacars = None
_libacars_loaded = False
_mock_decoder = None  # Används för tester i miljöer utan kompilerat libacars-bibliotek

def _load_libacars():
    """
    Söker efter och laddar libacars-2.so (eller libacars.so / DLL).
    Söker i systemets standardbibliotekskataloger, /usr/local/lib, /usr/lib samt via find_library.
    """
    global _libacars, _libacars_loaded
    if _libacars_loaded:
        return _libacars

    candidate_paths = [
        "libacars-2.so.2",
        "libacars-2.so",
        "/usr/local/lib/libacars-2.so",
        "/usr/local/lib/libacars-2.so.2",
        "/usr/lib/libacars-2.so",
        "/usr/lib/libacars-2.so.2",
        "/usr/lib/x86_64-linux-gnu/libacars-2.so",
        "/usr/lib/aarch64-linux-gnu/libacars-2.so",
        "libacars.so",
        "libacars-2.dll",
        "libacars.dll"
    ]

    # Prova find_library
    found = ctypes.util.find_library("acars-2") or ctypes.util.find_library("acars")
    if found:
        candidate_paths.insert(0, found)

    for path in candidate_paths:
        try:
            lib = ctypes.CDLL(path)
            # Konfigurera funktionssignaturer
            lib.la_acars_decode_apps.restype = LaProtoNodePtr
            lib.la_acars_decode_apps.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]

            lib.la_proto_tree_format_json.restype = LaVStringPtr
            lib.la_proto_tree_format_json.argtypes = [LaVStringPtr, LaProtoNodePtr]

            lib.la_vstring_destroy.restype = None
            lib.la_vstring_destroy.argtypes = [LaVStringPtr, ctypes.c_bool]

            lib.la_proto_tree_destroy.restype = None
            lib.la_proto_tree_destroy.argtypes = [LaProtoNodePtr]

            _libacars = lib
            _libacars_loaded = True
            logger.info(f"[LIBACARS] Bibliotek laddat framgångsrikt från: {path}")
            return _libacars
        except (OSError, AttributeError):
            continue

    _libacars_loaded = True  # Markera att sökning genomförts för att undvika upprepade filaccesser
    logger.debug("[LIBACARS] libacars delat bibliotek hittades inte i miljön (körs i ren Python-läge).")
    return None

def is_libacars_available() -> bool:
    """Returnerar True om libacars-2.so är tillgängligt och initierat, eller om mock är aktiv."""
    if _mock_decoder is not None:
        return True
    lib = _load_libacars()
    return lib is not None

def set_mock_decoder(decoder_fn):
    """Sätter en mock-avkodare för enhetstester."""
    global _mock_decoder
    _mock_decoder = decoder_fn

def decode_acars_apps(label: str, text: str, msg_dir: int = LA_MSG_DIR_UNKNOWN) -> dict:
    """
    Avkodar ACARS applikationslager (ARINC 622 CPDLC / ADS-C, MIAM etc.) med libacars.
    
    Parametrar:
      label: ACARS label-kod (t.ex. 'H1', '21', 'RA', 'B6', 'CR')
      text: Rå meddelandesträng från ACARS
      msg_dir: LA_MSG_DIR_UNKNOWN (0), LA_MSG_DIR_GND2AIR (1), LA_MSG_DIR_AIR2GND (2)
      
    Returnerar:
      dict med det avkodade JSON-trädet från libacars, eller None om meddelandet inte
      kunde avkodas av libacars eller om biblioteket saknas.
    """
    if not label or not text:
        return None

    if label in ('H1', '_F', 'CR') or '.AT' in text:
        text = clean_fans_payload(text)

    if _mock_decoder is not None:
        return _mock_decoder(label, text, msg_dir)

    lib = _load_libacars()
    if not lib:
        return None

    try:
        label_bytes = str(label).strip().encode('ascii', errors='ignore')
        text_bytes = str(text).strip().encode('ascii', errors='ignore')

        # 1. Bygg protokollträd i libacars
        node = lib.la_acars_decode_apps(label_bytes, text_bytes, msg_dir)
        if not node:
            return None

        # 2. Formatera protokollträdet till JSON-sträng
        vstr = lib.la_proto_tree_format_json(None, node)
        if not vstr:
            lib.la_proto_tree_destroy(node)
            return None

        json_bytes = vstr.contents.str
        result_dict = None
        if json_bytes:
            try:
                json_str = json_bytes.decode('utf-8', errors='replace')
                result_dict = json.loads(json_str)
            except Exception as e:
                logger.debug(f"[LIBACARS] JSON-avkodningsfel: {e}")

        # 3. Frigör allokerat minne i C-biblioteket
        lib.la_vstring_destroy(vstr, True)
        lib.la_proto_tree_destroy(node)

        return result_dict
    except Exception as e:
        logger.debug(f"[LIBACARS] Oväntat fel vid ctypes-avkodning: {e}")
        return None
