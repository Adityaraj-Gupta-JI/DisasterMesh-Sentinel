"""Multilingual emergency lexicon (English, Hindi, Tamil).

Deliberately explicit data, not a model. It powers the deterministic rule triage that
runs when no model is loaded — the fallback that keeps the product working offline —
and it doubles as the mock model used in tests.
"""

from __future__ import annotations

from ..domain.enums import ConditionType, DisasterType

#: term -> (disaster types, severity contribution, safety flag or None)
DISASTER_TERMS: dict[str, tuple[tuple[DisasterType, ...], int, str | None]] = {
    # --- English
    "fire": ((DisasterType.FIRE,), 70, "active_fire"),
    "burning": ((DisasterType.FIRE,), 70, "active_fire"),
    "smoke": ((DisasterType.FIRE,), 45, None),
    "flood": ((DisasterType.FLOOD,), 60, None),
    "flooding": ((DisasterType.FLOOD,), 60, None),
    "water rising": ((DisasterType.FLOOD,), 70, None),
    "drowning": ((DisasterType.FLOOD, DisasterType.MEDICAL), 90, "immediate_life_threat"),
    "earthquake": ((DisasterType.EARTHQUAKE,), 75, None),
    "collapsed": ((DisasterType.BUILDING_COLLAPSE,), 80, None),
    "collapse": ((DisasterType.BUILDING_COLLAPSE,), 80, None),
    "landslide": ((DisasterType.LANDSLIDE,), 75, None),
    "accident": ((DisasterType.ACCIDENT,), 55, None),
    "crash": ((DisasterType.ACCIDENT,), 60, None),
    "injured": ((DisasterType.MEDICAL,), 60, None),
    "bleeding": ((DisasterType.MEDICAL,), 75, "immediate_life_threat"),
    "unconscious": ((DisasterType.MEDICAL,), 90, "immediate_life_threat"),
    "not breathing": ((DisasterType.MEDICAL,), 95, "immediate_life_threat"),
    "heart attack": ((DisasterType.MEDICAL,), 90, "immediate_life_threat"),
    "trapped": ((DisasterType.TRAPPED_PERSON,), 85, "immediate_life_threat"),
    "stuck under": ((DisasterType.TRAPPED_PERSON,), 85, "immediate_life_threat"),
    "missing": ((DisasterType.MISSING_PERSON,), 55, None),
    "water": ((DisasterType.LOGISTICS,), 15, None),
    "food": ((DisasterType.LOGISTICS,), 12, None),
    "shelter": ((DisasterType.LOGISTICS,), 12, None),
    "supplies": ((DisasterType.LOGISTICS,), 12, None),
    "blanket": ((DisasterType.LOGISTICS,), 10, None),
    # --- Hindi (Devanagari)
    "आग": ((DisasterType.FIRE,), 70, "active_fire"),
    "बाढ़": ((DisasterType.FLOOD,), 60, None),
    "भूकंप": ((DisasterType.EARTHQUAKE,), 75, None),
    "इमारत गिर": ((DisasterType.BUILDING_COLLAPSE,), 80, None),
    "फंसे": ((DisasterType.TRAPPED_PERSON,), 85, "immediate_life_threat"),
    "फंस": ((DisasterType.TRAPPED_PERSON,), 85, "immediate_life_threat"),
    "घायल": ((DisasterType.MEDICAL,), 60, None),
    "बेहोश": ((DisasterType.MEDICAL,), 90, "immediate_life_threat"),
    "खून": ((DisasterType.MEDICAL,), 75, "immediate_life_threat"),
    "मदद": ((DisasterType.OTHER,), 40, None),
    "पानी": ((DisasterType.LOGISTICS,), 15, None),
    # --- Tamil
    "தீ": ((DisasterType.FIRE,), 70, "active_fire"),
    "வெள்ளம்": ((DisasterType.FLOOD,), 60, None),
    "நிலநடுக்கம்": ((DisasterType.EARTHQUAKE,), 75, None),
    "இடிந்து": ((DisasterType.BUILDING_COLLAPSE,), 80, None),
    "சிக்கி": ((DisasterType.TRAPPED_PERSON,), 85, "immediate_life_threat"),
    "காயம்": ((DisasterType.MEDICAL,), 60, None),
    "மயக்கம்": ((DisasterType.MEDICAL,), 90, "immediate_life_threat"),
    "உதவி": ((DisasterType.OTHER,), 40, None),
    "தண்ணீர்": ((DisasterType.LOGISTICS,), 15, None),
}

