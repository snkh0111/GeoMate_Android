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
    const act = `<button type="button" class="task-del" data-plan-edit="${task.id}" aria-label="编辑任务">
      <i data-lucide="pencil" class="w-4 h-4"></i>
    </button><button type="button" class="task-del" data-plan-del="${task.id}" aria-label="删除任务">
      <i data-lucide="trash-2" class="w-4 h-4"></i>
    </button>`;
    return `<div class="gm-task-row" data-plan-id="${task.id}">${check}${text}${cat}${act}</div>`;
  }

  // ── 行内编辑态 ──
  function editRowHtml(task) {
    return `<div class="gm-task-row gm-task-row-edit" data-plan-id="${task.id}">
      <div class="plan-edit-fields">
        <input type="text" class="gm-input plan-edit-name" value="${escapeHtml(task.task_name)}" placeholder="任务名称" aria-label="任务名称">
        <input type="text" class="gm-input plan-edit-cat" value="${escapeHtml(task.category || "")}" placeholder="分类（可选）" aria-label="任务分类">
      </div>
      <div class="plan-edit-actions">
        <button type="button" class="gm-btn-ghost-sm" data-plan-edit-save="${task.id}">保存</button>
        <button type="button" class="gm-btn-ghost-sm" data-plan-edit-cancel>取消</button>
      </div>
    </div>`;
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
      lastDaily = daily || [];
      render(lastDaily, stats);
    } catch (e) {
      console.error("加载学习计划失败:", e);
      if (daysEl) daysEl.innerHTML = emptyHtml();
    }
  }

  // ── 点击任务行：切换完成状态；编辑/删除按钮：行内编辑或删除 ──
  let lastDaily = null;

  // 行内编辑：把任务行替换为编辑态
  function startEdit(planId) {
    const daily = lastDaily || [];
    let task = null;
    daily.forEach(function (d) {
      (d.items || []).forEach(function (t) { if (String(t.id) === String(planId)) task = t; });
    });
    if (!task) return;
    const row = daysEl.querySelector('[data-plan-id="' + planId + '"]');
    if (!row) return;
    row.outerHTML = editRowHtml(task);
    if (window.lucide) lucide.createIcons();
  }

  // 保存行内编辑
  function saveEdit(planId, nameInput, catInput) {
    const data = {};
    if (nameInput && nameInput.value.trim()) data.task_name = nameInput.value.trim();
    if (catInput && catInput.value.trim()) data.category = catInput.value.trim();
    if (!data.task_name && !data.category) { data.task_name = "未命名任务"; }
    GeoMate.updatePlan(planId, data)
      .then(load)
      .catch(function (err) {
        console.error("更新任务失败:", err);
        alert("保存失败：" + ((err && err.message) || "网络错误"));
      });
  }

  if (daysEl) {
    daysEl.addEventListener("click", function (e) {
      // 保存
      const saveBtn = e.target.closest("[data-plan-edit-save]");
      if (saveBtn) {
        e.stopPropagation();
        const id = saveBtn.getAttribute("data-plan-edit-save");
        const row = saveBtn.closest(".gm-task-row-edit");
        const nameInput = row && row.querySelector(".plan-edit-name");
        const catInput = row && row.querySelector(".plan-edit-cat");
        saveEdit(id, nameInput, catInput);
        return;
      }
      // 取消
      const cancelBtn = e.target.closest("[data-plan-edit-cancel]");
      if (cancelBtn) {
        e.stopPropagation();
        load();
        return;
      }
      // 编辑
      const editBtn = e.target.closest("[data-plan-edit]");
      if (editBtn) {
        e.stopPropagation();
        startEdit(editBtn.getAttribute("data-plan-edit"));
        return;
      }
      // 删除
      const delBtn = e.target.closest("[data-plan-del]");
      if (delBtn) {
        e.stopPropagation();
        const id = delBtn.getAttribute("data-plan-del");
        if (!window.confirm("确定删除这项学习任务吗？")) return;
        GeoMate.deletePlan(id)
          .then(load)
          .catch(function (err) {
            console.error("删除任务失败:", err);
            alert("删除失败：" + ((err && err.message) || "网络错误"));
          });
        return;
      }
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
