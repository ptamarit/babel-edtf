# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2024 CERN.
#
# Babel-EDTF is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

"""Localization of Extended Date Time Format (EDTF) level 0 strings."""

import calendar
import re
from datetime import date as date_

from babel import Locale
from babel.dates import LC_TIME, format_date, format_interval, format_skeleton
from dateutil.parser import isoparse
from edtf import Date, EDTFObject, Interval
from edtf import parse_edtf as edtf_parse_edtf
from edtf import struct_time_to_datetime
from edtf.parser.grammar import EDTFParseException, ParseException
from edtf.parser.parser_classes import PRECISION_DAY, PRECISION_MONTH, \
    PRECISION_YEAR

from .version import __version__

BOUND_LOWER = 'lower'
BOUND_UPPER = 'upper'

_isoparse_date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DATE_SKELETON_FORMATS = {
    PRECISION_YEAR: {
        'full': 'y',
        'long': 'y',
        'medium': 'y',
        'short': 'y',
    },
    PRECISION_MONTH: {
        'full': 'yMMMM',
        'long': 'yMMMM',
        'medium': 'yMMM',
        'short': 'yM',
    },
    # Day precision is only used for intervals (not for date or date and time)
    # formatting. This is because the format_skeleton does not format exactly
    # the same way as format_date, and thus we use format_date to ensure all
    # dates look the same independently if they where formatted with
    # format_edtf or format_date.
    PRECISION_DAY: {
        'full': 'EEEEyMMMMd',
        'long': 'yMMMMd',
        'medium': 'yMMMd',
        'short': 'yMd',
    },
}


class EDTFValueError(ValueError):
    """An error for invalid EDTF formatted strings."""


class EDTFTypeError(TypeError):
    """An error for invalid EDTF formatted strings."""


def parse_edtf_level0(edtfstr):
    """Parse EDTF input string."""
    try:
        return parse_edtf(edtfstr)
    except ParseException:
        raise EDTFValueError(
            "The string is not a valid EDTF-formatted string.")


def get_edtf_date_skeleton(precision, format='medium'):
    """Return the date skeleton for a given precision.

    :param precision: the precision to use, one of "year", "month" or "day"
    :param format: the format to use, one of "full", "long", "medium", or
                   "short"
    """
    return DATE_SKELETON_FORMATS[precision][format]


def get_interval_precision(interval):
    """Get the precision for an interval."""
    precisions = [interval.lower.precision, interval.upper.precision]
    for p in [PRECISION_DAY, PRECISION_MONTH, PRECISION_YEAR]:
        if p in precisions:
            return p


def edtf_to_datetime(edtf_date, strict):
    """Convert an EDTF date to a Python date object."""
    if strict == BOUND_LOWER:
        date = edtf_date.lower_strict()
    elif strict == BOUND_UPPER:
        date = edtf_date.upper_strict()
    else:
        raise ValueError("Invalid value for 'strict' parameter.")

    return struct_time_to_datetime(date)


def format_edtf(edtf_level0=None, format='medium', locale=LC_TIME):
    """Format a EDTF level 0 expression.

    The formatting relies on Babel's ``format_skeleton()`` and
    ``format_interval()`` for all the heavy lifting.

    :param edtf_level0: a Date, Interval, or string representing
        and EDTF level 0 expression.
    :param format: one of "full", "long", "medium", or "short", or a custom
                   date/time pattern
    :param locale: a `Locale` object or a locale identifier
    """
    if edtf_level0 is None:
        edtf_level0 = date_.today().isoformat()

    if isinstance(edtf_level0, str):
        edtf_level0 = parse_edtf_level0(edtf_level0)

    # Do we have an EDTFObject (directly or parsed from a string)?
    if not isinstance(edtf_level0, EDTFObject):
        raise EDTFTypeError(
            'You must provide either a EDTF formatted string or an EDTF '
            'object.')

    # Do we have a Date, Interval or DateAndTime?
    if not (isinstance(edtf_level0, Date)
            or isinstance(edtf_level0, Interval)):
        raise EDTFValueError(
            'Only an EDTF level 0 date, date and time or interval is '
            'supported.'
        )

    locale = Locale.parse(locale)

    if isinstance(edtf_level0, Date):
        return _format_edtf0_date(edtf_level0, format, locale, BOUND_LOWER)
    elif isinstance(edtf_level0, Interval):
        return _format_edtf0_interval_naive(edtf_level0, format, locale)


def _format_edtf0_date(edtf_date, format, locale, strict):
    """Format an EDTF level 0 date."""
    # Convert EDTFDate to a python Date
    dt = edtf_to_datetime(edtf_date, strict)

    if edtf_date.precision == PRECISION_DAY:
        # Day precision: use normal date formatter
        return format_date(dt.date(), format=format, locale=locale)
    else:
        # Year or month precision: Use skeleton formatting
        if format in ('full', 'long', 'medium', 'short'):
            skeleton = get_edtf_date_skeleton(edtf_date.precision, format)
        else:
            skeleton = format

        return format_skeleton(
            skeleton, datetime=dt, fuzzy=True, locale=locale)


def _format_edtf0_interval_naive(edtf_interval, format, locale):
    """Format an EDTF level 0 interval."""
    dt_start = edtf_to_datetime(edtf_interval.lower, BOUND_LOWER).date()
    dt_end = edtf_to_datetime(edtf_interval.upper, BOUND_UPPER).date()

    precision = get_interval_precision(edtf_interval)

    # Get skeleton format
    if format in ('full', 'long', 'medium', 'short'):
        skeleton = get_edtf_date_skeleton(precision, format)
    else:
        skeleton = format

    return format_interval(
        dt_start, dt_end, skeleton, fuzzy=True, locale=locale)


def _validate_leap_year(edtf_date):
    """Validate that dates on the 29th of February are on leap years."""
    if isinstance(edtf_date, Date):
        if (
            edtf_date.precision == PRECISION_DAY
            and edtf_date.day == '29'
            and edtf_date.month == '02'
            and not calendar.isleap(int(edtf_date.year))
        ):
            raise EDTFParseException(
                'Day is out of range for month of February on non-leap year.'
            )
    elif isinstance(edtf_date, Interval):
        _validate_leap_year(edtf_date.lower)
        _validate_leap_year(edtf_date.upper)


def parse_edtf(date):
    """parse_edtf after trying isoparse for the simple date format YYYY-MM-DD.

    parse_edtf/pyparsing don't work in a thread safe way and throw
    TypeError randomly on some runs. This function tries to get isoparse first
    and then falls back to parse_edtf
    """
    if len(date) == 10 and _isoparse_date_pattern.match(date):
        try:
            isodate = isoparse(date)
            return Date(
                str(isodate.year),
                str(isodate.month).zfill(2),
                str(isodate.day).zfill(2),
            )
        except Exception:
            pass

    edtf_date = edtf_parse_edtf(date)

    # python-edtf's edtf_parse_edtf uses a grammar that allows days up to 29
    # for the month of February regardless of whether the year is a leap year
    # or not. Here we fail in case we hit this corner case.
    _validate_leap_year(edtf_date)

    return edtf_date
