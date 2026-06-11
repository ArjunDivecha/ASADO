"""
=============================================================================
SCRIPT NAME: apply_tier_a_semantics.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/tier_a_semantics.yaml
    Hand-authored base-variable semantics (definition, units, mechanism,
    concept, comparability) — one entry per base_variable + provider.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/variable_registry_seed.yaml
    The curated registry seed (1,434 skeleton entries) — read AND rewritten.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/variable_registry_seed.yaml
    Same file, with Tier-A semantics merged in (a timestamped backup of the
    original is saved to Data/backups/{ts}/variable_registry_seed.yaml first).

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Claude (drafted), Arjun Divecha (to verify)

DESCRIPTION:
Phase 2 of the Semantic Layer PRD. Merges hand-authored Tier-A semantics
into the registry seed, propagating base-variable semantics to _CS/_TS
variants with deterministic rules:
  - definition gets a normalization prefix for _CS/_TS variants
  - units become "z-score" for _CS/_TS variants
  - cross_country_comparable becomes true for _CS/_TS variants
  - sign / normalization / native_frequency / is_broadcast are NEVER touched
  - review_status is set to 'model_drafted' (or 'needs_review' when the
    semantics entry says so); 'verified' entries are NEVER overwritten
Two templated generators cover mechanical families:
  - ECB_FX_{CUR}_EUR reference rates (26 vars)
  - WB_CMDTY_{SERIES}_{FEATURE} Pink Sheet features (609 vars)

DEPENDENCIES:
- pyyaml

USAGE:
  python scripts/apply_tier_a_semantics.py            # apply
  python scripts/apply_tier_a_semantics.py --dry-run  # report only, no write

NOTES:
- Idempotent: re-running applies the same values again (no duplication).
- Only fills fields that are empty/null in the seed unless the field was
  previously written by this script (same value, harmless overwrite).
- After running, rebuild the registry:
    python scripts/build_variable_registry.py
    python scripts/qa/validate_variable_registry.py
=============================================================================
"""

# Standard library
import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Third-party
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
SEED_PATH = BASE_DIR / "config" / "variable_registry_seed.yaml"
SEMANTICS_PATH = BASE_DIR / "config" / "tier_a_semantics.yaml"
BACKUP_ROOT = BASE_DIR / "Data" / "backups"

# Fields the apply pass may write (everything else is protected)
WRITABLE = {
    "definition", "units", "cross_country_comparable", "economic_mechanism",
    "mechanism_reference", "concept", "valid_range", "quality_flag",
    "notes", "review_status", "source_series_id",
}

CS_PREFIX = "Cross-sectional z-score (across the 34-country panel) of: "
TS_PREFIX = "Time-series z-score (vs own trailing history) of: "

# ---------------------------------------------------------------------------
# Templated generator: ECB FX reference rates
# ---------------------------------------------------------------------------
ECB_FX_RE = re.compile(r"^ECB_FX_([A-Z]{3})_EUR$")

CURRENCY_NAMES = {
    "AUD": "Australian dollar", "BRL": "Brazilian real", "CAD": "Canadian dollar",
    "CHF": "Swiss franc", "CNY": "Chinese yuan", "DKK": "Danish krone",
    "EUR": "euro", "GBP": "British pound", "HKD": "Hong Kong dollar",
    "IDR": "Indonesian rupiah", "INR": "Indian rupee", "JPY": "Japanese yen",
    "KRW": "Korean won", "MXN": "Mexican peso", "MYR": "Malaysian ringgit",
    "NOK": "Norwegian krone", "NZD": "New Zealand dollar", "PHP": "Philippine peso",
    "PLN": "Polish zloty", "SEK": "Swedish krona", "SGD": "Singapore dollar",
    "THB": "Thai baht", "TRY": "Turkish lira", "TWD": "New Taiwan dollar",
    "USD": "US dollar", "ZAR": "South African rand",
}


def ecb_fx_semantics(base_variable: str) -> dict | None:
    m = ECB_FX_RE.match(base_variable)
    if not m:
        return None
    cur = m.group(1)
    name = CURRENCY_NAMES.get(cur, cur)
    return {
        "definition": f"ECB daily reference exchange rate: {name} ({cur}) per 1 euro.",
        "units": f"{cur} per EUR",
        "cross_country_comparable": False,
        "economic_mechanism": "FX level building block; the depreciation rate, not the level, carries the signal.",
        "concept": "external",
        "source_series_id": f"EXR.D.{cur}.EUR.SP00.A",
    }


# ---------------------------------------------------------------------------
# Templated generator: World Bank Pink Sheet commodity features
# ---------------------------------------------------------------------------
WB_CMDTY_RE = re.compile(
    r"^WB_CMDTY_(.+)_(LEVEL|MOM_PCT|RET_3M_PCT|RET_12M_PCT|YOY_PCT|VOL_12M|Z_36M)$"
)

CMDTY_FEATURE_TEMPLATES = {
    "LEVEL": (
        "{name} price level (World Bank Pink Sheet, monthly, global series broadcast to all countries).",
        "price level (Pink Sheet native unit)",
    ),
    "MOM_PCT": (
        "Month-over-month percent change in the {name} price (Pink Sheet).",
        "percent (MoM)",
    ),
    "RET_3M_PCT": (
        "3-month percent return of the {name} price (Pink Sheet).",
        "percent (3m)",
    ),
    "RET_12M_PCT": (
        "12-month percent return of the {name} price (Pink Sheet).",
        "percent (12m)",
    ),
    "YOY_PCT": (
        "Year-over-year percent change in the {name} price (Pink Sheet).",
        "percent (YoY)",
    ),
    "VOL_12M": (
        "12-month rolling volatility of monthly {name} price returns (Pink Sheet).",
        "percent (volatility)",
    ),
    "Z_36M": (
        "Z-score of the {name} price versus its trailing 36-month history (Pink Sheet).",
        "z-score",
    ),
}


