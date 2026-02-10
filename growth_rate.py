#!/usr/bin/env python
"""
growth_rate.py
--------------
CLI and Flask API for looking up predicted microbial doubling times
(temperature-corrected) by taxonomic name.

Predictions are from the Phydon database:
  Xu L, Zakem E & Weissman JL (2025) Nature Communications 16:4256.

Usage (CLI):
    python growth_rate.py <query> [--level LEVEL] [--stat STAT]

    Examples:
        python growth_rate.py pseudomonas --genus --median
        python growth_rate.py marmicola --genus --median
        python growth_rate.py enterobacterales --order --mean

    If --level is omitted the tool searches every level.
    If --stat  is omitted the full JSON record is returned.

Usage (API):
    python growth_rate.py --serve [--port 5000]

    GET /growth_rate?query=pseudomonas&level=genus&stat=median
"""

import argparse
import json
import os
import sys

import pandas as pd
from rapidfuzz import fuzz, process

# ── optional Flask import (graceful if missing) ──────────────────────
try:
    from flask import Flask, request, jsonify

    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

CACHE_DIR = "cache"
TAXONOMY_LEVELS = ["domain", "phylum", "class", "order", "family", "genus", "species"]
STAT_CHOICES = ["mean", "median", "min", "max", "range", "std", "se", "count"]

# ── data loading ─────────────────────────────────────────────────────

_cache: dict[str, pd.DataFrame] = {}


def _load_level(level: str) -> pd.DataFrame:
    if level not in _cache:
        path = os.path.join(CACHE_DIR, f"{level}.parquet")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} not found – run build.py first."
            )
        _cache[level] = pd.read_parquet(path)
    return _cache[level]


# ── lookup helpers ───────────────────────────────────────────────────

def _exact_lookup(df: pd.DataFrame, level: str, name: str) -> pd.DataFrame:
    return df[df[level] == name]


def _fuzzy_lookup(df: pd.DataFrame, level: str, name: str, score_cutoff: int = 50):
    """Return (matched_rows, matched_name, score)."""
    candidates = df[level].dropna().unique().tolist()
    result = process.extractOne(name, candidates, scorer=fuzz.WRatio, score_cutoff=score_cutoff)
    if result is None:
        return pd.DataFrame(), None, 0
    matched_name, score, _ = result
    rows = df[df[level] == matched_name]
    return rows, matched_name, score


def _row_to_dict(row: pd.Series, level: str) -> dict:
    """Convert a summary row to a JSON-friendly dict."""
    idx = TAXONOMY_LEVELS.index(level)
    lineage = {lv: row.get(lv, None) for lv in TAXONOMY_LEVELS[: idx + 1]}
    return {
        "lineage": lineage,
        "doubling_time_hours": {
            "mean": round(row["mean"], 4),
            "median": round(row["median"], 4),
            "min": round(row["min"], 4),
            "max": round(row["max"], 4),
            "range": round(row["range"], 4),
            "std": round(row["std"], 4) if pd.notna(row["std"]) else None,
            "se": round(row["se"], 4) if pd.notna(row["se"]) else None,
        },
        "species_count": int(row["count"]),
    }


def _search_all_levels(name: str):
    """Search every level for an exact or fuzzy match; return best."""
    name_lower = name.strip().lower()

    # 1) exact match across all levels
    for level in TAXONOMY_LEVELS:
        df = _load_level(level)
        hits = _exact_lookup(df, level, name_lower)
        if not hits.empty:
            records = [_row_to_dict(r, level) for _, r in hits.iterrows()]
            return {
                "query": name,
                "matched_name": name_lower,
                "matched_level": level,
                "match_score": 100,
                "results": records,
            }

    # 2) fuzzy across all levels – pick best score
    best = None
    for level in TAXONOMY_LEVELS:
        df = _load_level(level)
        rows, matched, score = _fuzzy_lookup(df, level, name_lower)
        if matched and (best is None or score > best[2]):
            best = (level, rows, score, matched)

    if best:
        level, rows, score, matched = best
        records = [_row_to_dict(r, level) for _, r in rows.iterrows()]
        return {
            "query": name,
            "matched_name": matched,
            "matched_level": level,
            "match_score": round(score, 2),
            "results": records,
        }

    return {"query": name, "error": "No match found at any taxonomic level."}


