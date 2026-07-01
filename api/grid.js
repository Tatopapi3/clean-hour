// Vercel serverless function: holds the Electricity Maps key (env var) and
// returns the data the Clean Hour app needs. Deploy on Vercel, then set
// ELECTRICITYMAPS_TOKEN in the project's Environment Variables.
//
// GET /api/grid?zone=US-CAL-CISO   or   /api/grid?lat=..&lon=..
//
// Fallback: if no token is set (or live fetch fails), serves data/{region}_insight.json
// (EIA-derived historical averages) so the app always returns real data.

import { readFileSync } from "fs";
import { join } from "path";

const EM = "https://api.electricitymap.org/v3/carbon-intensity";
const TTL_MS = 10 * 60 * 1000; // 10 minutes, matches CDN s-maxage
const cache = new Map(); // zone -> { data, expiresAt }

function cacheGet(key) {
  const entry = cache.get(key);
  if (entry && entry.expiresAt > Date.now()) return entry.data;
  cache.delete(key);
  return null;
}

function cacheSet(key, data) {
  cache.set(key, { data, expiresAt: Date.now() + TTL_MS });
}

function hourLabel(h) {
  const ap = h < 12 ? "am" : "pm";
  const h12 = h % 12 || 12;
  return `${h12}${ap}`;
}

async function em(path, params, token) {
  const url = new URL(`${EM}/${path}`);
  for (const k in params) url.searchParams.set(k, params[k]);
  const r = await fetch(url, { headers: { "auth-token": token } });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

// Maps Electricity Maps zone codes → EIA region codes used by the Python pipeline
const ZONE_TO_EIA = {
  "US-CAL-CISO": "cal",
  "US-TEX-ERCO": "tex",
  "US-NY-NYIS":  "ny",
  "US-MIDA-PJM": "mida",
  "US-MIDW-MISO":"midw",
  "US-NW-PACW":  "nw",
  "US-SE-SERC":  "se",
  "US-SW-PNM":   "sw",
};

function eiaFallback(zone) {
  const region = (zone && ZONE_TO_EIA[zone]) || "cal";
  let filePath = join(process.cwd(), "data", `${region}_insight.json`);
  // fall back to cal if the requested region file doesn't exist
  try { readFileSync(filePath); } catch { filePath = join(process.cwd(), "data", "cal_insight.json"); }
  const raw = JSON.parse(readFileSync(filePath, "utf8"));
  const hourly = new Array(24).fill(null);
  for (const { hour, carbon_intensity } of raw.hourly_avg) {
    hourly[hour] = Math.round(carbon_intensity);
  }
  const swing = Math.round(raw.daily_swing_pct);
  const gridfit = swing >= 30 ? "high" : swing >= 15 ? "moderate" : "low";
  const cleanest = {
    start: hourLabel(raw.cleanest_hour),
    end: hourLabel((raw.cleanest_hour + 2) % 24),
    value: Math.round(raw.min_intensity),
    savings_pct: Math.round(raw.pct_saved),
  };
  return {
    zone: zone || "US-CAL-CISO",
    current: raw.current_intensity,
    hourly,
    swing,
    gridfit,
    cleanest,
    source: "eia-fallback",
  };
}

export default async function handler(req, res) {
  const token = process.env.ELECTRICITYMAPS_TOKEN;
  const { zone, lat, lon } = req.query;

  if (!token) {
    try {
      res.setHeader("Cache-Control", "s-maxage=3600, stale-while-revalidate");
      return res.status(200).json(eiaFallback(zone));
    } catch (e) {
      return res.status(500).json({ error: "No token and EIA insight file unavailable" });
    }
  }

  const cacheKey = lat && lon ? `${lat},${lon}` : (zone || "US-CAL-CISO");
  const cached = cacheGet(cacheKey);
  if (cached) {
    res.setHeader("Cache-Control", "s-maxage=600, stale-while-revalidate");
    return res.status(200).json(cached);
  }

  const geo = lat && lon ? { lat, lon } : null;

  try {
    // latest -> current value + resolve zone if using coordinates
    const latest = await em("latest", geo || { zone }, token);
    const resolvedZone = latest.zone || zone || "US-CAL-CISO";
    const current = latest.carbonIntensity ?? null;

    // history -> 24h clock + daily swing
    const hist = await em("history", { zone: resolvedZone }, token);
    const hourly = new Array(24).fill(null);
    for (const p of hist.history || []) {
      if (p.carbonIntensity == null) continue;
      const h = new Date(p.datetime).getHours();
      hourly[h] = Math.round(p.carbonIntensity);
    }
    const vals = hourly.filter((v) => v != null);
    const swing = vals.length ? Math.round(((Math.max(...vals) - Math.min(...vals)) / Math.max(...vals)) * 100) : 0;
    const gridfit = swing >= 30 ? "high" : swing >= 15 ? "moderate" : "low";

    // forecast -> cleanest upcoming window (next 24h)
    let cleanest = null;
    try {
      const fc = await em("forecast", { zone: resolvedZone }, token);
      const now = Date.now();
      const up = (fc.forecast || [])
        .map((p) => ({ t: new Date(p.datetime), v: p.carbonIntensity }))
        .filter((p) => p.v != null && p.t.getTime() >= now && p.t.getTime() < now + 24 * 3600e3);
      if (up.length) {
        const best = up.reduce((a, b) => (b.v < a.v ? b : a));
        const worst = Math.max(...up.map((p) => p.v));
        const base = current || worst;
        cleanest = {
          start: hourLabel(best.t.getHours()),
          end: hourLabel((best.t.getHours() + 2) % 24),
          value: Math.round(best.v),
          savings_pct: base ? Math.max(0, Math.round(((base - best.v) / base) * 100)) : 0,
        };
      }
    } catch (e) { /* forecast optional */ }

    const result = { zone: resolvedZone, current, hourly, swing, gridfit, cleanest };
    cacheSet(cacheKey, result);
    res.setHeader("Cache-Control", "s-maxage=600, stale-while-revalidate");
    res.status(200).json(result);
  } catch (e) {
    try {
      res.setHeader("Cache-Control", "s-maxage=3600, stale-while-revalidate");
      return res.status(200).json({ ...eiaFallback(zone), live_error: String(e.message || e) });
    } catch {
      res.status(502).json({ error: String(e.message || e) });
    }
  }
}
