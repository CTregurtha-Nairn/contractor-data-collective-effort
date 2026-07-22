"""
BioSecurity_Dashboard_Export.py
===============================
Builds the data feed for the embedded Biosecurity Pest Plants metrics dashboard.

This is the pest-plant sibling of Contractor_Dashboard_Export.py. It queries the
``Biosecurity_Pest_Plants_Contractor_Data`` feature service on AGOL — a SEPARATE
service from the Biodiversity contractor data — and writes a single
``bios_dashboard_data.json`` into ``html/contractor-data/``. The static Chart.js
page fetches that JSON at runtime and does all filtering/aggregation in-browser.

Five layers are pulled (resolved by their REST layer id):
    0  Ground Control Points   1  Ground Control Tracks
    2  Aerial Data Points      3  Aerial Data Tracks    4  Aerial Data Polygons

The service is in NZTM2000 (wkid 2193, metres), so any ``Shape__Length`` /
``Shape__Area`` values are real metres / m² (no web-mercator distortion).

Because the contractor layers' exact field names aren't known ahead of time, the
export is FIELD-ADAPTIVE: it keeps every real attribute on each layer, dropping
only system / geometry / editor-tracking noise. Two conveniences are added per
record:
  * ``FinYear`` is normalised to ``FinYr`` so every record speaks one year field.
  * A canonical ``SpeciesID`` (the 3-letter code) and readable ``SpeciesName`` are
    attached, resolved from bios_species_lookup.json if that file is present.

Usage (ArcGIS Pro Python environment — arcgispro-py3):
    python BioSecurity_Dashboard_Export.py

You must be signed in to ArcGIS Pro with your portal credentials first
(the script authenticates with GIS("pro")).

Configuration:
    Copy config.example.py -> config.py and set the BIOS_* keys.
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
        "and fill in the BIOS_* keys."
    )

ITEM_ID = getattr(config, "BIOS_CONTRACTOR_ITEM_ID", None)
if not ITEM_ID or ITEM_ID == "your-bios-contractor-item-id":
    sys.exit("ERROR: BIOS_CONTRACTOR_ITEM_ID is not set in config.py.")

# (layer_id, bucket_name, control_tag) — layer ids matched on layer.properties.id.
LAYERS = [
    (getattr(config, "BIOS_GROUND_POINTS_LAYER_ID", 0),  "ground_points",   "ground"),
    (getattr(config, "BIOS_GROUND_LINES_LAYER_ID", 1),   "ground_lines",    "ground"),
    (getattr(config, "BIOS_AERIAL_POINTS_LAYER_ID", 2),  "aerial_points",   "aerial"),
    (getattr(config, "BIOS_AERIAL_LINES_LAYER_ID", 3),   "aerial_lines",    "aerial"),
    (getattr(config, "BIOS_AERIAL_POLYGONS_LAYER_ID", 4),"aerial_polygons", "aerial"),
]

# System / geometry / editor-tracking fields we never want in the feed. The
# coverage measures Shape__Length / Shape__Area are deliberately NOT dropped.
DROP_FIELDS = {
    "SHAPE", "Shape", "geometry", "OBJECTID", "objectid", "GlobalID", "GLOBALID",
    "Creator", "Editor", "CreationDate", "EditDate",
    "created_user", "created_date", "last_edited_user", "last_edited_date",
}
# Names that (case-insensitively) contain any of these get numeric coercion.
NUMERIC_HINTS = ("size", "length", "area", "count", "distance", "km",
                 "extent", "number", "occupancy")
# Candidate field names that hold the 3-letter species code.
SPECIES_CODE_FIELDS = ("SpeciesID", "specieID", "SpeciesCode", "Species_ID",
                        "SpeciesId", "Species", "species")

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR    = os.path.join(SCRIPT_DIR, "html", "contractor-data")
JSON_OUT   = os.path.join(OUT_DIR, "bios_dashboard_data.json")
JSON_REL   = "html/contractor-data/bios_dashboard_data.json"  # path for git add
LOOKUP     = os.path.join(SCRIPT_DIR, "bios_species_lookup.json")  # code -> name
os.makedirs(OUT_DIR, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(SCRIPT_DIR, "Logs", "contractor-data")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, dt.now().strftime("%Y-%m-%d_%H-%M-%S") + "_bios_export.log")

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


# ── AGOL helpers ──────────────────────────────────────────────────────────────
def connect_gis() -> GIS:
    log.info("Connecting to ArcGIS Online...")
    gis = GIS("pro")
    log.info(f"Connected as: {gis.properties.user.username}")
    return gis


def get_layer_by_rest_id(item, rest_id: int):
    """Return the item's layer whose service (REST) id == rest_id."""
    for lyr in item.layers:
        if int(lyr.properties.id) == int(rest_id):
            return lyr
    available = [(int(l.properties.id), l.properties.name) for l in item.layers]
    raise IndexError(
        f"REST layer id {rest_id} not found on item {item.id}. Available: {available}"
    )


