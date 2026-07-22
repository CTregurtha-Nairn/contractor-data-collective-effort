# =============================================================================
# config.example.py - Template for local configuration
# Copy this file to config.py and fill in the real values.
# config.py is gitignored and must never be committed.
# =============================================================================

# Biodiversity Contractor Data feature layer (AGOL item).
# Points (weed locations) = layer 1, Tracks (coverage polylines) = layer 2.
BIOD_CONTRACTOR_ITEM_ID = "your-biod-contractor-item-id"
BIOD_POINTS_LAYER_ID = 1
BIOD_TRACKS_LAYER_ID = 2

# Biosecurity Pest Plants Contractor Data feature service (AGOL item) — a separate
# service from the Biodiversity one above (NZTM2000 / wkid 2193, so Shape__Length
# and Shape__Area are real metres). REST layer ids (resolved by id, not list order):
#   0 = Ground Control Points  1 = Ground Control Tracks
#   2 = Aerial Data Points     3 = Aerial Data Tracks  4 = Aerial Data Polygons
BIOS_CONTRACTOR_ITEM_ID = "your-bios-contractor-item-id"
BIOS_GROUND_POINTS_LAYER_ID = 0
BIOS_GROUND_LINES_LAYER_ID = 1
BIOS_AERIAL_POINTS_LAYER_ID = 2
BIOS_AERIAL_LINES_LAYER_ID = 3
BIOS_AERIAL_POLYGONS_LAYER_ID = 4
