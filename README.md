# Clean Hour

> Same outlet. Same lifestyle. A fraction of the carbon.

**Live site:** https://clean-hour.vercel.app  
🔗 **Also live at:** [tatopapi3.github.io/clean-hour](https://tatopapi3.github.io/clean-hour)

Clean Hour tells you whether carbon-aware energy use is worth it where you live — and by how much. It shows real-time grid carbon intensity **and** electricity pricing across three major U.S. grids on a 24-hour clock, so the timing mismatch between clean supply and dirty demand is visible in one glance.

---

## The insight

Grid carbon intensity isn't constant — it swings hard by the hour. California's grid can be **3.6× cleaner at 1pm than at 7pm**, on the same day, through the same outlet. Solar peaks at midday when demand is low. Gas fires up in the evening when everyone gets home. Nobody tells you this.

Clean Hour does — for California, Texas, and New York, combining carbon intensity with real electricity pricing into one plain verdict.

---

## What's live now

- **Multi-region support:** California (CAISO), Texas (ERCOT), New York (NYISO)
- **ZIP code lookup:** enter any ZIP, get your grid's live status instantly
- **Combined carbon + price verdict:** not just "is the grid clean" — is it clean *and* worth it, using both carbon intensity and real electricity pricing
- **24-hour clock visualization:** clean/moderate/high windows at a glance, with a live current-time marker
- **Interactive map:** Electricity Maps-style colored region overlays; zooming into a city fades to street level and tints the map with the live intensity color
- **Push notifications:** alerts when today's clean energy window opens
- **Impact tracking:** CO₂ saved over time, weekly savings chart, clean-charge history
- **Installable PWA:** add to your home screen on iOS/Android, works offline via service worker

---

## Architecture

```
EIA Open Data API          gridstatus library
        ↓                          ↓
fetch_data.py              fetch_price.py
        ↓                          ↓
data/{region}_hourly.json  data/{region}_price_hourly.json
              ↘               ↙
               analyze.py
                    ↓
         data/{region}_insight.json
                    ↓
              api/grid.js  ←  Electricity Maps API (live token)
                    ↓
              index.html  (PWA frontend)
```

GitHub Actions runs the full pipeline every hour and commits updated `data/` files to `main`. Vercel redeploys automatically on each push.

**Supported regions:**

| Grid | EIA code | Zone | Price hub |
|---|---|---|---|
| CAISO | CAL | US-CAL-CISO | TH_NP15_GEN-APND |
| ERCOT | TEX | US-TEX-ERCO | HB_HOUSTON |
| NYISO | NYIS | US-NY-NYIS | N.Y.C. |

---

## Setup

### 1. Get a free EIA API key
Register at [eia.gov/opendata](https://www.eia.gov/opendata/register.php) — instant, no credit card.

### 2. Install dependencies
Requires Python 3.11+ (gridstatus uses `int | None` union syntax).
```bash
pip install -r requirements.txt
```

### 3. Set your API key
```bash
export EIA_API_KEY=your_key_here
```

### 4. Fetch carbon data
```bash
python fetch_data.py --region CAL
python fetch_data.py --region TEX
python fetch_data.py --region NYIS
```
Pulls 2 weeks of hourly generation by fuel type. Saves to `data/{region}_hourly.json`.

### 5. Fetch price data
```bash
python fetch_price.py --region CAL
python fetch_price.py --region TEX
python fetch_price.py --region NYIS
```
Pulls recent real-time LMP/SPP prices via gridstatus. Saves to `data/{region}_price_hourly.json`.

### 6. Run the analysis engine
```bash
python analyze.py --region CAL
python analyze.py --region TEX
python analyze.py --region NYIS
```
Computes hourly averages, daily swing %, marginal carbon intensity, next clean window, and the combined carbon + price verdict. Saves to `data/{region}_insight.json`.

### 7. Open the app
Open `index.html` in your browser — or visit the live URL above.

---

## Serverless API

`api/grid.js` is a Vercel serverless function that the frontend calls at `/api/grid?zone=US-CAL-CISO` (or `?lat=&lon=`).

**Live path:** fetches from [Electricity Maps API](https://www.electricitymaps.com/) using `ELECTRICITYMAPS_TOKEN` (set in Vercel environment variables).  
**EIA fallback:** if no token or live fetch fails, reads `data/{region}_insight.json` from disk — always returns real data including marginal intensity, next clean window, and combined verdict.

---

## Verdict logic

### Grid fit (carbon only)

| Verdict | Daily swing | What it means |
|---|---|---|
| High fit | ≥ 30% | Timing cuts ~25–45% of charging emissions |
| Moderate | 15–29% | Some benefit but not transformative |
| Low fit | < 15% | Flat grid — timing barely matters |

### Combined verdict (carbon + price)

Each hour is classified into a tercile (low/mid/high) for both carbon intensity and electricity price independently. The crossing produces five signals:

| Signal | Meaning |
|---|---|
| `both_worth_it` | Clean grid, low price — best time to charge |
| `both_skip` | Dirty grid, high price — worst time |
| `clean_but_pricey` | Low carbon but elevated price |
| `cheap_but_dirty` | Low price but high emissions |
| `mixed` | Middle terciles on one or both dimensions |

---

## Data sources

- **EIA Open Data API** — hourly electricity generation by fuel type, per grid region
- **Electricity Maps API** — live carbon intensity and 48-hour forecast
- **gridstatus** — real-time LMP/SPP electricity prices (CAISO, ERCOT, NYISO)
- **Carbon factors** — kg CO₂/MWh per fuel type (IPCC lifecycle estimates)
- **zippopotam.us** — ZIP code → lat/lon for the location finder

---

## Team

Built at Pursuit L2 · Cycle 2

**Antonin Lesov** · **Juan Fernandez** · **Bertrand Cius**
