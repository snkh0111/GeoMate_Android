/**
 * GeoMate Android — 野外记录页
 * 从后端 /notes?user_id= 渲染记录卡片；路线 chips 按 route_id 过滤；
 * "新增记录"真实调用 POST /notes/ 创建一条记录并刷新。
 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const listEl = $("#notes-list");
  const countEl = $("#notes-count");
  const filtersEl = $("#notes-filters");

  let notes = [];
  let currentRoute = "all"; // "all" | 路线 id 字符串

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function cleanName(name) {
    const s = String(name || "")
      .replace(/^[一二三四五六七八九十百\d]+、/, "")
      .replace(/^路线[一二三四五六七八九十\d]*[:：]?\s*/, "")
      .trim();
    return s || name;
  }
  // ISO "2026-07-28T14:20:00" → "7/28 14:20"
  function fmtTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const mm = String(d.getMonth() + 1);
    const dd = String(d.getDate());
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    return mm + "/" + dd + " " + hh + ":" + mi;
  }

  // ── 卡片渲染（复刻原设计结构） ──
  function noteCardHtml(n) {
    const title = n.point_number || ("点位 " + (n.id || ""));
    const metas = [];
    if (n.attitude) {
      metas.push('<span class="inline-flex items-center gap-1"><i data-lucide="compass" class="h-3.5 w-3.5"></i>产状 ' + escapeHtml(n.attitude) + "</span>");
    }
    if (n.sample_number) {
      metas.push('<span class="inline-flex items-center gap-1"><i data-lucide="tag" class="h-3.5 w-3.5"></i>标本 ' + escapeHtml(n.sample_number) + "</span>");
    }
    if (n.weather) {
      metas.push('<span class="inline-flex items-center gap-1"><i data-lucide="sun" class="h-3.5 w-3.5"></i>' + escapeHtml(n.weather) + "</span>");
    }
    const t = fmtTime(n.recorded_at || n.created_at);
    if (t) {
      metas.push('<span class="inline-flex items-center gap-1"><i data-lucide="clock" class="h-3.5 w-3.5"></i>' + t + "</span>");
    }
    return `<article class="gm-card p-4">
      <div class="gm-row items-start">
        <div class="gm-icon-tile">
          <i data-lucide="map-pin" class="h-5 w-5"></i>
        </div>
        <div class="note-body">
          <div class="flex flex-wrap items-center gap-2">
            <h2 class="text-[15px] font-semibold">${escapeHtml(title)}</h2>
            ${n.rock_type ? `<span class="gm-chip">${escapeHtml(n.rock_type)}</span>` : ""}
          </div>
          ${n.location ? `<div class="mt-1.5 flex items-center gap-1 text-[13px] text-ink-2">
            <i data-lucide="map-pin" class="h-3.5 w-3.5 flex-shrink-0"></i>
            <span class="truncate">${escapeHtml(n.location)}</span>
          </div>` : ""}
          ${n.description ? `<p class="mt-1.5 line-clamp-2 text-[14px] leading-relaxed text-ink-2">${escapeHtml(n.description)}</p>` : ""}
          ${metas.length ? `<div class="gm-row meta-row mt-2.5 gap-3 text-[12px] text-ink-3">${metas.join("")}</div>` : ""}
        </div>
      </div>
    </article>`;
  }

  function emptyHtml() {
    return `<div class="gm-card p-5 text-center">
      <p class="text-[15px] font-medium">还没有野外记录</p>
      <p class="mt-1.5 text-[13px] text-ink-2">出野时点击"新增记录"记下你的观察点位</p>
    </div>`;
  }

  // ── 路线筛选 chips ──
  async function buildFilters() {
    if (!filtersEl) return;
    try {
      const data = await GeoMate.getRoutes();
      const routes = (data && data.items) || [];
      const html = ['<button class="gm-chip gm-chip-active" data-route="all">全部路线</button>']
        .concat(routes.map(function (r) {
          return `<button class="gm-chip" data-route="${r.id}">${escapeHtml(cleanName(r.name))}</button>`;
        }))
        .join("");
      filtersEl.innerHTML = html;
    } catch (e) { /* 无路线时仅保留"全部路线" */ }
    filtersEl.addEventListener("click", function (ev) {
      const chip = ev.target.closest(".gm-chip");
      if (!chip) return;
      const r = chip.getAttribute("data-route");
      filtersEl.querySelectorAll(".gm-chip").forEach(function (c) {
        c.classList.toggle("gm-chip-active", c === chip);
      });
      currentRoute = r;
      render();
    });
  }

  // ── 渲染 ──
  function render() {
    if (!listEl) return;
    const items = notes.filter(function (n) {
      return currentRoute === "all" || String(n.route_id) === currentRoute;
    });
    if (countEl) countEl.textContent = items.length + " 条";
    if (!items.length) {
      listEl.innerHTML = emptyHtml();
      return;
    }
    listEl.innerHTML = items.map(noteCardHtml).join("");
    if (window.lucide) lucide.createIcons();
  }

  async function load() {
    const user = window.GeoMate && GeoMate.currentUser();
    if (!user) {
      location.href = "./login.html";
      return;
    }
    try {
      const data = await GeoMate.getNotes(user.id);
      notes = (data && data.items) || [];
      render();
    } catch (e) {
      console.error("加载野外记录失败:", e);
      if (listEl) listEl.innerHTML = emptyHtml();
    }
  }

  // ── 新增记录 ──
  function bindAdd() {
    const btn = document.querySelector('[data-dom-id="fab-notes"]');
    if (!btn) return;
    btn.addEventListener("click", async function () {
      const user = window.GeoMate && GeoMate.currentUser();
      if (!user) { location.href = "./login.html"; return; }
      const orig = btn.innerHTML;
      btn.innerHTML = '<i data-lucide="loader" class="h-5 w-5"></i>创建中...';
      btn.disabled = true;
      try {
        const seq = notes.length + 1;
        await GeoMate.createNote(user.id, {
          point_number: "D" + seq,
          location: "待补充地点",
          description: "待补充地质描述",
        });
        await load();
      } catch (err) {
        console.error("创建记录失败:", err);
        alert("创建失败：" + ((err && err.message) || "网络错误"));
      } finally {
        btn.innerHTML = orig;
        btn.disabled = false;
        if (window.lucide) lucide.createIcons();
      }
    });
  }

  async function init() {
    buildFilters();
    bindAdd();
    await load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
