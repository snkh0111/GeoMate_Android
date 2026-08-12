/**
 * GeoMate Android — 路线详情页动态加载
 * 优先用 URL ?id= 从后端 GET /routes/{id} 拉取真实数据；
 * 无 id 时回退 ?name= 匹配（清洗序号前缀后比对）。
 * "加入学习计划"按钮：真实调用 POST /plans/ 创建一条预习任务。
 */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  // 枚举值 → 中文显示映射
  const DIFFICULTY_MAP = { easy: "较易", medium: "中等", hard: "较难" };
  const TYPE_MAP = {
    igneous: "岩浆岩",
    sedimentary: "沉积岩",
    metamorphic: "变质岩",
    composite: "综合",
    coastal: "海岸地貌",
  };

  function displayDifficulty(v) { return DIFFICULTY_MAP[v] || v || "中等"; }
  function displayType(v) { return TYPE_MAP[v] || v || "综合"; }

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

  function el(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstChild;
  }

  function fillRoute(route) {
    // 1. 信息头
    const orderIdx = route.order_index != null ? route.order_index : (route.id || 1);
    $("route-chip").textContent = "路线 " + String(orderIdx).padStart(2, "0");
    $("route-name").textContent = cleanName(route.name);
    $("route-location").textContent = route.location || "";
    $("route-difficulty").textContent = displayDifficulty(route.difficulty || "");
    $("route-duration").textContent = route.duration_hours != null ? route.duration_hours : "-";
    $("route-type").textContent = displayType(route.geological_type || "");

    // 2. 简介
    $("route-desc").textContent = route.description || "";

    // 3. 教学目标
    const objectives = route.learning_objectives || [];
    if (objectives.length) {
      $("route-objectives").innerHTML = objectives
        .map(
          (o, i) =>
            `<li class="list-row flex items-center gap-3">
              <span class="obj-num rounded-full bg-primary-soft text-primary text-[13px] font-semibold inline-flex items-center justify-center">${i + 1}</span>
              <span class="text-[14px] text-foreground">${escapeHtml(o)}</span>
            </li>`
        )
        .join("");
    }

    // 4. 关键观察点（key_points 是 {text, image_url} 对象数组）
    const keyPoints = route.key_points || [];
    if (keyPoints.length) {
      $("route-keypoints").innerHTML = keyPoints
        .map((k) => {
          const text = typeof k === "string" ? k : (k.text || k.name || "");
          return `<li class="list-row flex items-start gap-2.5">
              <i data-lucide="check" class="w-4 h-4 mt-[3px] text-primary flex-shrink-0"></i>
              <span class="text-[14px] text-foreground">${escapeHtml(text)}</span>
            </li>`;
        })
        .join("");
    }

    // 5. 注意事项
    const precautions = route.precautions || [];
    if (precautions.length) {
      $("route-precautions").innerHTML = precautions
        .map(
          (p) =>
            `<li class="list-row flex items-start gap-2.5">
              <i data-lucide="alert-circle" class="w-4 h-4 mt-[3px] text-state-warning flex-shrink-0"></i>
              <span class="text-[14px] text-foreground">${escapeHtml(p)}</span>
            </li>`
        )
        .join("");
    }

    // 6. 所需工具
    const tools = route.required_tools || [];
    if (tools.length) {
      $("route-tools").innerHTML = tools
        .map((t) => `<span class="gm-chip">${escapeHtml(t)}</span>`)
        .join("");
    }

    // 重新渲染 lucide 图标
    if (window.lucide) lucide.createIcons();

    console.log("路线详情已加载:", route.name);
    return route;
  }

  async function loadById(id) {
    const route = await GeoMate.getRoute(Number(id));
    return fillRoute(route);
  }

  async function loadByName(name) {
    const data = await GeoMate.getRoutes();
    const routes = (data && data.items) || [];
    const wanted = cleanName(name);
    const route = routes.find(function (r) { return cleanName(r.name) === wanted; })
      || routes.find(function (r) { return cleanName(r.name).indexOf(wanted) >= 0 || wanted.indexOf(cleanName(r.name)) >= 0; });
    if (!route) throw new Error("未找到路线:" + name);
    return fillRoute(route);
  }

  // ── 加入学习计划 ──
  function bindJoinPlan(route) {
    const btn = document.querySelector('[data-dom-id="btn-plan"]');
    if (!btn || !route) return;
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (btn.dataset.added === "1") return;

      const user = window.GeoMate && GeoMate.currentUser();
      if (!user) {
        location.href = "./login.html";
        return;
      }
      const today = new Date();
      const dateStr = today.getFullYear() + "-"
        + String(today.getMonth() + 1).padStart(2, "0") + "-"
        + String(today.getDate()).padStart(2, "0");

      btn.disabled = true;
      btn.textContent = "加入中...";
      GeoMate.addPlan(user.id, {
        date: dateStr,
        task_name: "预习路线：" + cleanName(route.name),
        content: (route.location || "") + " — " + cleanName(route.name),
        category: "路线复习",
        priority: "medium",
        route_id: route.id,
      }).then(function () {
        btn.dataset.added = "1";
        btn.textContent = "已加入学习计划 ✓";
        const hint = document.querySelector('section [class*="text-ink-3"] p, p');
        console.log("已加入今日学习计划");
      }).catch(function (err) {
        console.error("加入计划失败:", err);
        btn.disabled = false;
        btn.textContent = "加入学习计划";
        alert("加入计划失败：" + ((err && err.message) || "网络错误"));
      });
    });
  }

  async function loadRoute() {
    const params = new URLSearchParams(location.search);
    const id = params.get("id");
    const name = params.get("name");
    let route = null;

    try {
      if (id) {
        route = await loadById(id);
      } else if (name) {
        route = await loadByName(name);
      } else {
        console.log("无路线参数，显示默认内容");
      }
    } catch (e) {
      console.error("加载路线详情失败:", e);
    }

    bindJoinPlan(route);
  }

  // 页面加载后执行
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadRoute);
  } else {
    loadRoute();
  }
})();
