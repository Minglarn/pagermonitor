import sys
sys.path.append('d:/antigravity/pager-monitor')
from sdr_processor import parse_multimon_line

lines = [
    "POCSAG512: Address: 1234567  Function: 3  Alpha:   TEST MESSAGE",
    "POCSAG1200: Address: 1234567  Function: 3  Alpha:   HELLO WORLD",
    "POCSAG1200: Address: 1234567  Function: 3  Numeric:   12345",
]

for line in lines:
    parsed = parse_multimon_line(line, "SE")
    print(f"Line: {line}")
    print(f"Parsed: {parsed}")
