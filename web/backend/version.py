"""Single app version string (also shown in the web UI and /health)."""

from pathlib import Path

_FALLBACK = "0.0.0-dev"


def app_version() -> str:
    here = Path(__file__).resolve()
    for candidate in (
        here.parents[2] / "VERSION",  # repo root when running from source
        here.parents[1] / "VERSION",  # /app/VERSION in the Docker image
        Path("/app/VERSION"),
    ):
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return _FALLBACK
