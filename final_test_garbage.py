
import re

def is_garbage_message_v3(message, sensitivity=50):
    if not message or len(message.strip()) == 0:
        return True

    msg = message.strip()
    temp_msg = re.sub(r'<[A-Z0-9]{2,4}>', '\x01', msg)
    length = len(temp_msg)

    if length < 3:
        return True

    readable_chars = ' .,;:!?-()/@&+=%\n\r\täöåÄÖÅ'
    readable = sum(1 for c in temp_msg if c.isalnum() or c in readable_chars)
    control = sum(1 for c in temp_msg if ord(c) < 32 and c not in '\t\n\r')
    
    readable_ratio = readable / length
    control_ratio = control / length

    # Base thresholds
    readable_min = 0.50 + (sensitivity / 100.0) * 0.30 
    control_max = 0.25 - (sensitivity / 100.0) * 0.20

    if control_ratio > control_max:
        return True
    
    # 3+ symbols in a row
    if re.search(r'[^a-zA-Z0-9\såäöÅÄÖ]{3,}', temp_msg):
        return True

    if length > 5:
        unique_ratio = len(set(temp_msg)) / length
        if unique_ratio > 0.70 and readable_ratio < 0.90:
             return True

    vowels = len(re.findall(r'[aeiouyåäöAEIOUYÅÄÖ]', temp_msg))
    digits = len(re.findall(r'\d', temp_msg))
    letters = re.findall(r'[a-zA-ZåäöÅÄÖ]', temp_msg)
    
    # Structure check
    if len(letters) > 4:
        case_changes = 0
        for i in range(1, len(temp_msg)):
            if temp_msg[i].isalpha() and temp_msg[i-1].isalpha():
                if temp_msg[i].isupper() != temp_msg[i-1].isupper():
                    case_changes += 1
        if case_changes / len(letters) > 0.35:
            return True

    if len(letters) > 2 and vowels == 0 and digits < 3:
        return True

    if readable_ratio < readable_min:
        return True

    return False

test_garbage = [
    "p`T'",
    "C4P3å",
    "öå&o",
    ">)UUpYB!6@;4å\"Tc=5q7L.1vÖogå!ö5biWtPbjQ)JB%?)SHÖ3^v",
    "F'`SCUi;gi(aA(AY"
]

test_valid = [
    "LARM: BRAND I BYGGNAD, STORGATAN 1",
    "Provlarm från SOS Alarm",
    "Vattenläcka rapporterad i källaren på skolan",
    "720412-1234",
    "Sms: Hej hur mår du?"
]

print("--- Final Verifier (V3) ---")
for msg in test_garbage:
    res = is_garbage_message_v3(msg, 50)
    print(f"Garbage: {'[OK]' if res else '[FAIL]'} -> {msg}")

for msg in test_valid:
    res = is_garbage_message_v3(msg, 50)
    print(f"Valid:   {'[OK]' if not res else '[FAIL]'} -> {msg}")
