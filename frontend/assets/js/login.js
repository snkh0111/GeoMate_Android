/**
 * GeoMate — 登录 / 注册页逻辑
 * 后端（开发模式）仅提供 register 与 /users/me（返回当前/第一个用户）：
 * - 注册：POST /users/register
 * - 登录：GET /users/me（已注册用户直接进入；未注册则提示先注册）
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

  // ── Backend probe (retry for cold start; show real error via native bridge) ──
  async function waitBackend(maxRetries = 60, intervalMs = 1000) {
    for (let i = 1; i <= maxRetries; i++) {
      try {
        await GeoMate.health();
        backendReady = true;
        setStatus("服务已就绪");
        return true;
      } catch (e) {
        setStatus(`正在连接服务 (${i}/${maxRetries})...`);
        const err = backendError();
        if (err) {
          setStatus("后端启动失败：" + err);
          backendReady = false;
          return false;
        }
        await new Promise((r) => setTimeout(r, intervalMs));
      }
    }
    backendReady = false;
    const err = backendError();
    setStatus(err ? "后端启动失败：" + err : "后端未启动，请退出应用后重新打开");
    return false;
  }

  // 通过 Android 原生桥读取后端启动异常（仅 APK 内可用，浏览器中返回 null）
  function backendError() {
    try {
      if (typeof AndroidNative !== "undefined" && AndroidNative.getBackendError) {
        const e = AndroidNative.getBackendError();
        if (e && e.trim() && !e.startsWith("bridge_error")) return e.trim();
      }
    } catch (err) { /* ignore */ }
    return null;
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
    btn.textContent = mode === "register" ? "注册中..." : "进入中...";
    setError("");

    try {
      let user;
      if (mode === "register") {
        const display = $("#f-display").value.trim();
        user = await GeoMate.register(username, password, "", display);
      } else {
        // 账号密码登录（后端 POST /users/login 校验）
        user = await GeoMate.login(username, password);
      }
      GeoMate.saveUser(user);
      setStatus("登录成功，正在进入...");
      location.href = "./home.html";
    } catch (err) {
      const msg = (err && err.message) || "操作失败，请重试";
      if (mode === "login" && /404/.test(msg)) {
        setError("暂无用户，请先注册");
      } else if (mode === "login" && /401/.test(msg)) {
        setError("用户名或密码错误");
      } else {
        setError(msg);
      }
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
