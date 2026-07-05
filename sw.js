const CACHE = "clean-hour-v7";
const ASSETS = ["./", "./index.html", "./manifest.json", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) return;
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});

// ── Notification scheduling (client-side, fires when SW is alive) ─────────────
let _notifTimer = null;

self.addEventListener("message", (e) => {
  if (!e.data || e.data.type !== "SCHEDULE_NOTIFICATION") return;
  const { cleanHour, zone, savingsPct } = e.data;
  clearTimeout(_notifTimer);
  const now = new Date();
  const target = new Date();
  target.setHours(cleanHour, 0, 0, 0);
  if (target <= now) target.setDate(target.getDate() + 1);
  const delay = target - now;
  _notifTimer = setTimeout(() => {
    self.registration.showNotification("Clean Hour now! ⚡", {
      body: `Grid is at its cleanest. Charge now to cut ~${savingsPct}% of emissions.`,
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      tag: "clean-hour-alert",
      renotify: true,
    });
  }, delay);
});

// ── VAPID server push handler (future) ────────────────────────────────────────
self.addEventListener("push", (e) => {
  const d = e.data ? e.data.json() : {};
  e.waitUntil(
    self.registration.showNotification(d.title || "Clean Hour now! ⚡", {
      body: d.body || "The grid is at its cleanest. Good time to charge.",
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      tag: "clean-hour-alert",
    })
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((cs) => {
      const win = cs.find((c) => c.url.includes(self.location.origin));
      if (win) return win.focus();
      return clients.openWindow("/");
    })
  );
});