def fetch_layer_records(item, rest_id: int, species_map: dict) -> list:
    """Query a layer and return clean records with all real attributes kept."""
    layer = get_layer_by_rest_id(item, rest_id)
    log.info(f"Querying layer {rest_id} ({layer.properties.name})...")
    fset = layer.query(where="1=1", out_fields="*", return_geometry=False)
    df = fset.sdf
    log.info(f"  -> {len(df):,} records returned")

    if "FinYear" in df.columns and "FinYr" not in df.columns:
        df = df.rename(columns={"FinYear": "FinYr"})

    keep = [c for c in df.columns if c not in DROP_FIELDS]
    out = df[keep].copy()
    log.info(f"  kept fields: {list(out.columns)}")

    for col in out.columns:
        low = col.lower()
        if any(h in low for h in NUMERIC_HINTS):
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].apply(lambda v: v.strip() if isinstance(v, str) else v)

    records = json.loads(out.to_json(orient="records"))

    # Canonical species code + readable name.
    code_field = next((f for f in SPECIES_CODE_FIELDS if f in out.columns), None)
    if code_field:
        for r in records:
            code = r.get(code_field)
            if code is not None and str(code).strip():
                code = str(code).strip()
                r["SpeciesID"] = code
                r["SpeciesName"] = species_map.get(code, code) if species_map else code
    else:
        log.warning(f"  No species code field found on layer {rest_id}.")
    return records


def load_species_lookup() -> dict:
    """code -> name map from bios_species_lookup.json ({"AFG": "African ..."})."""
    if not os.path.exists(LOOKUP):
        log.warning("No bios_species_lookup.json found — species will show as codes.")
        return {}
    with open(LOOKUP, "r", encoding="utf-8") as f:
        data = json.load(f)
    log.info(f"Loaded species lookup with {len(data):,} codes.")
    return {str(k).strip(): str(v).strip() for k, v in data.items()}


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 70)
    log.info("Starting Biosecurity Pest Plants dashboard export")
    log.info("=" * 70)

    gis = connect_gis()
    item = gis.content.get(ITEM_ID)
    if item is None:
        sys.exit(f"ERROR: could not find AGOL item {ITEM_ID}.")
    log.info(f"Item: {item.title}")

    species_map = load_species_lookup()

    generated_at = dt.now().strftime("%d %B %Y %H:%M")
    payload = {"generated_at": generated_at, "has_species_names": bool(species_map)}
    for rest_id, bucket, control in LAYERS:
        records = fetch_layer_records(item, rest_id, species_map)
        for r in records:
            r["_control"] = control
        payload[bucket] = records
        log.info(f"  {bucket:16s}: {len(records):,} records")

    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    log.info(f"Written: {JSON_OUT}")

    # ── Git commit & push ─────────────────────────────────────────────────────
    log.info("Committing and pushing bios_dashboard_data.json to GitHub...")
    try:
        subprocess.run(["git", "-C", SCRIPT_DIR, "add", JSON_REL], check=True)
        result = subprocess.run(
            ["git", "-C", SCRIPT_DIR, "commit", "-m",
             f"Update biosecurity pest plants dashboard data ({generated_at})"],
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
    log.info(f"  bios_dashboard_data.json : {JSON_OUT}")
    log.info(f"  Generated at             : {generated_at}")
    log.info(f"  Log                      : {log_file}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
