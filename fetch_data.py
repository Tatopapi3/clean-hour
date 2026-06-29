"""
fetch_data.py
Pulls hourly electricity generation by fuel type for California (CAISO)
from the EIA Open Data API and saves it to data/ca_hourly.json
"""

import requests
import json
import os
from datetime import datetime, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY   = os.environ.get("EIA_API_KEY", "YOUR_API_KEY_HERE")
REGION    = "CAL"   # California CAISO
DAYS_BACK = 14      # 2 weeks of hourly data
OUT_DIR   = "data"
OUT_FILE  = os.path.join(OUT_DIR, "ca_hourly.json")

# Carbon intensity factors (kg CO2 per MWh) by fuel type
# Source: EIA / IPCC lifecycle estimates
CARBON_FACTORS = {
    "NG":    450,   # Natural gas
    "COL":   1000,  # Coal
    "OIL":   700,   # Oil / petroleum
    "NUC":   12,    # Nuclear
    "WAT":   4,     # Hydro
    "WND":   11,    # Wind
    "SUN":   48,    # Solar (utility)
    "GEO":   38,    # Geothermal
    "BIO":   230,   # Biomass
    "OTH":   300,   # Other (conservative estimate)
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_date_range():
    end   = datetime.utcnow()
    start = end - timedelta(days=DAYS_BACK)
    return start.strftime("%Y-%m-%dT%H"), end.strftime("%Y-%m-%dT%H")


def fetch_generation_by_fuel():
    """Pull hourly net generation by fuel type for CAISO."""
    start, end = get_date_range()
    url = "https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/"
    params = {
        "api_key":          API_KEY,
        "frequency":        "hourly",
        "data[0]":          "value",
        "facets[respondent][]": REGION,
        "start":            start,
        "end":              end,
        "sort[0][column]":  "period",
        "sort[0][direction]": "asc",
        "offset":           0,
        "length":           5000,
    }

    print(f"Fetching EIA data for {REGION} from {start} to {end}...")
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rows = data.get("response", {}).get("data", [])
    print(f"  ✓ {len(rows)} rows returned")
    return rows


def compute_carbon_intensity(rows):
    """
    Group rows by hour and compute weighted carbon intensity.
    Returns list of dicts: { period, total_mwh, carbon_intensity, fuel_mix }
    """
    from collections import defaultdict

    # Group by period (hour)
    by_hour = defaultdict(dict)
    for row in rows:
        period   = row.get("period", "")
        fueltype = row.get("fueltype", "OTH")
        value    = float(row.get("value") or 0)
        by_hour[period][fueltype] = value

    results = []
    for period in sorted(by_hour.keys()):
        fuel_mix  = by_hour[period]
        total_mwh = sum(max(v, 0) for v in fuel_mix.values())

        if total_mwh == 0:
            continue

        # Weighted average carbon intensity
        carbon_intensity = sum(
            max(mwh, 0) * CARBON_FACTORS.get(fuel, 300)
            for fuel, mwh in fuel_mix.items()
        ) / total_mwh

        # Parse hour of day (0-23) from period string e.g. "2024-06-15T14"
        try:
            hour = int(period.split("T")[1].split(":")[0])
        except Exception:
            hour = -1

        results.append({
            "period":           period,
            "hour":             hour,
            "total_mwh":        round(total_mwh, 1),
            "carbon_intensity": round(carbon_intensity, 1),
            "fuel_mix":         {k: round(v, 1) for k, v in fuel_mix.items()},
        })

    return results


def save(data):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump({
            "region":     REGION,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "days_back":  DAYS_BACK,
            "records":    len(data),
            "data":       data,
        }, f, indent=2)
    print(f"  ✓ Saved {len(data)} records to {OUT_FILE}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Set your EIA API key.")
        print("  export EIA_API_KEY=your_key_here")
        print("  Get one free at: https://www.eia.gov/opendata/register.php")
        exit(1)

    rows     = fetch_generation_by_fuel()
    computed = compute_carbon_intensity(rows)
    save(computed)
    print("Done.")
