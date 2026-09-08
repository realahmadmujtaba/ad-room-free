"""Central config.

Reads from Streamlit secrets when running on Streamlit Community Cloud, and from
environment variables / .env when running locally. Free-tier mode: Gemini is
reached through a Google AI Studio API key, so no billing account is required.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _secrets():
    try:
        import streamlit as st

        return st.secrets
    except Exception:  # not under Streamlit, or no secrets file present
        return {}


_S = _secrets()


def get(name: str, default: str = "") -> str:
    try:
        if name in _S:
            return str(_S[name])
    except Exception:
        pass
    return os.getenv(name, default)


# --- Gemini (free tier via AI Studio) ---
GOOGLE_API_KEY = get("GOOGLE_API_KEY")
MODEL_PRO = get("GEMINI_MODEL_PRO", "gemini-2.5-flash")
MODEL_FLASH = get("GEMINI_MODEL_FLASH", "gemini-2.5-flash")
# Used only when MODEL_PRO exhausts its retries on a 429/503 — a cheaper, lighter
# model draws from a different capacity pool, so it often stays up when the
# primary model is overloaded. See src/retry.py.
MODEL_FALLBACK = get("GEMINI_MODEL_FALLBACK", "gemini-3.5-flash-lite")

# Route the ADK and the genai SDK at the AI Studio endpoint rather than Vertex AI.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
if GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# --- ClickHouse ---
CH_HOST = get("CLICKHOUSE_HOST")
CH_PORT = int(get("CLICKHOUSE_PORT", "8443"))
CH_USER = get("CLICKHOUSE_USER", "default")
CH_PASSWORD = get("CLICKHOUSE_PASSWORD")
CH_DATABASE = get("CLICKHOUSE_DATABASE", "default")

DEFAULT_PROJECT = get("DEMO_PROJECT_ID", "demo_feature")

ELEMENT_CATEGORIES = [
    "cast", "prop", "vehicle", "wardrobe", "makeup_hair",
    "stunt", "vfx", "equipment", "animal", "minor",
]
