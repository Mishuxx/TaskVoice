"""
core/recurrence.py
==================
Recurrence logic and calculation for recurring tasks in Taskmaster.

Features:
- Calculate next occurrence from recurrence days and time.
- Format friendly recurrence badges (e.g., '🔁 Diario 09:00', '🔁 Lun, Mié 18:30').
- Serialization of recurrence days.
"""

from __future__ import annotations

import json
from datetime import datetime, date, timedelta
from typing import Optional, List, Set, Union


WEEKDAY_NAMES_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
WEEKDAY_SHORT_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
WEEKDAY_LETTERS_ES = ["L", "M", "X", "J", "V", "S", "D"]

WEEKDAYS_MON_TO_FRI = [0, 1, 2, 3, 4]
WEEKEND_DAYS = [5, 6]
ALL_DAYS = [0, 1, 2, 3, 4, 5, 6]


def parse_recurrence_days(days_input: Union[str, List[int], None]) -> List[int]:
    """Parse recurrence days from JSON string, comma string or list of ints."""
    if not days_input:
        return list(ALL_DAYS)
    if isinstance(days_input, list):
        return sorted([int(d) for d in days_input if 0 <= int(d) <= 6])
    if isinstance(days_input, str):
        try:
            parsed = json.loads(days_input)
            if isinstance(parsed, list):
                return sorted([int(d) for d in parsed if 0 <= int(d) <= 6])
        except Exception:
            pass
        # Comma-separated fallback
        res = []
        for p in days_input.split(","):
            p = p.strip()
            if p.isdigit():
                val = int(p)
                if 0 <= val <= 6:
                    res.append(val)
        return sorted(res) if res else list(ALL_DAYS)
    return list(ALL_DAYS)


def serialize_recurrence_days(days: List[int]) -> str:
    """Serialize a list of weekday integers (0-6) into a compact JSON string."""
    cleaned = sorted(list(set(int(d) for d in days if 0 <= int(d) <= 6)))
    return json.dumps(cleaned)


def calculate_next_occurrence(
    recurrence_days: Optional[Union[List[int], str]],
    recurrence_time: str = "09:00",
    from_dt: Optional[datetime] = None,
) -> datetime:
    """
    Calculate the next occurrence datetime based on recurrence days and time.
    """
    if from_dt is None:
        from_dt = datetime.now()

    # Parse hour and minute
    try:
        parts = str(recurrence_time).strip().split(":")
        r_hour = int(parts[0])
        r_minute = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= r_hour <= 23 and 0 <= r_minute <= 59):
            r_hour, r_minute = 9, 0
    except Exception:
        r_hour, r_minute = 9, 0

    parsed_days = parse_recurrence_days(recurrence_days)
    target_days = set(parsed_days) if parsed_days else set(ALL_DAYS)

    # Check next 8 days starting today
    for offset in range(8):
        cand_date = from_dt.date() + timedelta(days=offset)
        if cand_date.weekday() in target_days:
            cand_dt = datetime(cand_date.year, cand_date.month, cand_date.day, r_hour, r_minute)
            if offset > 0 or cand_dt > from_dt:
                return cand_dt

    # Fallback to 7 days ahead
    return from_dt + timedelta(days=7)


def format_recurrence_badge(
    recurrence_days: Optional[Union[List[int], str]] = None,
    recurrence_time: str = "09:00",
    recurrence_type: str = "daily",
    is_recurring: bool = True,
) -> str:
    """
    Format a concise HUD label for a task card.
    Examples:
      - '🔁 Diario 09:00'
      - '🔁 Lun-Vie 18:30'
      - '🔁 Lun, Mié 10:00'
    """
    if not is_recurring:
        return ""

    time_str = recurrence_time.strip() if recurrence_time else "09:00"
    days = parse_recurrence_days(recurrence_days)

    if len(days) == 7:
        days_label = "Diario"
    elif days == WEEKDAYS_MON_TO_FRI:
        days_label = "Lun-Vie"
    elif days == WEEKEND_DAYS:
        days_label = "Fin de semana"
    elif len(days) == 1:
        days_label = WEEKDAY_SHORT_ES[days[0]]
    else:
        days_label = ", ".join(WEEKDAY_SHORT_ES[d] for d in days)

    return f"🔁 {days_label} {time_str}"


