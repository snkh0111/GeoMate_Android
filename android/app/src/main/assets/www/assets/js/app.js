/**
 * GeoMate Android — App Bootstrap
 * Initializes the app: seeds data, loads home page content from API.
 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ── Status banner ──
  function showStatus(text, type) {
    const el = document.getElementById("api-status");
    if (!el) return;
    el.textContent = text;
    el.className = type === "error" ? "text-red-500" : type === "loading" ? "text-muted-foreground" : "text-green-600";
  }

  // ── Check backend health ──
  async function checkBackend() {
    try {
      showStatus("连接后端...", "loading");
      const h = await GeoMate.health();
      console.log("Backend:", h);
      showStatus("后端已连接 ✓", "ok");
      return true;
    } catch (e) {
      console.error("Backend unreachable:", e);
      showStatus("后端未启动，请在终端运行: python run.py", "error");
      return false;
    }
  }

  // ── Ensure user + seed data ──
  async function initApp() {
    // Register / login default user
    try {
      const user = await GeoMate.register(
        "geomate_user",
        "user@geomate.cn",
        "geomate123",
        "GeoMate"
      );
      console.log("User:", user);
    } catch (e) {
      // User may already exist — try fetching existing data
      console.log("User already exists, skipping register");
    }

    // Seed routes
    try {
      await GeoMate.seedRoutes();
      console.log("Routes seeded");
    } catch (e) { console.log("Routes seed skipped:", e.message); }

    // Seed study plans
    try {
      // Use userId=1 as fallback
      const uid = GeoMate.userId || 1;
      const plans = await GeoMate.seedPlans(uid);
      console.log("Plans seeded:", plans);
    } catch (e) { console.log("Plans seed skipped:", e.message); }

    // Seed field notes
    try {
      const uid = GeoMate.userId || 1;
      await GeoMate.seedNotes(uid);
      console.log("Notes seeded");
    } catch (e) { console.log("Notes seed skipped:", e.message); }
  }

  // ── Load home page data ──
  async function loadHomeData() {
    try {
      // Routes summary
      const routes = await GeoMate.getRoutes(1, 5);
      console.log("Routes:", routes);

      // Plan stats
      const stats = await GeoMate.getPlanStats(1);
      console.log("Plan stats:", stats);

      // Populate UI elements if they exist
      const routeCountEl = document.getElementById("route-count-num");
      if (routeCountEl) routeCountEl.textContent = routes.total || "7";

      showStatus("数据加载完成 ✓", "ok");
    } catch (e) {
      console.error("Home data load failed:", e);
    }
  }

  // ── Init ──
  async function bootstrap() {
    console.log("GeoMate Android booting...");

    const ok = await checkBackend();
    if (!ok) return;

    await initApp();
    await loadHomeData();

    console.log("GeoMate ready.");
  }

  // Auto-start when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})();
