"""Create the ClickHouse tables and load a small demo screenplay.

    python scripts/init_db.py          # schema only
    python scripts/init_db.py --seed   # schema + demo data

Always run --seed before recording your video. A pre-loaded project means the
demo never depends on an upload finishing on camera.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ch  # noqa: E402
import config  # noqa: E402

DEMO_SCENES = [
    {
        "scene_number": "1", "page_number": 1, "page_eighths": 12,
        "int_ext": "EXT", "time_of_day": "NIGHT",
        "location": "COASTAL HIGHWAY", "set_name": "COASTAL HIGHWAY",
        "synopsis": "MARA outruns a black sedan along the cliff road. The sedan clips her bumper.",
        "cast_members": ["MARA", "DRIVER"], "background_actors": [],
        "props": ["burner phone"], "vehicles": ["1972 Chevelle", "black sedan"],
        "wardrobe": ["leather jacket"], "makeup_hair": ["cut lip"],
        "stunts": ["car chase", "PIT manoeuvre"], "vfx": ["muzzle flash"],
        "special_equipment": ["process trailer", "crane"], "animals": [], "minors": [],
        "complexity_score": 9,
    },
    {
        "scene_number": "2", "page_number": 3, "page_eighths": 20,
        "int_ext": "INT", "time_of_day": "NIGHT",
        "location": "DINER", "set_name": "ROADSIDE DINER",
        "synopsis": "Mara meets HOLLIS. He slides an envelope across the formica.",
        "cast_members": ["MARA", "HOLLIS"], "background_actors": ["trucker", "waitress"],
        "props": ["manila envelope", "coffee cup", "burner phone"], "vehicles": [],
        "wardrobe": ["leather jacket"], "makeup_hair": ["cut lip"],
        "stunts": [], "vfx": [], "special_equipment": [], "animals": [], "minors": [],
        "complexity_score": 3,
    },
    {
        "scene_number": "3", "page_number": 6, "page_eighths": 16,
        "int_ext": "INT", "time_of_day": "DAY",
        "location": "DINER", "set_name": "ROADSIDE DINER",
        "synopsis": "Morning after. Mara reads the file. TESS, 11, watches from the counter.",
        "cast_members": ["MARA", "TESS"], "background_actors": ["waitress"],
        "props": ["case file", "coffee cup"], "vehicles": [],
        "wardrobe": ["school uniform"], "makeup_hair": [],
        "stunts": [], "vfx": [], "special_equipment": [], "animals": [],
        "minors": ["TESS"], "complexity_score": 4,
    },
    {
        "scene_number": "4", "page_number": 8, "page_eighths": 8,
        "int_ext": "EXT", "time_of_day": "DAY",
        "location": "DINER PARKING LOT", "set_name": "ROADSIDE DINER",
        "synopsis": "Hollis finds the Chevelle stripped. A stray dog circles the wreck.",
        "cast_members": ["HOLLIS"], "background_actors": [],
        "props": [], "vehicles": ["1972 Chevelle"], "wardrobe": [], "makeup_hair": [],
        "stunts": [], "vfx": [], "special_equipment": [], "animals": ["stray dog"],
        "minors": [], "complexity_score": 5,
    },
    {
        "scene_number": "5", "page_number": 9, "page_eighths": 24,
        "int_ext": "INT", "time_of_day": "DAY",
        "location": "PRECINCT BULLPEN", "set_name": "PRECINCT",
        "synopsis": "Mara is dressed down by CAPT. REYES in front of the whole squad.",
        "cast_members": ["MARA", "REYES"], "background_actors": ["detectives"],
        "props": ["case file", "badge"], "vehicles": [], "wardrobe": ["dress blues"],
        "makeup_hair": [], "stunts": [], "vfx": [], "special_equipment": [],
        "animals": [], "minors": [], "complexity_score": 2,
    },
    {
        "scene_number": "6", "page_number": 12, "page_eighths": 18,
        "int_ext": "EXT", "time_of_day": "NIGHT",
        "location": "CLIFF OVERLOOK", "set_name": "COASTAL HIGHWAY",
        "synopsis": "The sedan returns. Mara goes over the rail and catches the ledge.",
        "cast_members": ["MARA", "DRIVER"], "background_actors": [],
        "props": ["burner phone"], "vehicles": ["black sedan"],
        "wardrobe": ["leather jacket"], "makeup_hair": ["blood"],
        "stunts": ["high fall", "wire work"], "vfx": ["set extension"],
        "special_equipment": ["crane", "condor lights"], "animals": [], "minors": [],
        "complexity_score": 10,
    },
    {
        "scene_number": "7", "page_number": 15, "page_eighths": 10,
        "int_ext": "INT", "time_of_day": "DAY",
        "location": "PRECINCT EVIDENCE ROOM", "set_name": "PRECINCT",
        "synopsis": "Tess slips in and lifts the envelope from the shelf.",
        "cast_members": ["TESS"], "background_actors": [],
        "props": ["manila envelope", "evidence tags"], "vehicles": [],
        "wardrobe": ["school uniform"], "makeup_hair": [], "stunts": [], "vfx": [],
        "special_equipment": [], "animals": [], "minors": ["TESS"],
        "complexity_score": 3,
    },
]


def main() -> None:
    print("Creating tables…")
    ch.init_schema(str(Path(__file__).resolve().parents[1] / "schema.sql"))
    print("Schema ready.")

    if "--seed" in sys.argv:
        stats = ch.replace_project(config.DEFAULT_PROJECT, "NIGHT WORK", DEMO_SCENES)
        print(f"Seeded {stats['scenes']} scenes / {stats['elements']} elements "
              f"/ {stats['pages']} pages into project '{config.DEFAULT_PROJECT}'.")


if __name__ == "__main__":
    main()