def extract_recurrence(text: str) -> tuple[str, bool, Optional[List[int]], Optional[str], Optional[str]]:
    """
    Extract recurrence keywords, days and time from a task string.
    Returns: (cleaned_title, is_recurring, recurrence_days, recurrence_time, recurrence_type)
    """
    import re
    cleaned = text
    is_recurring = False
    recurrence_days = None
    recurrence_time = None
    recurrence_type = None

    # 1. Match Time: e.g. "a las 09:30", "a las 8", "a las 18:00 horas"
    time_pat = re.compile(
        r'\b(?:a\s+las?|a\s+la)\s+(\d{1,2})(?::(\d{2}))?\s*(?:horas?|hrs?|hs?)?\b',
        re.IGNORECASE
    )
    m_time = time_pat.search(cleaned)
    if m_time:
        is_recurring = True
        hour = int(m_time.group(1))
        minute = int(m_time.group(2)) if m_time.group(2) else 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            recurrence_time = f"{hour:02d}:{minute:02d}"
        cleaned = time_pat.sub('', cleaned)

    # 2. Daily patterns: "todos los dias", "diario", "diariamente", "cada dia"
    daily_pat = re.compile(
        r'\b(?:todos\s+los\s+d[ií]as|cada\s+d[ií]a|diariamente|diari[ao])\b',
        re.IGNORECASE
    )
    if daily_pat.search(cleaned):
        is_recurring = True
        recurrence_type = "daily"
        recurrence_days = list(ALL_DAYS)
        cleaned = daily_pat.sub('', cleaned)

    # 3. Weekdays patterns: "lunes a viernes", "dias habiles", "dias laborales"
    weekdays_pat = re.compile(
        r'\b(?:de\s+)?lunes\s+a\s+viernes\b|\b(?:d[ií]as\s+h[aá]biles|d[ií]as\s+laborales)\b',
        re.IGNORECASE
    )
    if weekdays_pat.search(cleaned):
        is_recurring = True
        recurrence_type = "weekdays"
        recurrence_days = list(WEEKDAYS_MON_TO_FRI)
        cleaned = weekdays_pat.sub('', cleaned)

    # 4. Weekend pattern
    weekend_pat = re.compile(
        r'\b(?:fines?\s+de\s+semana|s[aá]bados?\s+y\s+domingos?)\b',
        re.IGNORECASE
    )
    if weekend_pat.search(cleaned):
        is_recurring = True
        recurrence_type = "custom"
        recurrence_days = list(WEEKEND_DAYS)
        cleaned = weekend_pat.sub('', cleaned)

    # 5. Specific weekdays pattern
    # e.g. "los lunes y miercoles", "cada martes", "lunes, miercoles y viernes"
    day_map = {
        "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
        "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
    }
    spec_day_pat = re.compile(
        r'\b(?:los|cada)?\s*(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b',
        re.IGNORECASE
    )
    matched_days = []
    for m in spec_day_pat.finditer(cleaned):
        day_word = m.group(1).lower()
        for k, v in day_map.items():
            if k == day_word:
                matched_days.append(v)
                break

    if matched_days and not recurrence_days:
        is_recurring = True
        recurrence_type = "custom"
        recurrence_days = sorted(list(set(matched_days)))
        cleaned = spec_day_pat.sub('', cleaned)

    # 6. General recurrence keywords: "recurrente", "repetir"
    rec_word_pat = re.compile(
        r'\b(?:tarea\s+)?(?:recurrente|repetir)\b',
        re.IGNORECASE
    )
    if rec_word_pat.search(cleaned):
        is_recurring = True
        if not recurrence_type:
            recurrence_type = "daily"
            recurrence_days = list(ALL_DAYS)
        cleaned = rec_word_pat.sub('', cleaned)

    # Clean punctuation, extra whitespace
    cleaned = re.sub(r'[,;:\-]+$', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,;:-')
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]

    if is_recurring and not recurrence_time:
        recurrence_time = "09:00"
    if is_recurring and not recurrence_days:
        recurrence_days = list(ALL_DAYS)
    if is_recurring and not recurrence_type:
        recurrence_type = "daily"

    return cleaned, is_recurring, recurrence_days, recurrence_time, recurrence_type
