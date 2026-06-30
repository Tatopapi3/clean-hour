// Vercel serverless function: holds the Electricity Maps key (env var) and
// returns the data the Clean Hour app needs. Deploy on Vercel, then set
// ELECTRICITYMAPS_TOKEN in the project's Environment Variables.
//
// GET /api/grid?zone=US-CAL-CISO   or   /api/grid?lat=..&lon=..

const EM = "https://api.electricitymap.org/v3/carbon-intensity";

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

export default async function handler(req, res) {
  const token = process.env.ELECTRICITYMAPS_TOKEN;
  if (!token) return res.status(500).json({ error: "ELECTRICITYMAPS_TOKEN not set" });

  const { zone, lat, lon } = req.query;
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

    res.setHeader("Cache-Control", "s-maxage=600, stale-while-revalidate");
    res.status(200).json({ zone: resolvedZone, current, hourly, swing, gridfit, cleanest });
  } catch (e) {
    res.status(502).json({ error: String(e.message || e) });
  }
}
