"""Map a JSON settings object onto PipelineSettings, filling defaults."""

from __future__ import annotations

from dataclasses import fields

from core.settings import PipelineSettings


class SettingsError(ValueError):
    pass


def settings_from_dict(data: dict | None) -> PipelineSettings:
    allowed = {f.name for f in fields(PipelineSettings)}
    incoming = data or {}
    unknown = set(incoming) - allowed
    if unknown:
        raise SettingsError(f"unknown settings: {', '.join(sorted(unknown))}")
    values = {name: getattr(PipelineSettings(), name) for name in allowed}
    values.update(incoming)
    try:
        return PipelineSettings(**values)
    except TypeError as exc:
        raise SettingsError(str(exc)) from exc
