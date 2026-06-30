"""
analyze.py
Reads data/{region}_hourly.json produced by fetch_data.py and outputs:
  data/{region}_insight.json  → hour-by-hour averages + verdict for the frontend

Usage:
  python analyze.py              # defaults to CAL
  python analyze.py --region TEX
  EIA_REGION=NY python analyze.py
"""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default=os.environ.get("EIA_REGION", "CAL"),
                        help="EIA region code matching what fetch_data.py used (default: CAL)")
    return parser.parse_args()

# ── Verdict thresholds ────────────────────────────────────────────────────────
WORTH_IT_THRESHOLD = 30   # ≥30% swing → charging timing makes a real difference
MODERATE_THRESHOLD = 15   # 15–29%    → moderate benefit

def load(region):
    in_file = os.path.join("data", f"{region.lower()}_hourly.json")
    if not os.path.exists(in_file):
        raise FileNotFoundError(
            f"{in_file} not found. Run: python fetch_data.py --region {region}"
        )
    with open(in_file) as f:
        return json.load(f)


def avg_by_hour(records):
    """Average carbon intensity for each hour of day (0–23) across all days."""
    totals = defaultdict(list)
    for r in records:
        h = r.get("hour", -1)
        if 0 <= h <= 23:
            totals[h].append(r["carbon_intensity"])
    return {
        h: round(sum(vals) / len(vals), 1)
        for h, vals in totals.items()
    }


def compute_verdict(avg_intensity):
    if not avg_intensity:
        return "unknown", 0, "Insufficient data"

    max_intensity = max(avg_intensity.values())
    min_intensity = min(avg_intensity.values())
    swing_pct     = round((max_intensity - min_intensity) / max_intensity * 100, 1)

    if swing_pct >= WORTH_IT_THRESHOLD:
        verdict = "worth_it"
        label   = "Worth it"
        reason  = (
            f"Your grid swings {swing_pct}% daily — "
            f"charging at the cleanest hour instead of the dirtiest "
            f"cuts roughly {round(swing_pct * 0.8)}% of your charging emissions."
        )
    elif swing_pct >= MODERATE_THRESHOLD:
        verdict = "moderate"
        label   = "Moderate benefit"
        reason  = (
            f"Your grid swings {swing_pct}% daily — "
            f"timing your charging helps somewhat but won't transform your footprint."
        )
    else:
        verdict = "skip"
        label   = "Skip it"
        reason  = (
            f"Your grid only swings {swing_pct}% daily — "
            f"timing barely matters here. Your grid is already relatively flat."
        )

    return verdict, swing_pct, label, reason


def find_windows(avg_intensity):
    if not avg_intensity:
        return None, None, None, None

    sorted_hours  = sorted(avg_intensity.items(), key=lambda x: x[1])
    cleanest_hour = sorted_hours[0][0]
    dirtiest_hour = sorted_hours[-1][0]

    def fmt(h):
        suffix  = "am" if h < 12 else "pm"
        display = h if h <= 12 else h - 12
        display = 12 if display == 0 else display
        return f"{display}{suffix}"

    cleanest_window = f"{fmt(cleanest_hour)}–{fmt((cleanest_hour + 3) % 24)}"
    dirtiest_window = f"{fmt(dirtiest_hour)}–{fmt((dirtiest_hour + 3) % 24)}"

    return cleanest_hour, dirtiest_hour, cleanest_window, dirtiest_window


def yearly_estimate(max_intensity, min_intensity):
    kwh_per_charge  = 60 * 0.80
    charges_per_yr  = 3 * 52
    intensity_diff  = max_intensity - min_intensity
    kg_saved        = (intensity_diff / 1000) * kwh_per_charge * charges_per_yr
    return round(kg_saved, 1)


def now_signal(avg_intensity):
    current_hour = datetime.utcnow().hour
    intensity    = avg_intensity.get(current_hour, None)
    if intensity is None:
        return current_hour, None, "unknown", "Unknown"

    all_vals    = list(avg_intensity.values())
    low_cutoff  = sorted(all_vals)[len(all_vals) // 3]
    high_cutoff = sorted(all_vals)[2 * len(all_vals) // 3]

    if intensity <= low_cutoff:
        signal = "use_now"
        signal_label = "Good time to use power"
    elif intensity >= high_cutoff:
        signal = "wait"
        signal_label = "Wait if you can"
    else:
        signal = "moderate"
        signal_label = "Moderate — not ideal, not terrible"

    return current_hour, round(intensity, 1), signal, signal_label


def save(insight, region):
    out_file = os.path.join("data", f"{region.lower()}_insight.json")
    os.makedirs("data", exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(insight, f, indent=2)
    print(f"  ✓ Saved insight to {out_file}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = parse_args()
    region = args.region.upper()

    print("Loading data...")
    raw = load(region)
    records = raw["data"]
    print(f"  ✓ {len(records)} records loaded")

    print("Computing hourly averages...")
    avg_intensity = avg_by_hour(records)

    print("Computing verdict...")
    verdict, swing_pct, label, reason = compute_verdict(avg_intensity)

    print("Finding clean/dirty windows...")
    cleanest_hour, dirtiest_hour, cleanest_window, dirtiest_window = find_windows(avg_intensity)

    max_intensity = max(avg_intensity.values())
    min_intensity = min(avg_intensity.values())

    print("Computing yearly estimate...")
    kg_saved_yr = yearly_estimate(max_intensity, min_intensity)
    pct_saved   = round((max_intensity - min_intensity) / max_intensity * 100, 1)

    print("Computing now signal...")
    current_hour, current_intensity, signal, signal_label = now_signal(avg_intensity)

    insight = {
        "region":           region,
        "analyzed_at":      datetime.utcnow().isoformat() + "Z",
        "days_analyzed":    raw.get("days_back", 14),
        "verdict":          verdict,
        "verdict_label":    label,
        "verdict_reason":   reason,
        "daily_swing_pct":  swing_pct,
        "cleanest_hour":    cleanest_hour,
        "dirtiest_hour":    dirtiest_hour,
        "cleanest_window":  cleanest_window,
        "dirtiest_window":  dirtiest_window,
        "min_intensity":    min_intensity,
        "max_intensity":    max_intensity,
        "pct_saved":        pct_saved,
        "kg_saved_yr":      kg_saved_yr,
        "current_hour":     current_hour,
        "current_intensity": current_intensity,
        "signal":           signal,
        "signal_label":     signal_label,
        "hourly_avg": [
            {
                "hour":             h,
                "carbon_intensity": avg_intensity.get(h, 0),
            }
            for h in range(24)
        ],
    }

    save(insight, region)

    print("\n── Clean Hour Insight ───────────────────────────────")
    print(f"  Region:         {region}")
    print(f"  Verdict:        {label}")
    print(f"  Daily swing:    {swing_pct}%")
    print(f"  Cleanest hour:  {cleanest_window} ({min_intensity} kg CO₂/MWh)")
    print(f"  Dirtiest hour:  {dirtiest_window} ({max_intensity} kg CO₂/MWh)")
    print(f"  Yearly savings: ~{kg_saved_yr} kg CO₂ if you always charge clean")
    print(f"  Right now:      {signal_label} ({current_intensity} kg CO₂/MWh)")
    print("─────────────────────────────────────────────────────")
    print(f"Done. Feed data/{region.lower()}_insight.json to your frontend.")
