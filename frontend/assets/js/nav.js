/**
 * GeoMate Android — 页面导航与交互
 * 处理 data-dom-id / data-nav-key 点击 → 跳转到对应页面
 * 路线卡片 → 路线详情页（携带路线名）
 */
(function () {
  "use strict";

  // DOM-ID → 页面 URL 映射
  const PAGE_MAP = {
    // 底部导航
    "nav-home": "home.html",
    "nav-routes": "routes.html",
    "nav-plans": "plans.html",
    "nav-knowledge": "knowledge.html",
    "nav-profile": "profile.html",
    // 首页入口
    "entry-plans": "plans.html",
    "entry-knowledge": "knowledge.html",
    "entry-notes": "notes.html",
    "entry-docs": "knowledge.html",
    "cta-ai-chat": "ai-chat.html",
    // 返回
    "back-home": "home.html",
    "back-routes": "routes.html",
    // 其他
    "btn-plan": "plans.html",
    "menu-notes": "notes.html",
    "menu-docs": "knowledge.html",
    "menu-ai-chat": "ai-chat.html",
  };

  const BASE = "./";

  function go(page, params) {
    let url = BASE + page;
    if (params) {
      const qs = new URLSearchParams(params).toString();
      url += "?" + qs;
    }
    location.href = url;
  }

  // 从当前 URL 读参数
  function getParam(key) {
    return new URLSearchParams(location.search).get(key);
  }

  // 路线详情跳转：从卡片提取路线名
  function routeCardClick(card) {
    // 路线名在卡片内第一个 <p> 标签
    const p = card.querySelector("p");
    const name = p ? p.textContent.trim() : "";
    go("route-detail.html", { name: name || "" });
  }

  // 绑定所有 data-dom-id 元素
  document.addEventListener("click", function (e) {
    const el = e.target.closest("[data-dom-id]");
    if (!el) return;
    const domId = el.getAttribute("data-dom-id");

    // 路线卡片特殊处理
    if (domId === "route-card") {
      e.preventDefault();
      routeCardClick(el);
      return;
    }

    // 其他映射
    const page = PAGE_MAP[domId];
    if (page) {
      e.preventDefault();
      go(page);
    }
  });

  // 绑定 data-nav-key 底部导航
  document.addEventListener("click", function (e) {
    const el = e.target.closest("[data-nav-key]");
    if (!el) return;
    const key = el.getAttribute("data-nav-key");
    const page = PAGE_MAP["nav-" + key];
    if (page) {
      e.preventDefault();
      go(page);
    }
  });

  // 暴露给其他脚本
  window.GeoMateNav = { go, getParam };

  // ── 登录守卫：未登录一律回到登录页 ──
  document.addEventListener("DOMContentLoaded", function () {
    try {
      if (window.GeoMate && !GeoMate.currentUser() && !/login\.html/.test(location.href)) {
        location.href = "./login.html";
      }
    } catch (e) { /* ignore */ }
  });
})();
