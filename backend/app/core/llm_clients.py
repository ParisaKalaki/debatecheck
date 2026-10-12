"""
Shared, lazily-created API clients.

Clients are created the first time they are needed, using whatever key is in the
environment at that moment. This means:
- the backend can start even when keys are missing (so the UI can ask for them), and
- keys entered through the UI take effect immediately, without a restart.
"""

import os
from functools import lru_cache

import groq
from dotenv import load_dotenv
from google import genai

from app.core.settings import ENV_PATH

load_dotenv(dotenv_path=ENV_PATH)


class MissingAPIKeyError(RuntimeError):
    """Raised when a required API key has not been set."""


@lru_cache(maxsize=4)
def _gemini_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


@lru_cache(maxsize=4)
def _groq_client(api_key: str) -> groq.Groq:
    return groq.Groq(api_key=api_key)


def get_gemini_client() -> genai.Client:
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        raise MissingAPIKeyError("GOOGLE_API_KEY is not set")
    return _gemini_client(key)


def get_groq_client() -> groq.Groq:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise MissingAPIKeyError("GROQ_API_KEY is not set")
    return _groq_client(key)