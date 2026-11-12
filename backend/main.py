"""Backwards-compatible entrypoint so `uvicorn main:app` still works from backend/."""
from secondsense.main import app  # noqa: F401
