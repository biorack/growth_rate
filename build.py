#!/usr/bin/env python
"""
build.py
--------
Downloads the Phydon GTDB SSU + OGT prediction CSV, parses taxonomy,
and creates per-taxonomic-level parquet summary files in cache/.

The growth-rate predictions (combopred = predicted minimum doubling
time in hours, temperature-corrected) come directly from:

  Xu L, Zakem E & Weissman JL (2025) "Improved maximum growth rate
  prediction from microbial genomes by integrating phylogenetic
  information." Nature Communications 16:4256.
  https://doi.org/10.1038/s41467-025-59558-9

We simply aggregate their released predictions by GTDB taxonomy.
"""

import os
import urllib.request
import math
import pandas as pd
import numpy as np

RAW_DIR = "raw"
CACHE_DIR = "cache"
CSV_URL = (
    "https://github.com/xl0418/Phydon/releases/download/v1.0.0/"
    "phydon_gtdb_ssu_with_OGT.csv"
)
CSV_FILE = os.path.join(RAW_DIR, "phydon_gtdb_ssu_with_OGT.csv")

TAXONOMY_LEVELS = ["domain", "phylum", "class", "order", "family", "genus", "species"]
TAXONOMY_PREFIXES = ["d__", "p__", "c__", "o__", "f__", "g__", "s__"]


def download_csv():
    os.makedirs(RAW_DIR, exist_ok=True)
    if not os.path.exists(CSV_FILE):
        print(f"Downloading {CSV_URL} ...")
        urllib.request.urlretrieve(CSV_URL, CSV_FILE)
        print("Done.")
    else:
        print(f"{CSV_FILE} already exists, skipping download.")


def parse_taxonomy(df: pd.DataFrame) -> pd.DataFrame:
    """Split the semicolon-delimited GTDB taxonomy string into columns."""
    parts = df["taxonomy"].str.split(";", expand=True)
    for i, level in enumerate(TAXONOMY_LEVELS):
        if i < parts.shape[1]:
            # strip the prefix (e.g. "d__") and lowercase
            df[level] = (
                parts[i]
                .str.replace(TAXONOMY_PREFIXES[i], "", regex=False)
                .str.strip()
                .str.lower()
            )
        else:
            df[level] = np.nan
    return df


def summarise_level(df: pd.DataFrame, level: str) -> pd.DataFrame:
    """Group by the given taxonomic level and compute summary stats on combopred."""
    # Build the grouping key: all levels from domain down to `level`
    idx = TAXONOMY_LEVELS.index(level)
    group_cols = TAXONOMY_LEVELS[: idx + 1]

    grouped = df.dropna(subset=[level, "combopred"]).groupby(group_cols)

    agg = grouped["combopred"].agg(
        mean="mean",
        median="median",
        min="min",
        max="max",
        std="std",
        count="count",
    )
    agg["range"] = agg["max"] - agg["min"]
    agg["se"] = agg["std"] / np.sqrt(agg["count"])
    agg = agg.reset_index()
    return agg


def main():
    download_csv()

    print("Reading CSV …")
    df = pd.read_csv(CSV_FILE)

    print("Parsing taxonomy …")
    df = parse_taxonomy(df)

    os.makedirs(CACHE_DIR, exist_ok=True)

    for level in TAXONOMY_LEVELS:
        print(f"  Summarising at {level} level …")
        summary = summarise_level(df, level)
        out = os.path.join(CACHE_DIR, f"{level}.parquet")
        summary.to_parquet(out, index=False)
        print(f"    → {out}  ({len(summary)} rows)")

    print("\nBuild complete.")


if __name__ == "__main__":
    main()