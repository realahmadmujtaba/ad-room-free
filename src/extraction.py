"""Screenplay -> structured breakdown, using Gemini's native PDF understanding.

We hand Gemini the raw PDF bytes (no OCR preprocessing) and constrain the output
with a response schema so the result drops straight into ClickHouse.
"""
import json

from google import genai
from google.genai import types

import config
import retry

_client = None


def client() -> genai.Client:
    """Gemini through the free AI Studio endpoint. No billing account needed."""
    global _client
    if _client is None:
        if not config.GOOGLE_API_KEY:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Get a free key at aistudio.google.com/apikey "
                "and put it in .env"
            )
        _client = genai.Client(api_key=config.GOOGLE_API_KEY)
    return _client


SCENE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "scenes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "scene_number": {"type": "STRING"},
                    "page_number": {"type": "NUMBER"},
                    "page_eighths": {"type": "INTEGER"},
                    "int_ext": {"type": "STRING", "enum": ["INT", "EXT", "INT/EXT"]},
                    "time_of_day": {
                        "type": "STRING",
                        "enum": ["DAY", "NIGHT", "DAWN", "DUSK", "CONTINUOUS"],
                    },
                    "location": {"type": "STRING"},
                    "set_name": {"type": "STRING"},
                    "synopsis": {"type": "STRING"},
                    "cast_members": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "background_actors": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "props": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "vehicles": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "wardrobe": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "makeup_hair": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "stunts": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "vfx": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "special_equipment": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "animals": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "minors": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "complexity_score": {"type": "INTEGER"},
                },
                "required": [
                    "scene_number",
                    "int_ext",
                    "time_of_day",
                    "location",
                    "synopsis",
                    "cast_members",
                    "complexity_score",
                ],
            },
        },
    },
    "required": ["title", "scenes"],
}


PROMPT = """You are a First Assistant Director doing a full script breakdown.

Read the attached screenplay and produce one record per scene, in script order.

Rules:
- A new scene starts at each slugline (INT./EXT. LOCATION - TIME).
- `set_name` is the normalised, reusable set: "SARAH'S APARTMENT - KITCHEN" and
  "KITCHEN" in the same apartment are the same set. Grouping shoot days depends on this.
- `page_eighths` is the scene's length in eighths of a page. A full page is 8.
  Estimate it from the amount of action and dialogue.
- `cast_members` are speaking or specifically named characters only. Crowds,
  waiters, and passers-by go in `background_actors`.
- `props` are objects a character handles or that the action calls out. Do not
  list set dressing.
- `stunts` covers fights, falls, chases, driving action. `vfx` covers anything
  needing post work. `special_equipment` covers cranes, drones, underwater rigs,
  steadicam, process trailers.
- `minors` lists any character written as under 18 — these carry legal shoot-hour limits.
- `complexity_score` is 1-10 for how hard the scene is to shoot. Night exteriors,
  stunts, animals, minors, crowds, and VFX all push it up.
- Use the exact character names from the script. Be consistent across scenes.

Return every scene. Do not summarise or skip.
"""


def extract_screenplay(pdf_bytes: bytes, model: str | None = None) -> dict:
    """Return {"title": str, "scenes": [ ... ]} from a screenplay PDF."""
    primary = model or config.MODEL_PRO
    models = [primary]
    if config.MODEL_FALLBACK and config.MODEL_FALLBACK != primary:
        models.append(config.MODEL_FALLBACK)

    response = retry.call_with_model_fallback(
        client().models.generate_content,
        models,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            types.Part.from_text(text=PROMPT),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SCENE_SCHEMA,
            temperature=0.1,
            max_output_tokens=32768,
        ),
    )
    data = json.loads(response.text)
    data.setdefault("scenes", [])
    return data
