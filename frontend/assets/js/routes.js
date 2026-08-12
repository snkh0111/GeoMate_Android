/**
 * GeoMate Android — 路线列表页
 * 从后端 GET /routes 渲染路线卡片（结构与原设计一致，数据为真实后端数据）
 * 支持顶部类型筛选 chips
 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const listEl = $("#route-list");
  const subEl = $("#route-subtitle");
  const filterEl = $("#route-filters");

  let routes = [];

  // ── 显示映射（兼容后端枚举与中文） ──
  function displayType(v) {
    const map = { igneous: "岩浆岩", sedimentary: "沉积岩", metamorphic: "变质岩", composite: "综合", coastal: "海岸地貌" };
    return map[v] || v || "综合";
  }
  function displayDifficulty(v) {
    const map = { easy: "较易", medium: "中等", hard: "较难" };
    return map[v] || v || "中等";
  }
  // 清洗规则引擎生成的序号前缀："二、路线一：马山火山喷出岩路线" → "马山火山喷出岩路线"
  function cleanName(name) {
    const s = String(name || "")
      .replace(/^[一二三四五六七八九十百\d]+、/, "")
      .replace(/^路线[一二三四五六七八九十\d]*[:：]?\s*/, "")
      .trim();
    return s || name;
  }
  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ── 卡片渲染（复刻原设计卡片结构） ──
  function cardHtml(r, num) {
    return `<a href="#" data-dom-id="route-card" data-route-id="${r.id}" class="gm-card p-4 block">
      <div class="route-card-inner">
        <span class="badge-num">${String(num).padStart(2, "0")}</span>
        <div class="min-w-0 flex-1">
          <p class="text-[16px] font-semibold leading-snug">${escapeHtml(cleanName(r.name))}</p>
          <p class="mt-1 flex items-center gap-1 text-[13px] text-ink-2 min-w-0">
            <i data-lucide="map-pin" class="w-3.5 h-3.5 shrink-0"></i>
            <span class="truncate">${escapeHtml(r.location || "")}</span>
          </p>
          <div class="mt-2 flex items-center gap-2">
            <span class="gm-chip">${escapeHtml(displayType(r.geological_type))}</span>
            <span class="text-[12px] text-ink-3">${r.duration_hours != null ? "约" + r.duration_hours + "小时 · " : ""}难度${escapeHtml(displayDifficulty(r.difficulty))}</span>
          </div>
        </div>
        <i data-lucide="chevron-right" class="w-5 h-5 shrink-0 text-ink-3"></i>
      </div>
    </a>`;
  }

  function emptyHtml() {
    return `<div class="gm-card p-5 text-center">
      <p class="text-[15px] font-medium">还没有实习路线</p>
      <p class="mt-1.5 text-[13px] text-ink-2">去首页上传实习 PDF，AI 将自动为你生成路线</p>
    </div>`;
  }

  function render(filter) {
    if (!listEl) return;
    const items = routes.filter(function (r) {
      return !filter || filter === "all" || displayType(r.geological_type) === filter;
    });
    if (!items.length) {
      listEl.innerHTML = emptyHtml();
      return;
    }
    listEl.innerHTML = "";
    items.forEach(function (r) {
      const num = routes.indexOf(r) + 1; // 序号取全列表位置，保持稳定
      listEl.insertAdjacentHTML("beforeend", cardHtml(r, num));
    });
    if (window.lucide) lucide.createIcons();
  }

  async function load() {
    try {
      const data = await GeoMate.getRoutes();
      routes = (data && data.items) || [];
      if (subEl) subEl.textContent = "威海 · " + routes.length + " 条实习路线";
      render("all");
    } catch (e) {
      console.error("加载路线失败:", e);
      if (listEl) listEl.innerHTML = emptyHtml();
    }
  }

  // ── 类型筛选 ──
  if (filterEl) {
    filterEl.addEventListener("click", function (e) {
      const chip = e.target.closest(".gm-chip");
      if (!chip) return;
      const f = chip.getAttribute("data-filter");
      filterEl.querySelectorAll(".gm-chip").forEach(function (c) {
        c.classList.toggle("gm-chip-active", c === chip);
      });
      render(f);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
