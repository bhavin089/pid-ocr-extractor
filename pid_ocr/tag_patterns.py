from __future__ import annotations

import re


PID_NUMBER_PATTERNS = [
    re.compile(r"\bP\s*&\s*ID\s*(?:NO\.?|NUMBER|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9._/\-]{4,})", re.I),
    re.compile(r"\bPID\s*(?:NO\.?|NUMBER|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9._/\-]{4,})", re.I),
    re.compile(r"\bDRAWING\s*(?:NO\.?|NUMBER|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9._/\-]{4,})", re.I),
    re.compile(r"\bDWG\s*(?:NO\.?|NUMBER|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9._/\-]{4,})", re.I),
]

TAG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("line_number", re.compile(r"\b\d{1,2}(?:\"|IN)?[-\s]?[A-Z]{1,4}[-\s]?\d{2,5}(?:[-\s][A-Z0-9]{1,8}){0,4}\b", re.I)),
    ("instrument", re.compile(r"\b(?:[AFJPQTW][A-Z]{0,3}|[LPFTQ][A-Z]{1,3})[-\s]?\d{2,5}[A-Z]?\b")),
    ("control_valve", re.compile(r"\b(?:XV|HV|FV|PV|TV|LV|SV|SDV|MOV|ROV|ESDV)[-\s]?\d{2,5}[A-Z]?\b")),
    ("equipment", re.compile(r"\b(?:P|V|TK|T|E|H|C|R|M|K|F|D|B|AG|MX|PKG)[-\s]?\d{2,5}[A-Z]?\b")),
]

FALSE_POSITIVE_PATTERNS = [
    re.compile(r"^\d+$"),
    re.compile(r"^A\d{2,3}$"),
    re.compile(r"^PID[-\s]?\d+", re.I),
    re.compile(r"^REV[-\s]?\d+$", re.I),
    re.compile(r"^SHEET[-\s]?\d+$", re.I),
]


def normalize_tag(value: str) -> str:
    cleaned = re.sub(r"\s+", "-", value.strip().upper())
    cleaned = cleaned.replace("--", "-")
    return cleaned.strip(".,;:()[]{}")


def is_false_positive(tag: str) -> bool:
    normalized = normalize_tag(tag)
    if len(normalized) < 4 or len(normalized) > 40:
        return True
    return any(pattern.match(normalized) for pattern in FALSE_POSITIVE_PATTERNS)
