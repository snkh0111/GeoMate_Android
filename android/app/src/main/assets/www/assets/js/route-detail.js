/**
 * GeoMate Android — 路线详情页动态加载
 * 根据 URL ?name= 参数从后端拉取对应路线数据并填充页面
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

  function displayDifficulty(v) { return DIFFICULTY_MAP[v] || v; }
  function displayType(v) { return TYPE_MAP[v] || v; }

  function el(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstChild;
  }

  async function loadRoute() {
    const name = GeoMateNav.getParam("name");
    if (!name) {
      console.log("无路线名参数，显示默认内容");
      return;
    }

    try {
      // 从后端获取全部路线
      const res = await fetch("http://127.0.0.1:8000/api/v1/routes/?page=1&size=50");
      const data = await res.json();
      const routes = data.routes || data.items || [];
      const route = routes.find((r) => r.name === name);

      if (!route) {
        console.warn("未找到路线:", name);
        return;
      }

      // 1. 信息头
      const orderIdx = route.order_index != null ? route.order_index : (route.id || 1);
      $("route-chip").textContent = "路线 " + String(orderIdx).padStart(2, "0");
      $("route-name").textContent = route.name;
      $("route-location").textContent = route.location || "";
      $("route-difficulty").textContent = displayDifficulty(route.difficulty || "");
      $("route-duration").textContent = route.duration_hours || "";
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
                <span class="text-[14px] text-foreground">${o}</span>
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
                <span class="text-[14px] text-foreground">${text}</span>
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
                <span class="text-[14px] text-foreground">${p}</span>
              </li>`
          )
          .join("");
      }

      // 6. 所需工具
      const tools = route.required_tools || [];
      if (tools.length) {
        $("route-tools").innerHTML = tools
          .map((t) => `<span class="gm-chip">${t}</span>`)
          .join("");
      }

      // 重新渲染 lucide 图标
      if (window.lucide) lucide.createIcons();

      console.log("路线详情已加载:", route.name);
    } catch (e) {
      console.error("加载路线详情失败:", e);
    }
  }

  // 页面加载后执行
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadRoute);
  } else {
    loadRoute();
  }
})();
