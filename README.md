# contractor-data-collective-effort

Embedded HTML chart dashboards for the **Contractor Data Collective Effort**
metrics at Horizons Regional Council. The charts are hosted on GitHub Pages and
embedded (via `<iframe>`) into the Contractor Data Collective Effort ArcGIS
Experience Builder app.

Follows the same pattern as the biod-hub Pressure Management dashboards: a
Python script pulls data from AGOL, builds one `dashboard_data.json`, and pushes
it to GitHub; the static Chart.js pages fetch that JSON at runtime and do all
filtering/aggregation in the browser.

> **Why a separate public repo?** GitHub Pages content is world-readable, and
> the daily-scan tooling that feeds these datasets lives in a *private* repo
> because it exposes internal network storage paths. This repo contains only
> aggregated metrics and an AGOL item ID (in gitignored `config.py`) — nothing
> sensitive — so it is safe to be public, which Pages requires.

## Repo structure

```
contractor-data-collective-effort/
├── Contractor_Dashboard_Export.py     # Builds dashboard_data.json from AGOL, commits + pushes
├── html/
│   └── contractor-data/
│       ├── CD_Infestation_by_AgeClass.html    # Chart — fetches dashboard_data.json at runtime
│       ├── CD_Infestation_by_Species.html     # Chart — fetches dashboard_data.json at runtime
│       ├── CD_Distance_by_Contractor.html     # Chart — fetches dashboard_data.json at runtime
│       └── dashboard_data.json                # Auto-updated by Contractor_Dashboard_Export.py
├── config.example.py        # Template for config.py
├── config.py                # LOCAL ONLY — never committed (gitignored)
├── requirements.txt
├── .gitignore
└── README.md
```

Export logs are written to `Logs/contractor-data/` (gitignored).

## Charts (biodiversity — first set)

| Chart | File | Metric | Source layer |
|---|---|---|---|
| Infestation Size by Age Class | `CD_Infestation_by_AgeClass.html` | sum `Size_of_in` by `Age_class` (A/J/S) | points |
| Infestation Size by Species | `CD_Infestation_by_Species.html` | sum `Size_of_in` by `SpeciesID`, split by `FinYr` | points |
| Distance Covered by Contractor | `CD_Distance_by_Contractor.html` | sum `Distance_Km` by `Cont_name`, split by `FinYr` | tracks |

Each chart has an in-page **Filter** panel (Financial Year, Contractor,
Species/Age Class, Programme, Activity Type as applicable), an **Export PNG**
button, and a "Generated:" timestamp.

Because Experience Builder Embed widgets are sandboxed iframes, these charts
**cannot** be two-way linked to the web map's filter widgets — they are designed
to live on a dedicated **Contractor Data Metrics** page and filter themselves.

## Data source

`Contractor_Dashboard_Export.py` queries the **Biodiversity Contractor Data**
feature layer on AGOL — points (layer 1, weed locations) and tracks (layer 2,
coverage polylines) — trims to the fields the charts need, and writes
`html/contractor-data/dashboard_data.json`.

## Setup

1. Copy `config.example.py` → `config.py` and set:
   - `BIOD_CONTRACTOR_ITEM_ID` — AGOL item ID for the Biodiversity Contractor Data feature layer
   - `BIOD_POINTS_LAYER_ID` — points layer index (default `1`)
   - `BIOD_TRACKS_LAYER_ID` — tracks layer index (default `2`)
2. Run from the ArcGIS Pro Python environment (`arcgispro-py3`), signed in to
   your portal:

   ```
   python Contractor_Dashboard_Export.py
   ```

   The script builds `dashboard_data.json`, then commits and pushes it to GitHub.

## Hosting the embeds (GitHub Pages)

1. **Settings → Pages** → Source: *Deploy from a branch* → Branch `main`, folder `/ (root)` → Save.
2. After the first build the charts are served at:
   - `https://ctregurtha-nairn.github.io/contractor-data-collective-effort/html/contractor-data/CD_Infestation_by_AgeClass.html`
   - `.../CD_Infestation_by_Species.html`
   - `.../CD_Distance_by_Contractor.html`
3. Embed each URL in an Experience Builder **Embed** widget on the Contractor
   Data Metrics page.

## Maintainer

**BioData Information Advisor — Horizons Regional Council**
