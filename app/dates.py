"""Calendar rules for birthdays.

Two problems live here, both caused by treating a (month, day) pair as if it
were always a real date:

1. month and day were validated independently -- 1..12 and 1..31 -- so
   February 31 and April 31 were accepted. Such an entry can never match a
   real day, so it never produces a reminder, and building a datetime from it
   raises.

2. February 29 exists only in leap years. Matching a birthday by
   ``month == today.month and day == today.day`` therefore skips leap-day
   birthdays in three years out of four -- silently, with no error and no
   email, which is the worst way for a reminder to fail.

The rule adopted here: **in a non-leap year a February 29 birthday is observed
on February 28**, so the reminder still arrives within the birth month. To
observe it on March 1 instead, change LEAP_DAY_OBSERVED below; everything else
follows from it.
"""

import calendar
from datetime import date
from typing import Optional, Tuple

# February is 29 here on purpose: leap-day birthdays are real and must be
# storable. This table is about which (month, day) pairs can exist at all, not
# about any particular year.
DAYS_IN_MONTH = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

LEAP_DAY = (2, 29)
LEAP_DAY_OBSERVED = (2, 28)


def month_day_error(month: Optional[int], day: Optional[int]) -> Optional[str]:
    """Return a human-readable reason the pair is not a real date, else None.

    A missing day is allowed: entries may record only the month.
    """
    if month is None or day is None:
        return None

    if not 1 <= month <= 12:
        return f"Month must be between 1 and 12, got {month}"

    limit = DAYS_IN_MONTH[month - 1]
    if day < 1 or day > limit:
        return (
            f"{MONTH_NAMES[month - 1]} has {limit} days at most, so day {day} "
            "is not a real date"
        )

    return None


def observed_month_day(month: int, day: int, year: int) -> Tuple[int, int]:
    """Where a birthday actually falls in a given year.

    Only February 29 moves, and only in a non-leap year.
    """
    if (month, day) == LEAP_DAY and not calendar.isleap(year):
        return LEAP_DAY_OBSERVED
    return (month, day)


def falls_on(month: Optional[int], day: Optional[int], on_date: date) -> bool:
    """Does a birthday fall on `on_date`?

    Entries without a day never match -- there is no day to remind about.
    """
    if month is None or day is None:
        return False
    return observed_month_day(month, day, on_date.year) == (
        on_date.month,
        on_date.day,
    )


def occurrence_in_year(month: int, day: int, year: int) -> date:
    """The date this birthday is observed on in `year`.

    Use this instead of date(year, month, day), which raises for February 29
    in a non-leap year.
    """
    observed_month, observed_day = observed_month_day(month, day, year)
    return date(year, observed_month, observed_day)


def next_occurrence(month: int, day: int, today: date) -> date:
    """The next date on or after `today` that this birthday is observed on."""
    this_year = occurrence_in_year(month, day, today.year)
    if this_year >= today:
        return this_year
    return occurrence_in_year(month, day, today.year + 1)
