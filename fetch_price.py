"""
fetch_price.py
Pulls recent real-time price data for an ISO region using the gridstatus
library and saves hourly averages to data/{region}_price_hourly.json,
in the same shape as fetch_data.py's carbon output so analyze.py can
combine them.

Regions map 1:1 to the EIA respondent codes already used in fetch_data.py:
  CAL  -> CAISO   (no credentials needed)
  TEX  -> ERCOT   (no credentials needed -- scrapes ERCOT's public report
                    archive, NOT the newer subscription-key Public API)
  NYIS -> NYISO   (no credentials needed)

NOTE ON LOCATIONS: each ISO's price hubs don't line up perfectly with the
EIA respondent boundaries used for the carbon data -- this picks one
representative hub/zone per region as an approximation, not an exact
geographic match. Documented per-region below.

Usage:
  python fetch_price.py --region TEX
"""

import argparse
import json
import os
from datetime import datetime, timedelta

import pandas as pd

DAYS_BACK = 14
OUT_DIR = "data"

# One representative hub/zone per region. These are approximations --
# picked because they're liquid, commonly-referenced hubs, not because
# they exactly match the EIA respondent's footprint.
REGION_CONFIG = {
    "CAL":  {"iso": "CAISO", "location": "TH_NP15_GEN-APND", "location_type": "Trading Hub"},
    "TEX":  {"iso": "ERCOT", "location": "HB_HOUSTON",        "location_type": "Trading Hub"},
    "NYIS": {"iso": "NYISO", "location": "N.Y.C.",            "location_type": "Zone"},
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default=os.environ.get("EIA_REGION", "TEX"),
                        help="Region code matching fetch_data.py (CAL, TEX, NYIS)")
    return parser.parse_args()


def get_client(region_cfg):
    import gridstatus

    iso = region_cfg["iso"]
    if iso == "CAISO":
        return gridstatus.CAISO()
    if iso == "ERCOT":
        return gridstatus.Ercot()
    if iso == "NYISO":
        return gridstatus.NYISO()
    raise ValueError(f"Unknown ISO: {iso}")


def fetch_raw_prices(region, days_back=DAYS_BACK):
    """Pull the last N days of real-time price data for the region's hub."""
    import gridstatus
    from gridstatus.base import Markets

    cfg = REGION_CONFIG[region]
    client = get_client(cfg)
    end = pd.Timestamp.now(tz="UTC")
    start = end - pd.Timedelta(days=days_back)

    print(f"Fetching {cfg['iso']} real-time prices for {cfg['location']} "
          f"from {start.date()} to {end.date()}...")

    if cfg["iso"] == "ERCOT":
        df = client.get_spp(
            date=start, end=end,
            market=Markets.REAL_TIME_15_MIN,
            locations=[cfg["location"]],
            location_type=cfg["location_type"],
        )
    elif cfg["iso"] == "CAISO":
        df = client.get_lmp(
            date=start, end=end,
            market="REAL_TIME_15_MIN",
            locations=[cfg["location"]],
        )
    elif cfg["iso"] == "NYISO":
        df = client.get_lmp(
            date=start, end=end,
            market=Markets.REAL_TIME_5_MIN,
            locations=[cfg["location"]],
        )

    print(f"  ✓ {len(df)} rows returned")
    return df


def price_column(df):
    """gridstatus names the price column differently per ISO (SPP vs LMP)."""
    for candidate in ("SPP", "LMP"):
        if candidate in df.columns:
            return candidate
    raise KeyError(f"No known price column found. Columns were: {list(df.columns)}")


def compute_hourly_avg(df):
    """Average price for each hour of day (0-23) across all days pulled."""
    col = price_column(df)
    ts_col = "Interval Start" if "Interval Start" in df.columns else "Time"
    df = df.copy()
    df["hour"] = pd.to_datetime(df[ts_col]).dt.hour
    hourly = df.groupby("hour")[col].mean().round(2)
    return {int(h): float(v) for h, v in hourly.items()}


def save(hourly_avg, region, raw_row_count):
    out_file = os.path.join(OUT_DIR, f"{region.lower()}_price_hourly.json")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump({
            "region": region,
            "hub": REGION_CONFIG[region]["location"],
            "iso": REGION_CONFIG[region]["iso"],
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "days_back": DAYS_BACK,
            "records": raw_row_count,
            "hourly_avg_price": [
                {"hour": h, "price": hourly_avg.get(h)}
                for h in range(24)
            ],
        }, f, indent=2)
    print(f"  ✓ Saved hourly price averages to {out_file}")


if __name__ == "__main__":
    args = parse_args()
    region = args.region.upper()

    if region not in REGION_CONFIG:
        print(f"ERROR: Unknown region '{region}'. Supported: {list(REGION_CONFIG.keys())}")
        exit(1)

    try:
        raw = fetch_raw_prices(region)
        hourly_avg = compute_hourly_avg(raw)
        save(hourly_avg, region, len(raw))
        print("\nDone.")
        print(f"  Region:  {region} ({REGION_CONFIG[region]['iso']})")
        print(f"  Hub:     {REGION_CONFIG[region]['location']}")
        for h in range(24):
            print(f"    {h:2d}h  ${hourly_avg.get(h, 'n/a')}")
    except Exception as e:
        print(f"ERROR: {e}")
        exit(1)