def _search_level(name: str, level: str):
    """Search a specific level; fall back to scanning all levels."""
    name_lower = name.strip().lower()
    level_lower = level.strip().lower()

    if level_lower not in TAXONOMY_LEVELS:
        # Maybe the user's "level" is actually a taxon name – try all.
        return _search_all_levels(name)

    df = _load_level(level_lower)

    # exact
    hits = _exact_lookup(df, level_lower, name_lower)
    if not hits.empty:
        records = [_row_to_dict(r, level_lower) for _, r in hits.iterrows()]
        return {
            "query": name,
            "matched_name": name_lower,
            "matched_level": level_lower,
            "match_score": 100,
            "results": records,
        }

    # fuzzy at requested level
    rows, matched, score = _fuzzy_lookup(df, level_lower, name_lower)
    if matched:
        records = [_row_to_dict(r, level_lower) for _, r in rows.iterrows()]
        return {
            "query": name,
            "matched_name": matched,
            "matched_level": level_lower,
            "match_score": round(score, 2),
            "results": records,
        }

    # fall back: maybe they said --order but it's actually a family, etc.
    fallback = _search_all_levels(name)
    if "error" not in fallback:
        fallback["note"] = (
            f"'{name}' was not found at the '{level_lower}' level. "
            f"Found at '{fallback['matched_level']}' instead."
        )
    return fallback


def lookup(query: str, level: str | None = None, stat: str | None = None):
    if level:
        result = _search_level(query, level)
    else:
        result = _search_all_levels(query)

    # If a specific stat was requested, simplify the output
    if stat and "results" in result:
        stat_lower = stat.strip().lower()
        if stat_lower == "count":
            for r in result["results"]:
                r["value"] = r.pop("species_count")
                del r["doubling_time_hours"]
        elif stat_lower in STAT_CHOICES:
            for r in result["results"]:
                r["value"] = r["doubling_time_hours"].get(stat_lower)
                r["stat"] = stat_lower
                r["unit"] = "hours"
                del r["doubling_time_hours"]
                del r["species_count"]
        result["stat_requested"] = stat_lower

    return result


# ── CLI ──────────────────────────────────────────────────────────────

def _parse_cli():
    parser = argparse.ArgumentParser(
        description="Look up predicted microbial doubling times by taxonomy."
    )
    parser.add_argument("query", nargs="?", help="Taxonomic name to search for.")
    parser.add_argument(
        "--serve", action="store_true", help="Start the Flask API server."
    )
    parser.add_argument("--port", type=int, default=5000, help="Port for API server.")

    # level flags – accept both "--level genus" and "--genus"
    parser.add_argument("--level", choices=TAXONOMY_LEVELS, default=None)
    for lv in TAXONOMY_LEVELS:
        parser.add_argument(f"--{lv}", dest="level_flag", action="store_const", const=lv)

    # stat flags – accept both "--stat median" and "--median"
    parser.add_argument("--stat", choices=STAT_CHOICES, default=None)
    for st in STAT_CHOICES:
        parser.add_argument(f"--{st}", dest="stat_flag", action="store_const", const=st)

    return parser.parse_args()


# ── Flask API ────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)

    @app.route("/growth_rate", methods=["GET"])
    def growth_rate_endpoint():
        query = request.args.get("query")
        if not query:
            return jsonify({"error": "Missing 'query' parameter."}), 400
        level = request.args.get("level", None)
        stat = request.args.get("stat", None)
        result = lookup(query, level=level, stat=stat)
        status = 200 if "error" not in result else 404
        return jsonify(result), status

    @app.route("/levels", methods=["GET"])
    def levels_endpoint():
        return jsonify({"levels": TAXONOMY_LEVELS, "stats": STAT_CHOICES})

    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "service": "Phydon Growth Rate Lookup API",
            "usage": "GET /growth_rate?query=<name>&level=<level>&stat=<stat>",
            "docs": "See README.md",
        })

    return app


# ── main ─────────────────────────────────────────────────────────────

def main():
    args = _parse_cli()

    if args.serve:
        if not HAS_FLASK:
            print("Flask is required for --serve. Install it first.", file=sys.stderr)
            sys.exit(1)
        app = create_app()
        app.run(host="0.0.0.0", port=args.port, debug=True)
        return

    if not args.query:
        print("Error: provide a taxonomic query or --serve.", file=sys.stderr)
        sys.exit(1)

    level = args.level or getattr(args, "level_flag", None)
    stat = args.stat or getattr(args, "stat_flag", None)

    result = lookup(args.query, level=level, stat=stat)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()