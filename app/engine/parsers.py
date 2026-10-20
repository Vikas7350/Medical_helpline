"""Multilingual input parsers for rural health helpline IVR.

Supports natural spoken language and DTMF keypad input across
English ('en'), Hindi ('hi'), and Marathi ('mr').
"""

import re
from typing import Optional

# Devanagari numerals to ASCII digits mapping
DEVANAGARI_DIGITS = {
    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9",
}

# Number words mapping across English, Hindi, and Marathi
NUMBER_WORDS = {
    # English
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    # Hindi
    "शून्य": 0,
    "एक": 1,
    "दो": 2,
    "तीन": 3,
    "चार": 4,
    "पांच": 5,
    "पाँच": 5,
    "छह": 6,
    "छः": 6,
    "सात": 7,
    "आठ": 8,
    "नौ": 9,
    "दस": 10,
    "ग्यारह": 11,
    "बारह": 12,
    "तेरह": 13,
    "चौदह": 14,
    "पंद्रह": 15,
    "बीस": 20,
    "तीस": 30,
    # Marathi
    "दोन": 2,
    "पाच": 5,
    "सहा": 6,
    "नऊ": 9,
    "दहा": 10,
    "अकरा": 11,
    "बारा": 12,
    "तेरा": 13,
    "चौदा": 14,
    "पंधरा": 15,
    "वीस": 20,
    # Common Roman transliterations
    "ek": 1,
    "do": 2,
    "don": 2,
    "teen": 3,
    "tin": 3,
    "char": 4,
    "paanch": 5,
    "panch": 5,
    "saat": 7,
    "aath": 8,
    "nau": 9,
    "das": 10,
}


def normalize_digits(text: str) -> str:
    """Convert Devanagari numerals to ASCII digits."""
    for dev, ascii_digit in DEVANAGARI_DIGITS.items():
        text = text.replace(dev, ascii_digit)
    return text


