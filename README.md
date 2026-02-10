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