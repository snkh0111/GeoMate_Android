/**
 * GeoMate Android — App Bootstrap
 * 1. 检查后端健康（重试容忍冷启动）
 * 2. 校验登录状态（未登录 → login.html）
 * 3. 加载真实数据填充首页（空库时保持空白提示）
 * 4. 提供上传 PDF → 自动生成路线/计划/知识库
 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  // ── Status banner ──
  function showStatus(text, type) {
    const el = document.getElementById("api-status");
    if (!el) return;
    el.textContent = text;
    el.className = type === "error" ? "text-red-500" : type === "loading" ? "text-muted-foreground" : "text-green-600";
  }

  // ── Check backend health (retry to tolerate slow first cold start) ──
  async function checkBackend(maxRetries = 15, intervalMs = 700) {
    showStatus("连接后端...", "loading");
    for (let i = 1; i <= maxRetries; i++) {
      try {
        const h = await GeoMate.health();
        console.log("Backend:", h);
        showStatus("后端已连接 ✓", "ok");
        return true;
      } catch (e) {
        console.log(`Backend not ready (${i}/${maxRetries})`, e.message || e);
        await new Promise((r) => setTimeout(r, intervalMs));
      }
    }
    console.error("Backend unreachable after retries");
    showStatus("后端未启动，请确认内嵌服务已启动", "error");
    return false;
  }

  // ── Auth guard ──
  function requireLogin() {
    const user = GeoMate.currentUser();
    if (!user) {
      location.href = "./login.html";
      return null;
    }
    return user;
  }

  // ── Render user + stats ──
  function renderUser(user) {
    const nameEl = $("#user-name");
    const avatarEl = $("#user-avatar");
    const subEl = $("#user-subtitle");
    if (nameEl) nameEl.textContent = user.display_name || user.username;
    if (avatarEl) {
      avatarEl.textContent = (user.display_name || user.username || "G").charAt(0);
    }
    if (subEl) subEl.textContent = `@${user.username}`;
  }

  // ── Load home page data (real data; empty DB stays blank) ──
  async function loadHomeData() {
    const user = GeoMate.currentUser();
    if (!user) return;

    try {
      const routes = await GeoMate.getRoutes(1, 20);
      const stats = await GeoMate.getPlanStats(user.id);
      const kstats = await GeoMate.getKnowledgeStats();

      const routeCountEl = $("#stat-routes");
      const planCountEl = $("#stat-plans");
      const kdCountEl = $("#stat-knowledge");
      if (routeCountEl) routeCountEl.textContent = (routes && routes.total) || 0;
      if (planCountEl) planCountEl.textContent = (stats && stats.total_tasks) || 0;
      if (kdCountEl) kdCountEl.textContent = (kstats && kstats.document_count) || 0;

      // Empty state hint
      const emptyEl = $("#empty-state");
      if (emptyEl) {
        const totalCount = ((routes && routes.total) || 0) + ((stats && stats.total_tasks) || 0);
        if (totalCount > 0) {
          emptyEl.style.display = "none";
        } else {
          emptyEl.style.display = "";
        }
      }

      showStatus("数据加载完成 ✓", "ok");
    } catch (e) {
      console.error("Home data load failed:", e);
      showStatus("首页数据加载失败", "error");
    }
  }

  // ── Upload PDF → auto-generate ──
  async function handleUpload(file) {
    const user = GeoMate.currentUser();
    if (!user || !file) return;

    const statusEl = $("#upload-status");
    if (statusEl) statusEl.textContent = "上传中...";

    let doc;
    try {
      doc = await GeoMate.uploadDocument(user.id, file);
    } catch (e) {
      if (statusEl) { statusEl.textContent = "上传失败：" + e.message; statusEl.className = "text-red-500 text-[13px]"; }
      return;
    }

    if (statusEl) statusEl.textContent = "已上传，正在解析并生成计划路线与知识库（首次需约 10-30 秒）...";
    showStatus("AI 生成中...", "loading");

    try {
      const result = await GeoMate.autoGenerate(doc.document_id, user.id);
      console.log("Auto-generate result:", result);
      if (statusEl) {
        statusEl.textContent = "生成完成：" + (result.message || "路线/计划/知识库已生成");
        statusEl.className = "text-green-600 text-[13px]";
      }
      showStatus("生成完成 ✓", "ok");
      await loadHomeData();
    } catch (e) {
      console.error("Auto-generate failed:", e);
      if (statusEl) {
        statusEl.textContent = "生成失败：" + (e.message || "未知错误");
        statusEl.className = "text-red-500 text-[13px]";
      }
      showStatus("生成失败", "error");
    }
  }

  function bindUpload() {
    const input = $("#upload-input");
    const btn = $("#upload-btn");
    if (!input || !btn) return;

    btn.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (file) handleUpload(file);
      input.value = ""; // allow re-selecting the same file
    });
  }

  // ── Init ──
  async function bootstrap() {
    console.log("GeoMate Android booting...");

    const ok = await checkBackend();
    if (!ok) return;

    const user = requireLogin();
    if (!user) return;

    renderUser(user);
    bindUpload();
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