def parse_duration(user_input: str, language: Optional[str] = None) -> Optional[int]:
    """Parse spoken duration or DTMF input into duration in days.

    Returns:
        int: Duration in days if recognized.
        None: If input is unclear, invalid, or does not indicate a duration.
    """
    raw = (user_input or "").strip()
    if not raw:
        return None

    cleaned = normalize_digits(raw.lower())

    # 1. Exact DTMF / numeric option codes:
    # "1" -> option 1 (<3 days -> 1 day)
    # "2" -> option 2 (>=3 days -> 4 days)
    if cleaned in ("1", "option 1", "option one"):
        return 1
    if cleaned in ("2", "option 2", "option two"):
        return 4

    # 2. Week expressions:
    # Explicit weeks with digits: "2 weeks", "1 week", "3 हफ्ते", "२ आठवडे"
    week_digit_match = re.search(r"\b(\d+)\s*(weeks?|हफ्ते?|हफ्ता|हफ्त्यांपासून|सप्ताह|आठवडे?|आठवडा|आठवड्यांपासून)\b", cleaned)
    if week_digit_match:
        return max(1, int(week_digit_match.group(1)) * 7)

    # Weeks with word numbers: "two weeks", "दो हफ्ते", "एक आठवडा"
    for word, num in NUMBER_WORDS.items():
        pattern = rf"\b{re.escape(word)}\s+(weeks?|हफ्ते?|हफ्ता|हफ्त्यांपासून|सप्ताह|आठवडे?|आठवडा|आठवड्यांपासून)\b"
        if re.search(pattern, cleaned):
            return max(1, num * 7)

    # Standalone week words: "a week", "one week", "हफ्ताभर", "आठवडा"
    if any(w in cleaned for w in ("week", "हफ्ता", "हफ्ते", "सप्ताह", "आठवडा", "आठवडे")):
        return 7

    # 3. Explicit days with digits: "3 days", "4 दिन", "2 दिवस", "5 days"
    day_digit_match = re.search(r"\b(\d+)\s*(days?|दिन|दिनों|दिवस|दिवसांपासून|रोज)\b", cleaned)
    if day_digit_match:
        return max(1, int(day_digit_match.group(1)))

    # 4. Explicit days with word numbers: "three days", "तीन दिन", "दोन दिवस", "दो दिन", "four days"
    for word, num in NUMBER_WORDS.items():
        pattern = rf"\b{re.escape(word)}\s+(days?|दिन|दिनों|दिवस|दिवसांपासून|रोज)\b"
        if re.search(pattern, cleaned):
            return max(1, num)

    # 5. Relative time phrases
    # Today / morning -> 1 day
    if any(p in cleaned for p in ("today", "morning", "since morning", "from today", "आज", "आज से", "आजपासून", "सुबह से", "सकाळपासून")):
        return 1

    # Yesterday / since yesterday -> 2 days (< 3 days)
    if any(p in cleaned for p in ("yesterday", "since yesterday", "कल से", "कालपासून")):
        return 2

    # Day before yesterday -> 3 days
    if any(p in cleaned for p in ("day before yesterday", "परसों से", "परवापासून")):
        return 3

    # 6. Comparative phrases matching the IVR prompt
    # Less than 3 days phrasing -> 1 day
    if any(p in cleaned for p in ("less than", "under 3", "under three", "3 दिन से कम", "तीन दिन से कम", "३ दिवसांपेक्षा कमी", "तीन दिवसांपेक्षा कमी", "कम", "कमी")):
        return 1

    # More than 3 days phrasing -> 4 days
    if any(p in cleaned for p in ("more than", "over 3", "over three", "3 दिन से अधिक", "3 दिन से ज्यादा", "तीन दिन से ज्यादा", "३ दिवसांपेक्षा जास्त", "तीन दिवसांपेक्षा जास्त", "ज्यादा", "अधिक", "जास्त", "काफी दिन", "खूप दिवस")):
        return 4

    # 7. Standalone number words or digits
    # Digits >= 3 (e.g. "3", "4", "5", "10") -> exact number of days
    digit_match = re.fullmatch(r"\d+", cleaned)
    if digit_match:
        val = int(digit_match.group(0))
        if val == 1:
            return 1
        elif val == 2:
            return 4  # Matches option 2 (>=3 days)
        else:
            return val

    # Word numbers alone (e.g. "तीन", "three", "four", "चार", "पाच", "पांच")
    for word, num in NUMBER_WORDS.items():
        if re.fullmatch(rf"{re.escape(word)}", cleaned) or cleaned.startswith(f"{word} ") or cleaned.endswith(f" {word}"):
            if num == 1:
                return 1
            elif num == 2:
                return 4  # Option 2
            else:
                return num

    return None


def parse_severity(user_input: str, language: Optional[str] = None) -> Optional[int]:
    """Parse spoken severity or DTMF input into a severity score (1 to 10).

    Returns:
        1: Mild (prompt option 1)
        2: Moderate (prompt option 2)
        8: Severe (prompt option 3, triggers prompt medical assessment escalation)
        None: If input is unclear or invalid.
    """
    raw = (user_input or "").strip()
    if not raw:
        return None

    cleaned = normalize_digits(raw.lower())

    # Exact DTMF / numeric options:
    if cleaned in ("1", "option 1", "option one"):
        return 1
    if cleaned in ("2", "option 2", "option two"):
        return 2
    if cleaned in ("3", "option 3", "option three"):
        return 8

    # Severe keywords (Check severe first to avoid overlap)
    severe_keywords = [
        "severe", "high", "very high", "extreme", "unbearable", "terrible", "bad",
        "very bad", "acute", "intense", "critical",
        "तेज", "बहुत तेज", "गंभीर", "असहनीय", "बहुत ज्यादा",
        "तीव्र", "खूप", "खूप जास्त", "प्रचंड", "असह्य",
        "three", "तीन",
    ]
    if any(k in cleaned for k in severe_keywords):
        return 8

    # Mild keywords
    mild_keywords = [
        "mild", "slight", "low", "minor", "little", "not much", "small", "light",
        "हल्का", "हल्की", "कम", "थोड़ा", "थोड़ी", "सामान्य", "हलका", "हलकी",
        "कमी", "थोडा", "थोडी", "कमी प्रमाणात", "फार नाही",
        "one", "एक",
    ]
    if any(k in cleaned for k in mild_keywords):
        return 1

    # Moderate keywords
    moderate_keywords = [
        "moderate", "medium", "normal", "average", "bearable", "okay", "tolerable",
        "मध्यम", "ठीक", "साधारण", "सहन", "बीच का",
        "सहन होण्यासारखा",
        "two", "दो", "दोन",
    ]
    if any(k in cleaned for k in moderate_keywords):
        return 2

    return None


