"""Turn pipeline dataclasses into JSON-safe dicts (NaN/Inf become null)."""

from __future__ import annotations

import math
from dataclasses import asdict, is_dataclass
from typing import Any


def jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value
