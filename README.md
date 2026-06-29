# Clean Hour

> Same outlet. Same lifestyle. A fraction of the carbon.

**Live site:** https://clean-hour.vercel.app

**Clean Hour** tells you whether carbon-aware charging is worth it where you live — and by how much. It shows California's hourly grid carbon intensity on a 24-hour radial clock, so the timing mismatch between clean supply and dirty demand is visible in one glance.

🔗 **Live at:** [tatopapi3.github.io/clean-hour](https://tatopapi3.github.io/clean-hour)

---

## The insight

California's grid is **3.6× cleaner at 1pm than at 7pm** — on the same day, through the same outlet. Solar peaks at midday when demand is low. Gas fires at 6pm when everyone gets home. Nobody tells you.

Clean Hour tells you.

---

## Architecture

```
EIA Open Data API
      ↓
fetch_data.py     → data/ca_hourly.json   (raw hourly generation by fuel type)
      ↓
analyze.py        → data/ca_insight.json  (verdict engine output)
      ↓
index.html        → 24hr polar clock chart + live signal
```

---

## Setup

### 1. Get a free EIA API key
Register at [eia.gov/opendata](https://www.eia.gov/opendata/register.php) — instant, no credit card.

### 2. Install dependencies
```bash
pip install requests
```

### 3. Set your API key
```bash
export EIA_API_KEY=your_key_here
```

### 4. Fetch data
```bash
python fetch_data.py
```
Pulls 2 weeks of hourly generation by fuel type for California (CAISO).
Saves to `data/ca_hourly.json`.

### 5. Run the verdict engine
```bash
python analyze.py
```
Computes hourly averages, daily swing %, verdict, and live signal.
Saves to `data/ca_insight.json`.

### 6. Open the chart
Open `index.html` in your browser — or visit the live URL above.

---

## Verdict logic

| Verdict | Daily swing | What it means |
|---|---|---|
| Worth it | ≥30% | Charging timing cuts ~25–45% of charging emissions |
| Moderate | 15–29% | Some benefit but not transformative |
| Skip it | <15% | Flat grid — timing barely helps |

**Why swing %?** A grid could be dirty overall but flat hour-to-hour — meaning your behavior can't change much. Swing tells you whether *when* you charge matters, not just how dirty your grid is.

---

## Data sources

- **EIA Open Data API** — hourly electricity generation by fuel type, CAISO region
- **Carbon factors** — kg CO₂/MWh per fuel type (IPCC lifecycle estimates)

---

## Team

Built at Pursuit L2 · Cycle 2 · Week 3

**Antonin Lesov** · **Juan Fernandez** · **Bertrand Cius**

---

## What's next

- [ ] Connect live EIA API to frontend (replace hardcoded averages)
- [ ] ZIP → grid region mapping for other US regions
- [ ] Push notification: "best charge window in next 3 hours"
- [ ] Smart appliance API endpoint
