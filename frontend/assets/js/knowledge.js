/**
 * GeoMate Android — 知识库页
 * 统计 + 文档列表来自 /knowledge/stats 与 /knowledge/documents；
 * 搜索 / 分类 chips 走 /knowledge/search 语义检索；
 * "上传 PDF 资料"真实调用 /knowledge/upload。
 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const listEl = $("#kb-doclist");
  let mode = "docs"; // docs | search

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function relTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const diff = Date.now() - d.getTime();
    const MIN = 60 * 1000, HOUR = 60 * MIN, DAY = 24 * HOUR;
    if (diff < MIN) return "刚刚";
    if (diff < HOUR) return Math.floor(diff / MIN) + " 分钟前";
    if (diff < DAY) return Math.floor(diff / HOUR) + " 小时前";
    if (diff < 7 * DAY) return Math.floor(diff / DAY) + " 天前";
    if (diff < 30 * DAY) return Math.floor(diff / (7 * DAY)) + " 周前";
    return Math.floor(diff / (30 * DAY)) + " 个月前";
  }
  function truncate(s, n) {
    const str = String(s || "");
    return str.length > n ? str.slice(0, n) + "…" : str;
  }

  // ── 统计 ──
  async function loadStats() {
    try {
      const stats = await GeoMate.getKnowledgeStats();
      const dEl = $("#kb-stat-docs");
      const cEl = $("#kb-stat-chunks");
      if (dEl) dEl.textContent = (stats && stats.document_count) || 0;
      if (cEl) cEl.textContent = (stats && stats.chunk_count) || 0;
      try {
        const filters = await GeoMate.getKnowledgeFilters();
        const cats = (filters && filters.categories) || [];
        const catEl = $("#kb-stat-cats");
        if (catEl) catEl.textContent = cats.length;
      } catch (e) { /* 分类数可缺省 */ }
    } catch (e) {
      console.error("加载知识库统计失败:", e);
    }
  }

  // ── 文档列表 ──
  function docCardHtml(doc) {
    const name = doc.title || doc.filename;
    const chunk = doc.chunk_count != null ? doc.chunk_count + " 知识块" : "";
    const time = relTime(doc.created_at);
    const ready = doc.status === "ready" || doc.status === "completed";
    return `<article class="gm-card kb-doc">
      <div class="kb-doc-row">
        <span class="gm-icon-tile"><i data-lucide="file-text" class="w-5 h-5"></i></span>
        <div class="kb-doc-body">
          <h3 class="kb-doc-title text-[15px] font-medium">${escapeHtml(name)}</h3>
          <div class="kb-doc-meta">
            <span class="gm-chip">${ready ? "已入库" : "处理中"}</span>
            ${chunk ? `<span class="kb-meta-text text-ink-3">· ${escapeHtml(chunk)}</span>` : ""}
            ${time ? `<span class="kb-meta-text text-ink-3">${escapeHtml(time)}</span>` : ""}
          </div>
        </div>
        <i data-lucide="chevron-right" class="kb-doc-arrow w-5 h-5"></i>
      </div>
    </article>`;
  }

  // ── 搜索结果 ──
  function resultCardHtml(item) {
    const cat = item.category && item.category !== "general" ? item.category : "知识片段";
    const score = item.score != null ? "相关度 " + Math.round(item.score * 100) + "%" : "";
    return `<article class="gm-card kb-doc">
      <div class="kb-doc-row">
        <span class="gm-icon-tile"><i data-lucide="search" class="w-5 h-5"></i></span>
        <div class="kb-doc-body">
          <h3 class="kb-doc-title text-[15px] font-medium">${escapeHtml(item.document_title || "知识片段")}</h3>
          <div class="kb-doc-meta">
            <span class="gm-chip">${escapeHtml(cat)}</span>
            ${score ? `<span class="kb-meta-text text-ink-3">· ${escapeHtml(score)}</span>` : ""}
          </div>
          <p class="mt-1.5 text-[13px] leading-relaxed text-ink-2 line-clamp-2">${escapeHtml(truncate(item.content, 90))}</p>
        </div>
      </div>
    </article>`;
  }

  function emptyHtml(text) {
    return `<div class="gm-card kb-doc text-center">
      <p class="text-[15px] font-medium">${escapeHtml(text)}</p>
      <p class="mt-1.5 text-[13px] text-ink-2">上传 PDF 或换个关键词试试</p>
    </div>`;
  }

  async function loadDocs() {
    mode = "docs";
    try {
      const data = await GeoMate.getKnowledgeDocuments();
      const items = (data && data.items) || [];
      if (!listEl) return;
      if (!items.length) {
        listEl.innerHTML = emptyHtml("知识库暂无内容");
        return;
      }
      listEl.innerHTML = items.map(docCardHtml).join("");
      if (window.lucide) lucide.createIcons();
    } catch (e) {
      console.error("加载知识文档失败:", e);
      if (listEl) listEl.innerHTML = emptyHtml("知识库加载失败");
    }
  }

  async function doSearch(q) {
    const query = (q || "").trim();
    if (!query) { loadDocs(); return; }
    mode = "search";
    try {
      const data = await GeoMate.searchKnowledge(query);
      const results = (data && data.results) || [];
      if (!listEl) return;
      if (!results.length) {
        listEl.innerHTML = emptyHtml("没有找到相关结果");
        return;
      }
      listEl.innerHTML = results.map(resultCardHtml).join("");
      if (window.lucide) lucide.createIcons();
    } catch (e) {
      console.error("知识库搜索失败:", e);
      if (listEl) listEl.innerHTML = emptyHtml("搜索失败，请稍后再试");
    }
  }

  // ── 事件绑定 ──
  function bindEvents() {
    const input = $("#kb-search-input");
    const btn = $("#kb-search-btn");
    if (btn) {
      btn.addEventListener("click", function () { doSearch(input && input.value); });
    }
    if (input) {
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); doSearch(input.value); }
      });
    }
    // 建议问题 chips
    document.querySelectorAll("[data-quick]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        if (input) input.value = chip.getAttribute("data-quick");
        doSearch(chip.getAttribute("data-quick"));
      });
    });
    // 分类筛选 chips
    const filtersEl = $("#kb-filters");
    if (filtersEl) {
      filtersEl.addEventListener("click", function (e) {
        const chip = e.target.closest(".gm-chip");
        if (!chip) return;
        const cat = chip.getAttribute("data-cat");
        filtersEl.querySelectorAll(".gm-chip").forEach(function (c) {
          c.classList.toggle("gm-chip-active", c === chip);
        });
        if (!cat || cat === "all") {
          loadDocs();
        } else {
          doSearch(cat);
        }
      });
    }
    // 上传 PDF
    const uploadBtn = $("#kb-upload-btn");
    const uploadInput = $("#kb-upload-input");
    if (uploadBtn && uploadInput) {
      uploadBtn.addEventListener("click", function () { uploadInput.click(); });
      uploadInput.addEventListener("change", async function () {
        const file = uploadInput.files && uploadInput.files[0];
        uploadInput.value = "";
        if (!file) return;
        const old = uploadBtn.innerHTML;
        uploadBtn.innerHTML = '<i data-lucide="loader" class="w-5 h-5"></i>上传处理中...';
        try {
          await GeoMate.uploadKnowledge(file);
          await loadStats();
          await loadDocs();
          uploadBtn.innerHTML = old;
          if (window.lucide) lucide.createIcons();
        } catch (err) {
          console.error("上传失败:", err);
          uploadBtn.innerHTML = old;
          alert("上传失败：" + ((err && err.message) || "网络错误"));
        }
      });
    }
  }

  async function init() {
    bindEvents();
    await loadStats();
    await loadDocs();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
