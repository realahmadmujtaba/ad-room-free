-- Script Breakdown Agent — ClickHouse schema
-- Run once against your ClickHouse Cloud service:  python scripts/init_db.py

CREATE TABLE IF NOT EXISTS scenes
(
    project_id        String,
    scene_number      String,
    page_number       Float32,
    page_eighths      UInt16,              -- scene length in 1/8ths of a page (industry standard)
    int_ext           LowCardinality(String),   -- INT | EXT | INT/EXT
    time_of_day       LowCardinality(String),   -- DAY | NIGHT | DAWN | DUSK | CONTINUOUS
    location          String,              -- the slugline location
    set_name          String,              -- normalised set, used for grouping shoot days
    synopsis          String,
    cast_members      Array(String),
    background_actors Array(String),
    props             Array(String),
    vehicles          Array(String),
    wardrobe          Array(String),
    makeup_hair       Array(String),
    stunts            Array(String),
    vfx               Array(String),
    special_equipment Array(String),
    animals           Array(String),
    minors            Array(String),
    complexity_score  UInt8,               -- 1..10, model-estimated shoot difficulty
    ingested_at       DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (project_id, scene_number);


-- Flattened element table. One row per (scene, category, element).
-- Makes "which scenes need the vintage car" a single fast lookup instead of an array scan.
CREATE TABLE IF NOT EXISTS scene_elements
(
    project_id   String,
    scene_number String,
    category     LowCardinality(String),   -- cast | prop | vehicle | wardrobe | stunt | vfx | equipment | animal | minor
    element      String,
    int_ext      LowCardinality(String),
    time_of_day  LowCardinality(String),
    set_name     String,
    page_eighths UInt16
)
ENGINE = MergeTree
ORDER BY (project_id, category, element);


-- Registry of ingested screenplays.
CREATE TABLE IF NOT EXISTS projects
(
    project_id   String,
    title        String,
    scene_count  UInt32,
    total_pages  Float32,
    ingested_at  DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY project_id;
