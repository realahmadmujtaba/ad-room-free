"""Agent tools. Each one is a real ClickHouse query behind a plain Python function.

ADK reads the signatures and docstrings below to decide when to call them, so the
wording of each docstring is part of the prompt. Edit with that in mind.
"""
import ch
import config


def search_scenes(
    int_ext: str = "",
    time_of_day: str = "",
    set_name: str = "",
    character: str = "",
    element: str = "",
    min_complexity: int = 0,
    limit: int = 50,
) -> dict:
    """Find scenes matching production criteria.

    Args:
        int_ext: "INT", "EXT" or "" for both.
        time_of_day: "DAY", "NIGHT", "DAWN", "DUSK" or "" for any.
        set_name: partial set/location name, case-insensitive. "" for any.
        character: a character who appears in the scene. "" for any.
        element: any prop, vehicle, stunt, animal or piece of equipment
            required by the scene, e.g. "vintage car". "" for any.
        min_complexity: only return scenes at or above this difficulty (1-10). 0 for all.
        limit: maximum scenes to return.

    Returns:
        Matching scenes with their sets, times of day, cast and length.
    """
    where = ["project_id = %(pid)s"]
    params: dict = {"pid": config.DEFAULT_PROJECT, "lim": int(limit)}

    if int_ext:
        where.append("int_ext = %(ie)s")
        params["ie"] = int_ext.upper()
    if time_of_day:
        where.append("time_of_day = %(tod)s")
        params["tod"] = time_of_day.upper()
    if set_name:
        where.append("positionCaseInsensitive(set_name, %(sn)s) > 0")
        params["sn"] = set_name
    if character:
        where.append(
            "arrayExists(x -> positionCaseInsensitive(x, %(ch)s) > 0, cast_members)"
        )
        params["ch"] = character
    if min_complexity:
        where.append("complexity_score >= %(mc)s")
        params["mc"] = int(min_complexity)
    if element:
        where.append(
            "scene_number IN (SELECT scene_number FROM scene_elements "
            "WHERE project_id = %(pid)s AND positionCaseInsensitive(element, %(el)s) > 0)"
        )
        params["el"] = element

    rows = ch.query(
        f"""
        SELECT scene_number, int_ext, time_of_day, set_name, page_eighths,
               complexity_score, cast_members, synopsis
        FROM scenes
        WHERE {' AND '.join(where)}
        ORDER BY toFloat32OrZero(scene_number), scene_number
        LIMIT %(lim)s
        """,
        params,
    )
    return {
        "count": len(rows),
        "total_eighths": sum(r["page_eighths"] for r in rows),
        "scenes": rows,
    }


def element_report(category: str, limit: int = 40) -> dict:
    """List every production element in one category and which scenes need it.

    Use this for questions like "what props do we need" or "list all the vehicles".

    Args:
        category: one of cast, prop, vehicle, wardrobe, makeup_hair, stunt, vfx,
            equipment, animal, minor.
        limit: maximum distinct elements to return.

    Returns:
        Each element with its scene count and the scene numbers that require it.
    """
    rows = ch.query(
        """
        SELECT element,
               count() AS scene_count,
               groupArray(scene_number) AS scene_numbers,
               sum(page_eighths) AS total_eighths
        FROM scene_elements
        WHERE project_id = %(pid)s AND category = %(cat)s
        GROUP BY element
        ORDER BY scene_count DESC
        LIMIT %(lim)s
        """,
        {"pid": config.DEFAULT_PROJECT, "cat": category.lower(), "lim": int(limit)},
    )
    return {"category": category, "distinct_elements": len(rows), "elements": rows}


def day_out_of_days(character: str = "") -> dict:
    """Produce a Day Out of Days report: which scenes and sets each actor works.

    This is the document used to schedule cast and calculate how many days each
    actor must be paid for.

    Args:
        character: a single character name, or "" for the full cast.

    Returns:
        Per character: scene count, total screen length, and the sets they appear on.
    """
    where = ["project_id = %(pid)s", "category = 'cast'"]
    params: dict = {"pid": config.DEFAULT_PROJECT}
    if character:
        where.append("positionCaseInsensitive(element, %(ch)s) > 0")
        params["ch"] = character

    rows = ch.query(
        f"""
        SELECT element AS character,
               count() AS scene_count,
               sum(page_eighths) / 8.0 AS pages,
               groupArray(scene_number) AS scenes,
               arrayDistinct(groupArray(set_name)) AS sets,
               countIf(time_of_day = 'NIGHT') AS night_scenes
        FROM scene_elements
        WHERE {' AND '.join(where)}
        GROUP BY character
        ORDER BY scene_count DESC
        """,
        params,
    )
    return {"cast_size": len(rows), "report": rows}


