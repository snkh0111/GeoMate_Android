/**
 * GeoMate Android — 学习计划页
 * 从后端 /plans/daily（每日分组）+ /plans/stats（进度）渲染，
 * 结构与原设计一致；点击任务行可切换完成状态（PATCH toggle）。
 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const daysEl = $("#plans-days");
  const miniEl = $("#plans-mini");
  const subEl = $("#plans-subtitle");

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  // "2026-08-13" → "8/13"
  function fmtMD(dateStr) {
    const p = String(dateStr || "").split("-");
    if (p.length !== 3) return dateStr || "";
    return Number(p[1]) + "/" + Number(p[2]);
  }
  function pct(rate) {
    const v = Math.round((rate == null ? 0 : rate) * 100);
    return Math.max(0, Math.min(100, v));
  }

  // ── 每日详细列表 ──
  function taskRowHtml(task) {
    const done = task.status === "completed";
    const check = done
      ? `<span class="gm-check gm-check-done"><i data-lucide="check" class="w-4 h-4 text-primary-foreground"></i></span>`
      : `<span class="gm-check gm-check-pending border-border"></span>`;
    const text = done
      ? `<span class="gm-task-text gm-task-text-done text-ink-3 line-through">${escapeHtml(task.task_name)}</span>`
      : `<span class="gm-task-text gm-task-text-pending text-foreground">${escapeHtml(task.task_name)}</span>`;
    const cat = task.category ? `<span class="gm-chip shrink-0">${escapeHtml(task.category)}</span>` : "";
    return `<div class="gm-task-row" data-plan-id="${task.id}">${check}${text}${cat}</div>`;
  }

  function dayBlockHtml(day, idx) {
    const done = day.completed_tasks || 0;
    const total = day.total_tasks || 0;
    const w = total ? pct(done / total) : 0;
    const tasks = (day.items || []).map(function (t, i) {
      return taskRowHtml(t) + (i < day.items.length - 1 ? '<div class="gm-hairline mx-4"></div>' : "");
    }).join("");
    return `<div class="space-y-3">
      <div class="gm-row gm-row-between">
        <h2 class="gm-section-title">第${idx + 1}天 · ${fmtMD(day.date)}</h2>
        <span class="text-[12px] text-ink-3">${done}/${total} 完成</span>
      </div>
      <div class="gm-progress"><div class="gm-progress-bar" style="width:${w}%"></div></div>
      <div class="gm-card">${tasks}</div>
    </div>`;
  }

  // ── 紧凑日行 ──
  function miniRowHtml(day, idx) {
    const done = day.completed_tasks || 0;
    const total = day.total_tasks || 0;
    const w = total ? pct(done / total) : 0;
    const first = (day.items || [])[0];
    const label = first ? first.task_name : "";
    return `<div class="gm-row px-4 py-3">
      <span class="gm-icon-tile"><i data-lucide="calendar" class="w-5 h-5"></i></span>
      <div class="gm-day-cell">
        <div class="text-[14px] font-medium leading-snug">第${idx + 1}天 · ${fmtMD(day.date)} ${escapeHtml(label)}</div>
        <div class="mt-1 text-[12px] text-ink-3 leading-none">${done}/${total} 已完成</div>
      </div>
      <div class="gm-progress shrink-0" style="width:64px"><div class="gm-progress-bar" style="width:${w}%"></div></div>
    </div>`;
  }

  function emptyHtml() {
    return `<div class="gm-card p-5 text-center">
      <p class="text-[15px] font-medium">还没有学习计划</p>
      <p class="mt-1.5 text-[13px] text-ink-2">去首页上传实习 PDF，AI 将自动为你规划每日任务</p>
    </div>`;
  }

  // ── 渲染 ──
  function renderStats(stats) {
    const done = (stats && stats.completed_tasks) || 0;
    const total = (stats && stats.total_tasks) || 0;
    const rate = (stats && stats.completion_rate) != null ? stats.completion_rate : (total ? done / total : 0);
    const w = pct(rate);
    const tEl = $("#plans-overview-text");
    const bEl = $("#plans-overview-bar");
    const dEl = $("#plans-done");
    const pEl = $("#plans-pending");
    const rEl = $("#plans-rate");
    if (tEl) tEl.textContent = done + "/" + total + " 已完成";
    if (bEl) bEl.style.width = w + "%";
    if (dEl) dEl.textContent = done;
    if (pEl) pEl.textContent = Math.max(0, total - done);
    if (rEl) rEl.textContent = w + "%";
  }

  function render(daily, stats) {
    renderStats(stats);
    if (!daily || !daily.length) {
      if (subEl) subEl.textContent = "暂无学习计划";
      if (daysEl) daysEl.innerHTML = emptyHtml();
      if (miniEl) miniEl.innerHTML = "";
      return;
    }
    if (subEl) subEl.textContent = daily.length + " 天野外实习 · 威海";
    if (daysEl) daysEl.innerHTML = daily.map(dayBlockHtml).join("");
    if (miniEl) {
      miniEl.innerHTML = daily.map(function (d, i) {
        return miniRowHtml(d, i) + (i < daily.length - 1 ? '<div class="gm-hairline mx-4"></div>' : "");
      }).join("");
    }
    if (window.lucide) lucide.createIcons();
  }

  async function load() {
    const user = window.GeoMate && GeoMate.currentUser();
    if (!user) {
      location.href = "./login.html";
      return;
    }
    try {
      const [daily, stats] = await Promise.all([
        GeoMate.getDailyPlans(user.id),
        GeoMate.getPlanStats(user.id).catch(function () { return null; }),
      ]);
      render(daily || [], stats);
    } catch (e) {
      console.error("加载学习计划失败:", e);
      if (daysEl) daysEl.innerHTML = emptyHtml();
    }
  }

  // ── 点击任务行：切换完成状态 ──
  if (daysEl) {
    daysEl.addEventListener("click", function (e) {
      const row = e.target.closest("[data-plan-id]");
      if (!row) return;
      const id = row.getAttribute("data-plan-id");
      GeoMate.togglePlan(id)
        .then(load)
        .catch(function (err) {
          console.error("更新计划状态失败:", err);
        });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
