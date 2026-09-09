"""ClickHouse access layer.

This is the ClickHouse partner integration. Every agent tool in tools.py reaches
the database through the functions below — nothing here is decorative.
"""
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import clickhouse_connect

import config

SCENE_COLUMNS = [
    "project_id",
    "scene_number",
    "page_number",
    "page_eighths",
    "int_ext",
    "time_of_day",
    "location",
    "set_name",
    "synopsis",
    "cast_members",
    "background_actors",
    "props",
    "vehicles",
    "wardrobe",
    "makeup_hair",
    "stunts",
    "vfx",
    "special_equipment",
    "animals",
    "minors",
    "complexity_score",
    "batch_id",
]

ARRAY_FIELDS = {
    "cast_members": "cast",
    "background_actors": "cast",
    "props": "prop",
    "vehicles": "vehicle",
    "wardrobe": "wardrobe",
    "makeup_hair": "makeup_hair",
    "stunts": "stunt",
    "vfx": "vfx",
    "special_equipment": "equipment",
    "animals": "animal",
    "minors": "minor",
}


@lru_cache(maxsize=1)
def client():
    return clickhouse_connect.get_client(
        host=config.CH_HOST,
        port=config.CH_PORT,
        username=config.CH_USER,
        password=config.CH_PASSWORD,
        database=config.CH_DATABASE,
        secure=True,
    )


def query(sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    """Run a SELECT and return a list of dicts."""
    result = client().query(sql, parameters=params or {})
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


def command(sql: str) -> None:
    client().command(sql)


def init_schema(path: str = "schema.sql") -> None:
    with open(path) as fh:
        raw = fh.read()
    for statement in raw.split(";"):
        lines = [line for line in statement.splitlines() if not line.strip().startswith("--")]
        cleaned = "\n".join(lines).strip()
        if cleaned:
            command(cleaned)


def _row_from_scene(project_id: str, scene: dict, batch_id: str) -> list:
    return [
        project_id,
        str(scene.get("scene_number", "")),
        float(scene.get("page_number", 0) or 0),
        int(scene.get("page_eighths", 0) or 0),
        scene.get("int_ext", "") or "",
        scene.get("time_of_day", "") or "",
        scene.get("location", "") or "",
        scene.get("set_name") or scene.get("location", "") or "",
        scene.get("synopsis", "") or "",
        scene.get("cast_members", []) or [],
        scene.get("background_actors", []) or [],
        scene.get("props", []) or [],
        scene.get("vehicles", []) or [],
        scene.get("wardrobe", []) or [],
        scene.get("makeup_hair", []) or [],
        scene.get("stunts", []) or [],
        scene.get("vfx", []) or [],
        scene.get("special_equipment", []) or [],
        scene.get("animals", []) or [],
        scene.get("minors", []) or [],
        int(scene.get("complexity_score", 1) or 1),
        batch_id,
    ]


def replace_project(project_id: str, title: str, scenes: list[dict]) -> dict:
    """Wipe and reload one screenplay. Idempotent — safe to re-run during a demo.

    ClickHouse's lightweight DELETE runs as an async mutation. Issuing it before
    the INSERT (delete-then-insert) races: the mutation can still be mid-flight
    when the new rows land and sweep them up too, silently leaving the project
    empty. So the new rows are inserted first, tagged with a fresh batch_id, and
    only then are old rows deleted by excluding that batch_id — an identity
    check, not a timestamp comparison, so it can't be fooled by clock skew
    between ClickHouse Cloud's compute replicas either.
    """
    c = client()
    batch_id = str(uuid.uuid4())

    scene_rows = [_row_from_scene(project_id, s, batch_id) for s in scenes]
    if scene_rows:
        c.insert("scenes", scene_rows, column_names=SCENE_COLUMNS)

    element_rows = []
    for scene in scenes:
        for field, category in ARRAY_FIELDS.items():
            for element in scene.get(field, []) or []:
                element_rows.append(
                    [
                        project_id,
                        str(scene.get("scene_number", "")),
                        category,
                        str(element),
                        scene.get("int_ext", "") or "",
                        scene.get("time_of_day", "") or "",
                        scene.get("set_name") or scene.get("location", "") or "",
                        int(scene.get("page_eighths", 0) or 0),
                        batch_id,
                    ]
                )
    if element_rows:
        c.insert(
            "scene_elements",
            element_rows,
            column_names=[
                "project_id",
                "scene_number",
                "category",
                "element",
                "int_ext",
                "time_of_day",
                "set_name",
                "page_eighths",
                "batch_id",
            ],
        )

    c.command(
        "DELETE FROM scenes WHERE project_id = %(p)s AND batch_id != %(batch)s",
        parameters={"p": project_id, "batch": batch_id},
    )
    c.command(
        "DELETE FROM scene_elements WHERE project_id = %(p)s AND batch_id != %(batch)s",
        parameters={"p": project_id, "batch": batch_id},
    )

    total_pages = sum(float(s.get("page_eighths", 0) or 0) for s in scenes) / 8.0
    # ClickHouse dedupes inserts by hashing the client-submitted block. ingested_at
    # is normally a server-side DEFAULT now() and so isn't part of that hash --
    # re-ingesting a project with identical (title, scene_count, total_pages), even
    # long after the original row was deleted, would silently no-op. Passing a real
    # timestamp explicitly keeps every insert's block content unique.
    c.insert(
        "projects",
        [[project_id, title, len(scenes), total_pages, datetime.now(timezone.utc)]],
        column_names=["project_id", "title", "scene_count", "total_pages", "ingested_at"],
    )
    return {"scenes": len(scene_rows), "elements": len(element_rows), "pages": round(total_pages, 1)}
