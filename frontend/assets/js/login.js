/**
 * GeoMate — 登录 / 注册页逻辑
 * 先探测后端健康，再允许登录/注册；成功后保存会话并进入首页。
 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  let mode = "login"; // login | register
  let backendReady = false;

  function setMode(m) {
    mode = m;
    $("#seg-login").classList.toggle("active", m === "login");
    $("#seg-register").classList.toggle("active", m === "register");
    $("#row-display").style.display = m === "register" ? "" : "none";
    $("#auth-submit").textContent = m === "register" ? "注 册" : "登 录";
    setError("");
  }

  function setError(msg) {
    $("#auth-error").textContent = msg || "";
  }

  function setStatus(text) {
    $("#backend-status").textContent = text;
  }

  // ── Backend probe (retry for cold start) ──
  async function waitBackend(maxRetries = 20, intervalMs = 700) {
    for (let i = 1; i <= maxRetries; i++) {
      try {
        await GeoMate.health();
        backendReady = true;
        setStatus("服务已就绪");
        return true;
      } catch (e) {
        setStatus(`正在连接服务 (${i}/${maxRetries})...`);
        await new Promise((r) => setTimeout(r, intervalMs));
      }
    }
    backendReady = false;
    setStatus("后端未启动，请检查内嵌服务");
    return false;
  }

  // ── Submit ──
  async function onSubmit(e) {
    e.preventDefault();

    const username = $("#f-username").value.trim();
    const password = $("#f-password").value;

    if (!username || !password) {
      setError("请输入用户名和密码");
      return;
    }
    if (mode === "register" && password.length < 4) {
      setError("密码至少 4 位");
      return;
    }
    if (!backendReady) {
      setError("服务未就绪，请稍候重试");
      return;
    }

    const btn = $("#auth-submit");
    btn.disabled = true;
    btn.textContent = mode === "register" ? "注册中..." : "登录中...";
    setError("");

    try {
      let user;
      if (mode === "register") {
        const display = $("#f-display").value.trim();
        user = await GeoMate.register(username, password, "", display);
      } else {
        user = await GeoMate.login(username, password);
      }
      GeoMate.saveUser(user);
      setStatus("登录成功，正在进入...");
      location.href = "./home.html";
    } catch (err) {
      setError(err.message || "操作失败，请重试");
      btn.disabled = false;
      btn.textContent = mode === "register" ? "注 册" : "登 录";
    }
  }

  // ── Init ──
  function init() {
    // 已登录则直接进入首页
    if (GeoMate.currentUser()) {
      location.href = "./home.html";
      return;
    }

    $("#seg-login").addEventListener("click", () => setMode("login"));
    $("#seg-register").addEventListener("click", () => setMode("register"));
    $("#auth-form").addEventListener("submit", onSubmit);

    waitBackend().then((ok) => {
      if (!ok) setError("无法连接后端服务");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
