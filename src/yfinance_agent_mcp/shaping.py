"""Turn yfinance's pandas output into compact, JSON-safe records that fit a size budget."""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, TypeVar

import numpy as np
import pandas as pd
from pydantic import BaseModel
from pydantic_core import to_json

from yfinance_agent_mcp.models import Envelope

ResponseFormat = Literal["concise", "detailed"]
JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
EnvelopeT = TypeVar("EnvelopeT", bound=Envelope)

# Maximum characters of a tool result's JSON, by response format. Claude Code warns above
# about 10k tokens and caps tool output at 25k tokens (~100k characters).
BUDGETS: dict[ResponseFormat, int] = {"concise": 20_000, "detailed": 80_000}
_WARNING_RESERVE = 400


def budget_for(response_format: ResponseFormat) -> int:
    return BUDGETS[response_format]


def to_json_value(value: object) -> JsonValue:
    """Convert pandas, numpy and datetime values to JSON: missing -> null, times -> UTC ISO."""
    if value is None or value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, dict):
        return {_json_key(k): to_json_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_json_value(v) for v in value]
    if isinstance(value, pd.DataFrame):
        return [to_json_value(row) for row in value.reset_index().to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return to_json_value(value.to_dict())
    if isinstance(value, np.datetime64):
        value = pd.Timestamp(value)
    elif isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        return iso_utc(value)
    if isinstance(value, date):
        return value.isoformat()
    return None if _is_missing(value) else str(value)


def iso_utc(moment: datetime) -> str | None:
    """Render a moment as ``YYYY-MM-DDTHH:MM:SSZ``; naive values are taken as UTC."""
    timestamp = pd.Timestamp(moment)
    if timestamp is pd.NaT:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def snake_case(name: object) -> str:
    """Yahoo labels to JSON keys: 'Surprise(%)' -> 'surprise_pct', 'strongBuy' -> 'strong_buy'."""
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name).replace("%", " pct "))
    return re.sub(r"[^0-9a-z]+", "_", text.strip().lower()).strip("_")


def round_price(value: float | None) -> float | None:
    """Round to 6 significant digits: enough for decisions, short in JSON."""
    return None if value is None else float(f"{value:.6g}")


def truncate_text(text: str | None, max_chars: int) -> str | None:
    """Shorten text to at most ``max_chars`` characters, ending with an ellipsis when cut."""
    if text is None or len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


@dataclass(frozen=True)
class Page:
    """A window of rows from a table, with what is needed to request the next window."""

    records: list[dict[str, JsonValue]]
    total: int
    truncated: bool
    next_offset: int | None


def frame_to_records(
    frame: pd.DataFrame,
    *,
    index_name: str | None = None,
    columns: Sequence[str] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> Page:
    """Rows ``offset`` to ``offset + limit`` as records; the index becomes ``index_name``."""
    selected = frame if columns is None else frame.loc[:, list(columns)]
    total = len(selected)
    end = total if limit is None else min(total, offset + limit)
    window = selected.iloc[offset:end]
    records: list[dict[str, JsonValue]] = []
    for index_value, row in zip(window.index, window.to_dict(orient="records"), strict=True):
        record: dict[str, JsonValue] = {}
        if index_name is not None:
            record[index_name] = to_json_value(index_value)
        record.update({_json_key(k): to_json_value(v) for k, v in row.items()})
        records.append(record)
    truncated = end < total
    return Page(records, total, truncated, end if truncated else None)


def fit_to_budget(result: EnvelopeT, budget: int) -> EnvelopeT:
    """Drop items from the largest lists until the result's JSON is at most ``budget`` chars.

    A last-resort guard: tools cap their rows up front, so this rarely trims anything.
    """
    size = len(result.model_dump_json())
    if size <= budget:
        return result
    target_size = budget - _WARNING_RESERVE
    kept: dict[str, tuple[int, int]] = {}
    while size > target_size:
        candidates = list(_list_fields(result, ""))
        if not candidates:
            break
        largest = max(candidates, key=lambda field: field.size)
        keep_ratio = 1 - (size - target_size) / largest.size
        keep = min(len(largest.items) - 1, max(0, math.floor(len(largest.items) * keep_ratio)))
        setattr(largest.owner, largest.name, largest.items[:keep])
        original = kept.get(largest.path, (len(largest.items), keep))[0]
        kept[largest.path] = (original, keep)
        size = len(result.model_dump_json())
    trimmed = ", ".join(f"{path} kept {k} of {n}" for path, (n, k) in list(kept.items())[:5])
    result.truncated = True
    result.warnings.append(
        f"Trimmed to fit the {budget:,}-character response budget ({trimmed}). "
        "Ask for fewer symbols or rows, or use response_format='detailed'."
    )
    return result


@dataclass(frozen=True)
class _ListField:
    owner: BaseModel
    name: str
    path: str
    items: list[object]
    size: int


def _list_fields(model: BaseModel, prefix: str) -> Iterator[_ListField]:
    """Every non-empty list inside ``model`` (recursively), except the warnings list."""
    for name in type(model).model_fields:
        if name == "warnings":
            continue
        value = getattr(model, name)
        path = f"{prefix}{name}"
        if isinstance(value, list):
            if value:
                yield _ListField(model, name, path, value, len(to_json(value)))
            for position, item in enumerate(value):
                if isinstance(item, BaseModel):
                    yield from _list_fields(item, f"{path}[{position}].")
        elif isinstance(value, BaseModel):
            yield from _list_fields(value, f"{path}.")


def _json_key(key: object) -> str:
    if isinstance(key, str):
        return key
    converted = to_json_value(key)
    return converted if isinstance(converted, str) else str(converted)


def _is_missing(value: object) -> bool:
    try:
        return bool(pd.isna(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
