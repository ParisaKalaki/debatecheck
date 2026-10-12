"""
API key settings: check which keys are set, validate new keys, apply them at runtime,
and optionally save them to the project's .env file.
Used by the /config endpoints so keys can be entered through the web UI.
"""

import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# name -> required?
KEY_FIELDS = {
    "NCBI_EMAIL": True,
    "GOOGLE_API_KEY": True,
    "GROQ_API_KEY": True,
    "NCBI_API_KEY": False,
}


def _is_set(name: str) -> bool:
    value = os.getenv(name, "").strip()
    return bool(value) and not value.startswith("#")


def key_status() -> dict:
    keys = {name: _is_set(name) for name in KEY_FIELDS}
    ready = all(keys[name] for name, required in KEY_FIELDS.items() if required)
    return {"keys": keys, "ready": ready}


def _short_error(exc: Exception) -> str:
    """One-line, readable version of an SDK error (full traceback goes to the backend terminal)."""
    traceback.print_exc()
    text = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {text[:250]}"


def validate_keys(values: dict[str, str]) -> dict[str, str]:
    """Return {key_name: error_message} for any value that fails a quick check."""
    errors = {}

    email = values.get("NCBI_EMAIL")
    if email is not None and ("@" not in email or "." not in email.split("@")[-1]):
        errors["NCBI_EMAIL"] = "Please enter a valid email address."

    google_key = values.get("GOOGLE_API_KEY")
    if google_key:
        try:
            from google import genai
            # Keep a reference: an unreferenced Client can be garbage-collected (closing its
            # HTTP connection) before the request is sent.
            gemini_client = genai.Client(api_key=google_key)
            next(iter(gemini_client.models.list()), None)
        except Exception as exc:
            errors["GOOGLE_API_KEY"] = f"Could not verify this key - {_short_error(exc)}"

    groq_key = values.get("GROQ_API_KEY")
    if groq_key:
        try:
            import groq
            groq_client = groq.Groq(api_key=groq_key)
            groq_client.models.list()
        except Exception as exc:
            errors["GROQ_API_KEY"] = f"Could not verify this key - {_short_error(exc)}"

    return errors


def apply_keys(values: dict[str, str], save_to_env: bool) -> None:
    """Set keys for the running backend, and optionally persist them to .env."""
    for name, value in values.items():
        os.environ[name] = value
    if save_to_env:
        _write_env(values)


def _write_env(values: dict[str, str]) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    remaining = dict(values)
    for i, line in enumerate(lines):
        name = line.split("=", 1)[0].strip()
        if name in remaining:
            lines[i] = f"{name}={remaining.pop(name)}"
    lines += [f"{name}={value}" for name, value in remaining.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")