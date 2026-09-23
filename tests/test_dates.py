"""Tests for the calendar rules in app.dates."""

from datetime import date

import pytest

from app.dates import (
    falls_on,
    month_day_error,
    next_occurrence,
    observed_month_day,
    occurrence_in_year,
)


class TestMonthDayValidation:
    @pytest.mark.parametrize(
        "month,day",
        [
            (1, 31),
            (2, 28),
            (2, 29),  # real: leap-day birthdays must be storable
            (4, 30),
            (12, 31),
        ],
    )
    def test_real_dates_accepted(self, month, day):
        assert month_day_error(month, day) is None

    @pytest.mark.parametrize(
        "month,day",
        [
            (2, 30),
            (2, 31),
            (4, 31),
            (6, 31),
            (9, 31),
            (11, 31),
        ],
    )
    def test_impossible_dates_rejected(self, month, day):
        error = month_day_error(month, day)
        assert error is not None
        assert str(day) in error

    def test_missing_day_is_allowed(self):
        """Entries may record only a month."""
        assert month_day_error(3, None) is None

    def test_error_names_the_month(self):
        assert "April" in month_day_error(4, 31)


class TestLeapDay:
    def test_feb_29_stays_put_in_a_leap_year(self):
        assert observed_month_day(2, 29, 2028) == (2, 29)

    def test_feb_29_observed_on_feb_28_otherwise(self):
        assert observed_month_day(2, 29, 2026) == (2, 28)

    def test_other_dates_never_move(self):
        assert observed_month_day(7, 4, 2026) == (7, 4)
        assert observed_month_day(2, 28, 2026) == (2, 28)

    def test_occurrence_in_year_does_not_raise_for_feb_29(self):
        """date(2026, 2, 29) raises; this must not."""
        assert occurrence_in_year(2, 29, 2026) == date(2026, 2, 28)
        assert occurrence_in_year(2, 29, 2028) == date(2028, 2, 29)


class TestFallsOn:
    def test_leap_day_birthday_is_found_in_a_non_leap_year(self):
        """The bug: comparing month/day directly skipped it silently."""
        assert falls_on(2, 29, date(2026, 2, 28)) is True

    def test_leap_day_birthday_is_found_in_a_leap_year(self):
        assert falls_on(2, 29, date(2028, 2, 29)) is True

    def test_leap_day_birthday_does_not_also_fire_on_feb_28_in_a_leap_year(self):
        """In a leap year the real date exists, so it must not double up."""
        assert falls_on(2, 29, date(2028, 2, 28)) is False

    def test_ordinary_feb_28_birthday_still_matches(self):
        assert falls_on(2, 28, date(2026, 2, 28)) is True
        assert falls_on(2, 28, date(2028, 2, 28)) is True

    def test_entry_without_a_day_never_matches(self):
        assert falls_on(5, None, date(2026, 5, 1)) is False

    def test_a_leap_day_birthday_is_reminded_every_year(self):
        """Four consecutive years, none skipped -- the point of the fix."""
        observed = [
            next((d for d in _february(year) if falls_on(2, 29, d)), None)
            for year in (2025, 2026, 2027, 2028)
        ]
        assert observed == [
            date(2025, 2, 28),
            date(2026, 2, 28),
            date(2027, 2, 28),
            date(2028, 2, 29),
        ]


class TestNextOccurrence:
    def test_later_this_year(self):
        assert next_occurrence(6, 15, date(2026, 1, 1)) == date(2026, 6, 15)

    def test_today_counts_as_next(self):
        assert next_occurrence(6, 15, date(2026, 6, 15)) == date(2026, 6, 15)

    def test_rolls_into_next_year_once_past(self):
        assert next_occurrence(6, 15, date(2026, 7, 1)) == date(2027, 6, 15)

    def test_leap_day_from_a_non_leap_year(self):
        assert next_occurrence(2, 29, date(2026, 1, 1)) == date(2026, 2, 28)

    def test_leap_day_rolls_to_the_real_date_in_a_leap_year(self):
        assert next_occurrence(2, 29, date(2028, 1, 1)) == date(2028, 2, 29)


def _february(year):
    """Every day in February of `year`."""
    day = date(year, 2, 1)
    while day.month == 2:
        yield day
        day = date.fromordinal(day.toordinal() + 1)