def build_shooting_schedule(max_eighths_per_day: int = 40) -> dict:
    """Group scenes into shooting days.

    Scenes are banked by set and time of day so the crew lights and moves once,
    then packed into days up to the page limit. Night work is kept on its own days
    because of turnaround rules.

    Args:
        max_eighths_per_day: page eighths schedulable per day. 40 = 5 pages, a
            normal feature day. Lower it for a heavier, more careful schedule.

    Returns:
        An ordered list of shoot days with their set, scenes, cast and page count.
    """
    banks = ch.query(
        """
        SELECT set_name,
               time_of_day,
               groupArray(scene_number) AS scenes,
               sum(page_eighths) AS eighths,
               arrayDistinct(arrayFlatten(groupArray(cast_members))) AS cast_needed,
               max(complexity_score) AS peak_complexity
        FROM scenes
        WHERE project_id = %(pid)s
        GROUP BY set_name, time_of_day
        ORDER BY (time_of_day = 'NIGHT') ASC, eighths DESC
        """,
        {"pid": config.DEFAULT_PROJECT},
    )

    days: list[dict] = []
    current: dict | None = None
    for bank in banks:
        is_night = bank["time_of_day"] == "NIGHT"
        too_full = current and current["eighths"] + bank["eighths"] > max_eighths_per_day
        wrong_shift = current and current["is_night"] != is_night
        if current is None or too_full or wrong_shift:
            current = {
                "day": len(days) + 1,
                "is_night": is_night,
                "unit": "NIGHT UNIT" if is_night else "DAY UNIT",
                "sets": [],
                "scenes": [],
                "cast": set(),
                "eighths": 0,
                "peak_complexity": 0,
            }
            days.append(current)
        current["sets"].append(f"{bank['set_name']} ({bank['time_of_day']})")
        current["scenes"].extend(bank["scenes"])
        current["cast"].update(bank["cast_needed"])
        current["eighths"] += bank["eighths"]
        current["peak_complexity"] = max(current["peak_complexity"], bank["peak_complexity"])

    for day in days:
        day["cast"] = sorted(day.pop("cast"))
        day["pages"] = round(day.pop("eighths") / 8.0, 2)
        day.pop("is_night")

    return {"shoot_days": len(days), "schedule": days}


def flag_production_risks() -> dict:
    """Surface the scenes that will cost money or blow the schedule.

    Checks for night exteriors, stunts, VFX, animals, minors and unusually
    complex scenes, and reports how concentrated each risk is.

    Returns:
        A per-risk breakdown with the scenes involved.
    """
    summary = ch.query(
        """
        SELECT
            countIf(int_ext = 'EXT' AND time_of_day = 'NIGHT') AS night_exteriors,
            countIf(length(stunts) > 0)   AS stunt_scenes,
            countIf(length(vfx) > 0)      AS vfx_scenes,
            countIf(length(animals) > 0)  AS animal_scenes,
            countIf(length(minors) > 0)   AS minor_scenes,
            countIf(complexity_score >= 8) AS high_complexity,
            count() AS total_scenes
        FROM scenes
        WHERE project_id = %(pid)s
        """,
        {"pid": config.DEFAULT_PROJECT},
    )

    detail = ch.query(
        """
        SELECT scene_number, set_name, int_ext, time_of_day, complexity_score,
               stunts, vfx, animals, minors, synopsis
        FROM scenes
        WHERE project_id = %(pid)s
          AND (complexity_score >= 8
               OR length(stunts) > 0
               OR length(animals) > 0
               OR length(minors) > 0
               OR (int_ext = 'EXT' AND time_of_day = 'NIGHT'))
        ORDER BY complexity_score DESC
        LIMIT 25
        """,
        {"pid": config.DEFAULT_PROJECT},
    )
    return {"summary": summary[0] if summary else {}, "flagged_scenes": detail}


def project_overview() -> dict:
    """Get the top-level shape of the loaded screenplay.

    Call this first when the user asks a broad question, so you know the title,
    scene count, page count and the biggest sets before answering.
    """
    stats = ch.query(
        """
        SELECT count() AS scenes,
               round(sum(page_eighths) / 8.0, 1) AS pages,
               countIf(int_ext = 'EXT') AS exteriors,
               countIf(int_ext = 'INT') AS interiors,
               countIf(time_of_day = 'NIGHT') AS night_scenes,
               uniqExact(set_name) AS distinct_sets
        FROM scenes
        WHERE project_id = %(pid)s
        """,
        {"pid": config.DEFAULT_PROJECT},
    )
    top_sets = ch.query(
        """
        SELECT set_name, count() AS scenes, round(sum(page_eighths) / 8.0, 1) AS pages
        FROM scenes
        WHERE project_id = %(pid)s
        GROUP BY set_name
        ORDER BY pages DESC
        LIMIT 10
        """,
        {"pid": config.DEFAULT_PROJECT},
    )
    title = ch.query(
        "SELECT title FROM projects WHERE project_id = %(pid)s ORDER BY ingested_at DESC LIMIT 1",
        {"pid": config.DEFAULT_PROJECT},
    )
    return {
        "title": title[0]["title"] if title else "Untitled",
        "stats": stats[0] if stats else {},
        "biggest_sets": top_sets,
    }


ALL_TOOLS = [
    project_overview,
    search_scenes,
    element_report,
    day_out_of_days,
    build_shooting_schedule,
    flag_production_risks,
]