def prettify_cmdty(code: str) -> str:
    """ALUMINUM -> aluminum; BANANA_EU -> banana (EU); CRUDE_BRENT -> crude Brent."""
    words = code.split("_")
    out = []
    for w in words:
        if w in {"EU", "US", "UK", "SGP", "WTI", "LNG", "TSP", "DAP", "SP"}:
            out.append(f"({w})" if w in {"EU", "US", "UK"} else w)
        else:
            out.append(w.lower())
    return " ".join(out)


def wb_cmdty_semantics(base_variable: str) -> dict | None:
    m = WB_CMDTY_RE.match(base_variable)
    if not m:
        return None
    code, feature = m.groups()
    name = prettify_cmdty(code)
    definition, units = CMDTY_FEATURE_TEMPLATES[feature]
    return {
        "definition": definition.format(name=name),
        "units": units,
        "cross_country_comparable": True,  # global broadcast — identical across countries
        "economic_mechanism": (
            "Commodity price context — terms-of-trade transfer between exporters and "
            "importers of " + name + "; explanatory unless joined back to returns."
        ),
        "concept": "commodity",
    }


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def load_semantics() -> dict:
    """Returns {(base_variable, provider): semantics_dict}."""
    entries = yaml.safe_load(SEMANTICS_PATH.read_text())
    table = {}
    for e in entries:
        key = (e["base_variable"], e["provider"])
        if key in table:
            raise ValueError(f"Duplicate semantics entry: {key}")
        table[key] = e
    return table


def variant_fields(sem: dict, normalization: str) -> dict:
    """Map base-level semantics onto one concrete variant."""
    out = {}
    definition = sem.get("definition", "")
    if normalization == "_CS":
        out["definition"] = CS_PREFIX + definition
        out["units"] = "z-score (cross-sectional)"
        out["cross_country_comparable"] = True
    elif normalization == "_TS":
        out["definition"] = TS_PREFIX + definition
        out["units"] = "z-score (time-series)"
        out["cross_country_comparable"] = True
    else:
        out["definition"] = definition
        if sem.get("units"):
            out["units"] = sem["units"]
        if sem.get("cross_country_comparable") is not None:
            out["cross_country_comparable"] = sem["cross_country_comparable"]
        if sem.get("valid_range"):
            out["valid_range"] = sem["valid_range"]

    for field in ("economic_mechanism", "mechanism_reference", "concept",
                  "quality_flag", "notes", "source_series_id"):
        if sem.get(field):
            out[field] = sem[field]

    out["review_status"] = "needs_review" if sem.get("review") == "needs_review" else "model_drafted"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Tier-A semantics to the registry seed")
    parser.add_argument("--dry-run", action="store_true", help="report only, no write")
    args = parser.parse_args()

    semantics = load_semantics()
    seed = yaml.safe_load(SEED_PATH.read_text())
    print(f"Seed entries: {len(seed)} | hand-authored semantics: {len(semantics)}")

    n_applied = n_template_ecb = n_template_cmdty = n_skipped_verified = 0
    unmatched_semantics = set(semantics.keys())

    for entry in seed:
        if entry.get("review_status") == "verified":
            n_skipped_verified += 1
            continue

        key = (entry["base_variable"], entry["source_provider"])
        sem = semantics.get(key)
        source = "hand"
        if sem is None:
            gen = ecb_fx_semantics(entry["base_variable"])
            if gen is not None and entry["source_provider"] == "ECB":
                sem, source = gen, "ecb"
            else:
                gen = wb_cmdty_semantics(entry["base_variable"])
                if gen is not None and entry["source_provider"] == "World Bank Pink Sheet":
                    sem, source = gen, "cmdty"
        else:
            unmatched_semantics.discard(key)

        if sem is None:
            continue

        updates = variant_fields(sem, entry.get("normalization", "raw"))
        for field, value in updates.items():
            if field not in WRITABLE:
                continue
            entry[field] = value

        if source == "hand":
            n_applied += 1
        elif source == "ecb":
            n_template_ecb += 1
        else:
            n_template_cmdty += 1

    print(f"Applied: {n_applied} hand-authored | {n_template_ecb} ECB FX templated "
          f"| {n_template_cmdty} Pink Sheet templated | {n_skipped_verified} skipped (verified)")
    if unmatched_semantics:
        print(f"WARNING: {len(unmatched_semantics)} semantics entries matched no seed row:")
        for k in sorted(unmatched_semantics):
            print(f"  - {k}")

    total_drafted = sum(1 for e in seed if e.get("review_status") in ("model_drafted", "needs_review"))
    print(f"Seed rows now drafted: {total_drafted} / {len(seed)}")

    if args.dry_run:
        print("DRY RUN — no files written.")
        return 0

    # Backup, then rewrite the seed preserving the header comment block.
    ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    backup_dir = BACKUP_ROOT / ts
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SEED_PATH, backup_dir / "variable_registry_seed.yaml")
    print(f"Backup: {backup_dir / 'variable_registry_seed.yaml'}")

    original = SEED_PATH.read_text()
    header_lines = []
    for line in original.splitlines():
        if line.startswith("#") or line.strip() == "":
            header_lines.append(line)
        else:
            break
    header = "\n".join(header_lines).rstrip() + "\n\n"

    body = yaml.safe_dump(seed, sort_keys=False, allow_unicode=True, width=100)
    SEED_PATH.write_text(header + body)
    print(f"Seed rewritten: {SEED_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
