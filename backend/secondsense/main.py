"""ASGI entrypoint: `uvicorn secondsense.main:app`."""
from dotenv import load_dotenv

load_dotenv()

from .api import create_app  # noqa: E402  (env must be loaded first)

app = create_app()
