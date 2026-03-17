
import re

CHAR_MAP = {
    '[': 'Ä',
    '\\': 'Ö',
    ']': 'Å',
    '{': 'ä',
    '|': 'ö',
    '}': 'å'
}

def translate_swedish_chars(text):
    for k, v in CHAR_MAP.items():
        text = text.replace(k, v)
    return text

def is_garbage_message(message, sensitivity=50):
    """Original logic from sdr_processor.py"""
    if not message or len(message.strip()) == 0:
        return True

    msg = message.strip()
    temp_msg = re.sub(r'<[A-Z0-9]{2,4}>', '\x01', msg)
    length = len(temp_msg)

    readable_min = 0.30 + (sensitivity / 100.0) * 0.40
    control_max = 0.35 - (sensitivity / 100.0) * 0.25

    readable = sum(1 for c in temp_msg if c.isalnum() or c in ' .,;:!?-()/@&+=%\n\r\täöåÄÖÅ')
    control = sum(1 for c in temp_msg if ord(c) < 32 and c not in '\t\n\r')

    readable_ratio = readable / length
    control_ratio = control / length

    if control_ratio > control_max:
        return True
    if readable_ratio < readable_min:
        return True

    if length > 10:
        unique_ratio = len(set(msg)) / length
        if unique_ratio > 0.85 and readable_ratio < (readable_min + 0.15):
            return True

    return False

def is_garbage_message_improved(message, sensitivity=50):
    """Improved logic to catch the user's examples."""
    if not message or len(message.strip()) == 0:
        return True

    msg = message.strip()
    # Normalize multimon tags
    temp_msg = re.sub(r'<[A-Z0-9]{2,4}>', '\x01', msg)
    length = len(temp_msg)

    # 1. Basic length check
    if length < 3:
        return True

    # 2. Ratio of "good" vs "bad" chars
    readable = sum(1 for c in temp_msg if c.isalnum() or c in ' .,;:!?-()/@&+=%\n\r\täöåÄÖÅ')
    control = sum(1 for c in temp_msg if ord(c) < 32 and c not in '\t\n\r')
    
    readable_ratio = readable / length
    control_ratio = control / length

    # Sensitivity scaling
    readable_min = 0.50 + (sensitivity / 100.0) * 0.30 # 0.5 to 0.8
    control_max = 0.25 - (sensitivity / 100.0) * 0.20 # 0.25 to 0.05

    if control_ratio > control_max:
        return True
    
    # 3. Pattern checks for "obviously" junk patterns
    # - Too many consecutive symbols/non-alphanumeric (except space)
    if re.search(r'[^a-zA-Z0-9\såäöÅÄÖ]{3,}', temp_msg):
        return True

    # 4. Entropy / Unique ratio
    if length > 5:
        unique_chars = len(set(temp_msg))
        unique_ratio = unique_chars / length
        # High entropy but low readable ratio
        if unique_ratio > 0.70 and readable_ratio < 0.85:
             return True
        if unique_ratio < 0.15 and length > 15: # Very repetitive
             return True

    # 5. Word/Vowel/Structure check
    vowels = len(re.findall(r'[aeiouyåäöAEIOUYÅÄÖ]', temp_msg))
    digits = len(re.findall(r'\d', temp_msg))
    letters = len(re.findall(r'[a-zA-ZåäöÅÄÖ]', temp_msg))
    
    # Random casing: "F'`SCUi;gi" - check for ratio of case changes if mostly letters
    if letters > 4:
        case_changes = 0
        for i in range(1, len(temp_msg)):
            if temp_msg[i].isalpha() and temp_msg[i-1].isalpha():
                if temp_msg[i].isupper() != temp_msg[i-1].isupper():
                    case_changes += 1
        if case_changes / letters > 0.4: # Too much toggling between upper/lower
            return True

    # vana: Real messages have words. 
    # "C4P3å" -> letters=3, vowels=0 (å is not always caught by [aeiou]), digits=2
    # Let's include Swedish vowels in the vowel check explicitly if not already
    
    if letters > 2 and vowels == 0 and digits < 3:
        return True

    if readable_ratio < readable_min:
        return True

    return False

# Nya testfall från användaren
test_garbage = [
    "p`T'",
    "C4P3å",
    "öå&o",
    ">)UUpYB!6@;4å\"Tc=5q7L.1vÖogå!ö5biWtPbjQ)JB%?)SHÖ3^v",
    "F'`SCUi;gi(aA(AY"
]

# Några giltiga meddelanden
test_valid = [
    "LARM: BRAND I BYGGNAD, STORGATAN 1",
    "Provlarm från SOS Alarm",
    "Vattenläcka rapporterad i källaren på skolan",
    "720412-1234", # ID-nummer
    "Sms: Hej hur mår du?"
]

print("--- Testing Improved Logic (Sensitivity 50) ---")
for msg in test_garbage:
    result = is_garbage_message_improved(msg, 50)
    print(f"Garbage: {'[OK]' if result else '[FAIL]'} -> {msg}")

for msg in test_valid:
    result = is_garbage_message_improved(msg, 50)
    print(f"Valid:   {'[OK]' if not result else '[FAIL]'} -> {msg}")
