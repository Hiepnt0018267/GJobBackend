"""Lossless professional CV dates; interval endpoints are validation only."""
import calendar
import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

DATE_CONTRACT_VERSION = "cv-date-precision-v2-source-evidence"


class PartialDate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=1, le=9999, strict=True)
    month: int | None = Field(default=None, ge=1, le=12, strict=True)
    day: int | None = Field(default=None, ge=1, le=31, strict=True)
    precision: Literal["year", "month", "day", "ambiguous"]

    @model_validator(mode="after")
    def validate_precision(self):
        if self.precision == "year" and (self.month is not None or self.day is not None):
            raise ValueError("year precision must omit month and day")
        if self.precision == "month" and (self.month is None or self.day is not None):
            raise ValueError("month precision requires month and omits day")
        if self.precision == "day":
            if self.month is None or self.day is None:
                raise ValueError("day precision requires month and day")
            date(self.year, self.month, self.day)
        if self.precision == "ambiguous":
            if self.day is not None and self.month is None:
                raise ValueError("day evidence requires month evidence")
            if self.month is not None and self.day is not None:
                date(self.year, self.month, self.day)
        return self

    def interval(self) -> tuple[date, date]:
        if self.precision in ("year", "ambiguous"):
            return date(self.year, 1, 1), date(self.year, 12, 31)
        month = self.month
        if self.precision == "month":
            return date(self.year, month, 1), date(self.year, month, calendar.monthrange(self.year, month)[1])
        value = date(self.year, month, self.day)
        return value, value


_MONTHS = {name.casefold(): index for index in range(1, 13)
           for name in (calendar.month_name[index], calendar.month_abbr[index])}


def parse_partial_date(value):
    """Normalize exact partial strings only; invalid/unknown inputs stay invalid."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if re.fullmatch(r"[0-9]{4}", text):
        return {"year": int(text), "precision": "year"}
    match = re.fullmatch(r"([0-9]{4})-([0-9]{1,2})", text)
    if match:
        year, month = map(int, match.groups())
        return {"year": year, "month": month, "precision": "month"}
    match = re.fullmatch(r"([0-9]{1,2})/([0-9]{4})", text)
    if match:
        month, year = map(int, match.groups())
        return {"year": year, "month": month, "precision": "month"}
    match = re.fullmatch(r"([A-Za-z]+)\.?\s+([0-9]{4})", text)
    if match and match[1].casefold() in _MONTHS:
        return {"year": int(match[2]), "month": _MONTHS[match[1].casefold()], "precision": "month"}
    return value


class OpenEndedDate(BaseModel):
    """Source-backed Current, never converted to today's date or null."""
    model_config = ConfigDict(extra="forbid")
    state: Literal["current"]


CVDate = Annotated[date | PartialDate | OpenEndedDate, BeforeValidator(parse_partial_date)]


def definitely_reversed(start: date | PartialDate | OpenEndedDate | None, end: date | PartialDate | OpenEndedDate | None) -> bool:
    if isinstance(start, OpenEndedDate):
        raise ValueError("start date cannot be open ended")
    if isinstance(end, OpenEndedDate):
        return False
    if start is None or end is None:
        return False
    earliest_start = start.interval()[0] if isinstance(start, PartialDate) else start
    latest_end = end.interval()[1] if isinstance(end, PartialDate) else end
    return earliest_start > latest_end
