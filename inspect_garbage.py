
import re

def inspect_message(msg):
    print(f"\nInspecting: {repr(msg)}")
    temp_msg = re.sub(r'<[A-Z0-9]{2,4}>', '\x01', msg)
    print(f"Normalized: {repr(temp_msg)}")
    length = len(temp_msg)
    vowels = re.findall(r'[aeiouyåäöAEIOUYÅÄÖ]', temp_msg)
    letters = re.findall(r'[a-zA-ZåäöÅÄÖ]', temp_msg)
    digits = re.findall(r'\d', temp_msg)
    readable = sum(1 for c in temp_msg if c.isalnum() or c in ' .,;:!?-()/@&+=%\n\r\täöåÄÖÅ')
    
    print(f"Length: {length}")
    print(f"Vowels ({len(vowels)}): {vowels}")
    print(f"Letters ({len(letters)}): {letters}")
    print(f"Digits ({len(digits)}): {digits}")
    print(f"Readable: {readable} ({readable/length:.2f})")
    
    if len(letters) > 0:
        case_changes = 0
        for i in range(1, len(temp_msg)):
            if temp_msg[i].isalpha() and temp_msg[i-1].isalpha():
                if temp_msg[i].isupper() != temp_msg[i-1].isupper():
                    case_changes += 1
        print(f"Case changes: {case_changes} (Ratio: {case_changes/letters:.2f})")

test_garbage = [
    "p`T'",
    "C4P3å",
    "öå&o",
    ">)UUpYB!6@;4å\"Tc=5q7L.1vÖogå!ö5biWtPbjQ)JB%?)SHÖ3^v",
    "F'`SCUi;gi(aA(AY"
]

for g in test_garbage:
    inspect_message(g)