def parse_yes_no(user_input: str, language: Optional[str] = None) -> Optional[bool]:
    """Parse spoken or DTMF yes/no answer.

    Returns:
        True: Confirmed Yes (DTMF 1 or spoken affirmative)
        False: Confirmed No (DTMF 2 or spoken negative)
        None: Unclear, empty, or invalid input
    """
    raw = (user_input or "").strip()
    if not raw:
        return None

    cleaned = normalize_digits(raw.lower())

    # Check exact DTMF
    if cleaned in ("1", "option 1", "option one"):
        return True
    if cleaned in ("2", "option 2", "option two"):
        return False

    # Negative words (check first to handle phrases like "नहीं है", "no i don't")
    negative_patterns = [
        "no", "nope", "not", "none", "negative", "nothing",
        "नहीं", "ना", "जी नहीं", "कुछ नहीं", "नहीं है",
        "नाही", "नाहीये", "काही नाही",
    ]
    for neg in negative_patterns:
        # Match as word boundary or exact token
        if re.search(rf"(?:^|\s){re.escape(neg)}(?:$|\s)", cleaned) or cleaned == neg:
            return False

    # Affirmative words
    positive_patterns = [
        "yes", "yeah", "yep", "yup", "correct", "true", "sure", "affirmative", "i do", "i have",
        "हाँ", "हां", "हाँजी", "हांजी", "जी हाँ", "जी हां", "सही", "बिल्कुल",
        "होय", "हो", "आहे", "बरोबर", "नक्की",
    ]
    for pos in positive_patterns:
        if re.search(rf"(?:^|\s){re.escape(pos)}(?:$|\s)", cleaned) or cleaned == pos:
            return True

    return None


def is_repeat_command(user_input: str) -> bool:
    """Check if input is DTMF 0 or spoken repeat request."""
    raw = (user_input or "").strip().lower()
    if not raw:
        return False

    if raw == "0":
        return True

    repeat_patterns = [
        "repeat", "repeat please", "please repeat", "say again", "once more", "pardon",
        "दोहराएं", "दोहराओ", "दोहराइए", "फिर से", "फिर से बोलो", "दोबारा", "दोबारा बोलो",
        "पुन्हा सांगा", "परत सांगा", "पुन्हा बोला", "परत बोला", "आणखी एकदा",
    ]
    return any(p in raw for p in repeat_patterns)


def is_exit_command(user_input: str) -> bool:
    """Check if input is DTMF 9 or explicit spoken call termination command."""
    raw = (user_input or "").strip().lower()
    if not raw:
        return False

    if raw == "9":
        return True

    exit_patterns = [
        "exit", "quit", "goodbye", "bye", "hang up", "end call", "end the call",
        "कॉल समाप्त", "कॉल काटो", "कॉल बंद", "समाप्त करें", "अलविदा",
        "कॉल संपवा", "कॉल बंद करा", "कॉल तोडा",
    ]
    return any(raw == p or f" {p}" in raw or raw.startswith(f"{p} ") for p in exit_patterns)
