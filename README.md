# Phydon Growth Rate Lookup API

A lightweight taxonomic lookup service for **predicted microbial maximum growth rates** (minimum doubling times, in hours, temperature-corrected).

**This project does NOT generate its own growth rate predictions.** All predicted doubling times served by this API come directly from the dataset released by:

> **Xu L, Zakem E & Weissman JL (2025)**
> *"Improved maximum growth rate prediction from microbial genomes by integrating phylogenetic information."*
> *Nature Communications* 16:4256.
> [https://doi.org/10.1038/s41467-025-59558-9](https://doi.org/10.1038/s41467-025-59558-9)

The predictions were generated using **Phydon**, an R package that combines codon usage bias (via gRodon) with phylogenetic information to estimate temperature-corrected maximum growth rates for 111,034 microbial species in GTDB v220. The underlying data file is hosted at the [Phydon GitHub repository](https://github.com/xl0418/Phydon).

**This project is simply a taxonomic API wrapper** that:
1. Downloads the Phydon prediction CSV.
2. Parses GTDB taxonomy strings and aggregates predictions at each taxonomic level (domain → species).
3. Provides command-line and REST API access with fuzzy name matching for convenience.

If you use growth rate values obtained through this service in a publication, **please cite the original Phydon paper above**, not this wrapper.

---

## Setup

```bash
conda env create -f environment.yml
conda activate growth-rate-api
```

## Step 1: Build the Cache

```bash
python build.py
```

This will:
- Download `phydon_gtdb_ssu_with_OGT.csv` into `raw/`.
- Parse taxonomy and compute summary statistics (mean, median, min, max, range, std, se, count) on `combopred` (predicted minimum doubling time in hours) at each taxonomic level.
- Save parquet files into `cache/` (one per level: `domain.parquet`, `phylum.parquet`, … `species.parquet`).

---

## Command Line Examples

The CLI supports flexible lookups with optional level and stat flags. Fuzzy matching handles typos and partial names automatically.

### Basic lookups

```bash
# Full stats for a genus
python growth_rate.py pseudomonas --genus

# Just the median doubling time for a genus
python growth_rate.py pseudomonas --genus --median

# Mean doubling time for an order
python growth_rate.py enterobacterales --order --mean

# Full stats for a phylum
python growth_rate.py cyanobacteria --phylum
```

### Fuzzy matching

```bash
# Misspelled name — fuzzy matching finds the closest genus
python growth_rate.py marmicola --genus --median

# Partial or approximate name
python growth_rate.py clostridi --genus --mean
```

### Auto-detect taxonomic level

```bash
# Don't know the rank? Leave off the level flag and all levels are searched
python growth_rate.py pseudomonas --median

# Works with any rank
python growth_rate.py bacillota --mean
```

### Level fallback

```bash
# Asked for --order but "enterobacteriaceae_a" is actually a family —
# the tool finds it anyway and tells you where it matched
python growth_rate.py enterobacteriaceae_a --order --mean
```

### Example output

```json
{
  "query": "pseudomonas",
  "matched_name": "pseudomonas",
  "matched_level": "genus",
  "match_score": 100,
  "stat_requested": "median",
  "results": [
    {
      "lineage": {
        "domain": "bacteria",
        "phylum": "pseudomonadota",
        "class": "gammaproteobacteria",
        "order": "pseudomonadales",
        "family": "pseudomonadaceae",
        "genus": "pseudomonas"
      },
      "value": 3.1234,
      "stat": "median",
      "unit": "hours"
    }
  ]
}
```

When a fuzzy match is used, the `match_score` will be less than 100. If the level was wrong, a `note` field explains where the match was actually found:

```json
{
  "query": "enterobacteriaceae_a",
  "matched_name": "enterobacteriaceae_a",
  "matched_level": "family",
  "match_score": 100,
  "note": "'enterobacteriaceae_a' was not found at the 'order' level. Found at 'family' instead.",
  "stat_requested": "mean",
  "results": [ ... ]
}
```

---

## API Examples

### Start the server

```bash
# Development mode
python growth_rate.py --serve --port 5000

# Production mode (via gunicorn)
./run_api_server.sh
```

### Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Service info |
| `GET /levels` | List available taxonomic levels and stats |
| `GET /growth_rate` | Query growth rate predictions |

### Query parameters for `/growth_rate`

| Parameter | Required | Description |
|---|---|---|
| `query` | yes | Taxonomic name to search for |
| `level` | no | Taxonomic level: `domain`, `phylum`, `class`, `order`, `family`, `genus`, `species` |
| `stat` | no | Statistic to return: `mean`, `median`, `min`, `max`, `range`, `std`, `se`, `count` |

### curl examples

```bash
# Median doubling time for a genus
curl "http://localhost:5000/growth_rate?query=pseudomonas&level=genus&stat=median"

# Full stats for an order
curl "http://localhost:5000/growth_rate?query=enterobacterales&level=order"

# Fuzzy match with typo
curl "http://localhost:5000/growth_rate?query=marmicola&level=genus&stat=median"

# Auto-detect level
curl "http://localhost:5000/growth_rate?query=cyanobacteria&stat=mean"

# List available levels and stats
curl "http://localhost:5000/levels"
```

### Python requests examples

```python
import requests

base = "http://localhost:5000"

# Simple lookup
r = requests.get(f"{base}/growth_rate", params={
    "query": "pseudomonas",
    "level": "genus",
    "stat": "median"
})
print(r.json())

# Fuzzy match
r = requests.get(f"{base}/growth_rate", params={
    "query": "marmicola",
    "level": "genus"
})
data = r.json()
print(f"Matched: {data['matched_name']} (score: {data['match_score']})")
print(data["results"])

# Batch lookups
genera = ["pseudomonas", "escherichia", "bacillus", "streptomyces"]
for g in genera:
    r = requests.get(f"{base}/growth_rate", params={
        "query": g, "level": "genus", "stat": "median"
    })
    result = r.json()
    value = result["results"][0]["value"]
    print(f"{g}: {value} hours")
```

---

## What the Numbers Mean

The `combopred` value from the Phydon database is the **predicted minimum doubling time in hours** — i.e., how fast the organism can grow under optimal conditions, corrected for optimal growth temperature. Lower values = faster growers. These are predictions, not direct measurements. See the Phydon paper for details on accuracy, variance, and appropriate interpretation.

## Project Structure

```
├── environment.yml       # Conda environment
├── build.py              # Downloads data, builds parquet cache
├── growth_rate.py        # CLI + Flask API
├── run_api_server.sh     # Production gunicorn launch script
├── README.md
├── LICENSE
├── .gitignore
├── raw/                  # Downloaded CSV (created by build.py)
│   └── phydon_gtdb_ssu_with_OGT.csv
└── cache/                # Parquet summaries (created by build.py)
    ├── domain.parquet
    ├── phylum.parquet
    ├── class.parquet
    ├── order.parquet
    ├── family.parquet
    ├── genus.parquet
    └── species.parquet
```

## License

The Phydon prediction data is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) as part of the original publication. This wrapper code is released under the [MIT License](LICENSE).