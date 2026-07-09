"""
Resolves relative date phrases ("next Friday", "tomorrow", "in 3 days") into
real calendar dates using plain Python -- no LLM involved.

Why this exists: LLMs are unreliable at weekday arithmetic (they'll happily
generate a date that "looks right" but land on the wrong day of the week).
Deterministic code never gets this wrong, so date resolution is pulled out
of the agent entirely and done here instead.
"""

import re
from datetime import date, timedelta

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def resolve_relative_date(phrase: str, reference_date: date | None = None) -> str | None:
    """
    Converts a relative date phrase into a YYYY-MM-DD string.
    Returns None if the phrase can't be confidently resolved (caller should
    treat that as still-missing and ask the user for an explicit date).

    reference_date defaults to today; pass it explicitly in tests for
    deterministic, reproducible results.
    """
    if not phrase:
        return None

    reference_date = reference_date or date.today()
    phrase = phrase.strip().lower()

    if phrase in ("today",):
        return reference_date.isoformat()

    if phrase in ("tomorrow",):
        return (reference_date + timedelta(days=1)).isoformat()

    # "in N days"
    match = re.fullmatch(r"in (\d+) days?", phrase)
    if match:
        n = int(match.group(1))
        return (reference_date + timedelta(days=n)).isoformat()

    # "in N weeks"
    match = re.fullmatch(r"in (\d+) weeks?", phrase)
    if match:
        n = int(match.group(1))
        return (reference_date + timedelta(weeks=n)).isoformat()

    # "next <weekday>" -> the occurrence of that weekday in the NEXT week
    # (colloquial reading: skip the rest of this week, go to next week's day)
    match = re.fullmatch(r"next (\w+)", phrase)
    if match and match.group(1) in WEEKDAYS:
        target = WEEKDAYS[match.group(1)]
        days_until = (target - reference_date.weekday() + 7) % 7
        days_until = days_until + 7 if days_until <= 0 else days_until
        # if today IS that weekday, "next X" still means next week's, not today
        if days_until == 0:
            days_until = 7
        return (reference_date + timedelta(days=days_until)).isoformat()

    # "this <weekday>" -> the occurrence of that weekday THIS week (upcoming)
    match = re.fullmatch(r"this (\w+)", phrase)
    if match and match.group(1) in WEEKDAYS:
        target = WEEKDAYS[match.group(1)]
        days_until = (target - reference_date.weekday()) % 7
        return (reference_date + timedelta(days=days_until)).isoformat()

    # bare weekday name, e.g. "friday" -> nearest upcoming occurrence
    if phrase in WEEKDAYS:
        target = WEEKDAYS[phrase]
        days_until = (target - reference_date.weekday()) % 7
        days_until = days_until if days_until != 0 else 7  # today's weekday -> next week
        return (reference_date + timedelta(days=days_until)).isoformat()

    # Unrecognized phrase -- don't guess, let the caller handle it as missing
    return None