CONDITION_TERMS: dict[str, ConditionType] = {
    "trapped": ConditionType.TRAPPED,
    "stuck under": ConditionType.TRAPPED,
    "फंसे": ConditionType.TRAPPED,
    "फंस": ConditionType.TRAPPED,
    "சிக்கி": ConditionType.TRAPPED,
    "missing": ConditionType.MISSING,
    "लापता": ConditionType.MISSING,
    "காணவில்லை": ConditionType.MISSING,
    "unconscious": ConditionType.UNCONSCIOUS,
    "बेहोश": ConditionType.UNCONSCIOUS,
    "மயக்கம்": ConditionType.UNCONSCIOUS,
    "not breathing": ConditionType.NOT_BREATHING,
    "साँस नहीं": ConditionType.NOT_BREATHING,
    "மூச்சு இல்லை": ConditionType.NOT_BREATHING,
    "bleeding": ConditionType.BLEEDING,
    "खून": ConditionType.BLEEDING,
    "ரத்தம்": ConditionType.BLEEDING,
    "dead": ConditionType.DEAD,
    "मृत": ConditionType.DEAD,
    "இறந்த": ConditionType.DEAD,
    "injured": ConditionType.INJURY,
    "घायल": ConditionType.INJURY,
    "காயம்": ConditionType.INJURY,
}

HAZARD_TERMS: tuple[str, ...] = (
    "gas leak",
    "live wire",
    "smoke",
    "fire",
    "debris",
    "current",
    "आग",
    "धुआं",
    "मलबा",
    "தீ",
    "புகை",
)

RESOURCE_TERMS: dict[str, str] = {
    "ambulance": "AMBULANCE",
    "boat": "RESCUE_BOAT",
    "rescue": "SEARCH_TEAM",
    "doctor": "MEDICAL_TEAM",
    "medic": "MEDICAL_TEAM",
    "fire brigade": "FIRE_UNIT",
    "water": "SUPPLY_TRUCK",
    "food": "SUPPLY_TRUCK",
    "shelter": "SHELTER",
    "एम्बुलेंस": "AMBULANCE",
    "नाव": "RESCUE_BOAT",
    "डॉक्टर": "MEDICAL_TEAM",
    "ஆம்புலன்ஸ்": "AMBULANCE",
    "படகு": "RESCUE_BOAT",
    "மருத்துவர்": "MEDICAL_TEAM",
}

#: Written numbers that map to an exact count.
NUMBER_WORDS: dict[str, int] = {
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
    "twelve": 12,
    "twenty": 20,
    "एक": 1,
    "दो": 2,
    "तीन": 3,
    "चार": 4,
    "पांच": 5,
    "पाँच": 5,
    "ஒரு": 1,
    "இரண்டு": 2,
    "மூன்று": 3,
    "நான்கு": 4,
    "ஐந்து": 5,
}

#: Vague quantities. These must NEVER become an exact number.
APPROXIMATE_WORDS: tuple[str, ...] = (
    "some",
    "several",
    "many",
    "few",
    "a lot",
    "multiple",
    "crowd",
    "कुछ",
    "कई",
    "बहुत",
    "சில",
    "பல",
    "நிறைய",
)

LANGUAGE_HINTS: dict[str, tuple[str, ...]] = {
    "hi": ("आग", "बाढ़", "फंसे", "मदद", "घायल", "पानी", "बेहोश", "लोग"),
    "ta": ("தீ", "வெள்ளம்", "சிக்கி", "உதவி", "காயம்", "தண்ணீர்", "மயக்கம்", "நபர்"),
}


def detect_language(text: str) -> str:
    """Script-based detection. Returns an ISO code or 'und' when unsure."""
    if any("ऀ" <= ch <= "ॿ" for ch in text):
        return "hi"
    if any("஀" <= ch <= "௿" for ch in text):
        return "ta"
    if any(ch.isascii() and ch.isalpha() for ch in text):
        return "en"
    return "und"
