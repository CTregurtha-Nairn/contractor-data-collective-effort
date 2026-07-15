"""
Contractor_Dashboard_Export.py
==============================
Builds the data feed for the embedded Contractor Data Metrics dashboards.

Queries the Biodiversity Contractor Data feature layer on AGOL (points +
tracks), trims it to the fields the charts need, and writes a single
``dashboard_data.json`` into ``html/contractor-data/``. The static Chart.js
HTML files fetch that JSON at runtime and do all filtering/aggregation in the
browser, so the charts never need regenerating.

The JSON is then committed and pushed to GitHub so GitHub Pages serves the
updated data to the Experience Builder embeds.

This mirrors the Pressure Management workflow in the biod-hub repo
(PM_Dashboard_Export.py): pull data -> build one JSON -> commit -> push.

Usage (ArcGIS Pro Python environment — arcgispro-py3):
    python Contractor_Dashboard_Export.py

You must be signed in to ArcGIS Pro with your portal credentials first
(the script authenticates with GIS("pro")).

Configuration:
    Copy config.example.py -> config.py and set the BIOD_CONTRACTOR_* keys.
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime as dt

import pandas as pd
from arcgis.gis import GIS

# ── Config ────────────────────────────────────────────────────────────────────
try:
    import config
except ImportError:
    sys.exit(
        "ERROR: config.py not found. Copy config.example.py to config.py "
        "and fill in the BIOD_CONTRACTOR_* keys."
    )

BIOD_CONTRACTOR_ITEM_ID = getattr(config, "BIOD_CONTRACTOR_ITEM_ID", None)
BIOD_POINTS_LAYER_ID    = getattr(config, "BIOD_POINTS_LAYER_ID", 1)
BIOD_TRACKS_LAYER_ID    = getattr(config, "BIOD_TRACKS_LAYER_ID", 2)

if not BIOD_CONTRACTOR_ITEM_ID:
    sys.exit("ERROR: BIOD_CONTRACTOR_ITEM_ID is not set in config.py.")

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR    = os.path.join(SCRIPT_DIR, "html", "contractor-data")
JSON_OUT   = os.path.join(OUT_DIR, "dashboard_data.json")
JSON_REL   = "html/contractor-data/dashboard_data.json"  # path for git add
os.makedirs(OUT_DIR, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(SCRIPT_DIR, "Logs", "contractor-data")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, dt.now().strftime("%Y-%m-%d_%H-%M-%S") + "_export.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Fields the charts need (kept small so the JSON stays lean) ─────────────────
POINT_FIELDS = [
    "Cont_name", "SiteID", "SiteName", "FinYr",
    "SpeciesID", "Age_class", "Size_of_in",
    "ProgrammeType", "ActivityType",
]
TRACK_FIELDS = [
    "Cont_name", "SiteID", "SiteName", "FinYr",
    "Distance_Km", "ProgrammeType", "ActivityType",
]


# ── AGOL helpers ──────────────────────────────────────────────────────────────
def connect_gis() -> GIS:
    log.info("Connecting to ArcGIS Online...")
    gis = GIS("pro")
    log.info(f"Connected as: {gis.properties.user.username}")
    return gis


def fetch_layer_as_df(gis: GIS, item_id: str, layer_id: int) -> pd.DataFrame:
    item = gis.content.get(item_id)
    if item is None:
        raise ValueError(f"Could not find AGOL item {item_id}.")
    if layer_id >= len(item.layers):
        available = [(i, lyr.properties.name) for i, lyr in enumerate(item.layers)]
        raise IndexError(
            f"Layer index {layer_id} not found on item {item_id}. "
            f"Available layers: {available}"
        )
    layer = item.layers[layer_id]
    log.info(f"Querying layer {layer_id} ({layer.properties.name})...")
    fset = layer.query(where="1=1", out_fields="*", return_geometry=False)
    df = fset.sdf
    log.info(f"  -> {len(df):,} records returned")
    return df


def trim_records(df: pd.DataFrame, fields: list) -> list:
    """Keep only the requested fields (those that exist) and return clean records."""
    keep = [f for f in fields if f in df.columns]
    missing = [f for f in fields if f not in df.columns]
    if missing:
        log.warning(f"  Fields not found on layer (skipped): {missing}")
    out = df[keep].copy()

    # Normalise types so JSON is tidy: strip strings, numeric size/distance.
    for col in ("Size_of_in", "Distance_Km"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].apply(lambda v: v.strip() if isinstance(v, str) else v)

    # to_json -> loads round-trip so NaN becomes null cleanly.
    return json.loads(out.to_json(orient="records"))


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 70)
    log.info("Starting Contractor Data dashboard export")
    log.info("=" * 70)

    gis = connect_gis()

    points_df = fetch_layer_as_df(gis, BIOD_CONTRACTOR_ITEM_ID, BIOD_POINTS_LAYER_ID)
    tracks_df = fetch_layer_as_df(gis, BIOD_CONTRACTOR_ITEM_ID, BIOD_TRACKS_LAYER_ID)

    points = trim_records(points_df, POINT_FIELDS)
    tracks = trim_records(tracks_df, TRACK_FIELDS)

    generated_at = dt.now().strftime("%d %B %Y %H:%M")
    payload = {
        "generated_at": generated_at,
        "points": points,
        "tracks": tracks,
    }

    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    log.info(f"Written: {JSON_OUT}")
    log.info(f"  points records : {len(points):,}")
    log.info(f"  tracks records : {len(tracks):,}")

    # ── Git commit & push ─────────────────────────────────────────────────────
    log.info("Committing and pushing dashboard_data.json to GitHub...")
    try:
        subprocess.run(["git", "-C", SCRIPT_DIR, "add", JSON_REL], check=True)
        result = subprocess.run(
            ["git", "-C", SCRIPT_DIR, "commit", "-m",
             f"Update contractor data dashboard data ({generated_at})"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            log.info(f"Committed: {result.stdout.strip()}")
            subprocess.run(["git", "-C", SCRIPT_DIR, "push", "origin", "main"], check=True)
            log.info("Pushed to GitHub successfully.")
        else:
            log.info("No changes to commit — dashboard data is already up to date.")
    except subprocess.CalledProcessError as e:
        log.error(f"Git operation failed: {e}")
        raise

    log.info("=" * 70)
    log.info("EXPORT COMPLETE")
    log.info(f"  dashboard_data.json : {JSON_OUT}")
    log.info(f"  Generated at        : {generated_at}")
    log.info(f"  Log                 : {log_file}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
