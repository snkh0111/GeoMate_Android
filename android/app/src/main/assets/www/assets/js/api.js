/**
 * GeoMate Android — API Client
 * Connects to embedded backend at http://127.0.0.1:8000
 * Uses fetch() with standard JSON handling.
 * Endpoints aligned with backend_Android/app/api/v1/*
 */
(function () {
  "use strict";

  const BASE = "http://127.0.0.1:8000/api/v1";
  const USER_KEY = "geomate_user";

  // Restore session from localStorage
  let _userId = null;
  function loadUser() {
    try {
      const raw = localStorage.getItem(USER_KEY);
      if (raw) {
        const u = JSON.parse(raw);
        _userId = u.id || null;
        return u;
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  window.GeoMate = {
    // ── Config ──
    get baseUrl() { return BASE; },
    get userId() { return _userId; },
    setUserId(id) { _userId = id; },

    // ── Session ──
    currentUser() { return loadUser(); },
    saveUser(user) {
      _userId = user.id;
      localStorage.setItem(USER_KEY, JSON.stringify({
        id: user.id,
        username: user.username,
        display_name: user.display_name || user.username,
        email: user.email || "",
      }));
    },
    logout() {
      _userId = null;
      localStorage.removeItem(USER_KEY);
    },

    // ── HTTP helpers ──
    async _get(path) {
      const res = await fetch(BASE + path);
      if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
      return res.json();
    },
    async _post(path, body) {
      const res = await fetch(BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
      return res.json();
    },
    async _put(path, body) {
      const res = await fetch(BASE + path, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      if (!res.ok) throw new Error(`PUT ${path} → ${res.status}`);
      return res.json();
    },
    async _patch(path, body) {
      const res = await fetch(BASE + path, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`PATCH ${path} → ${res.status}`);
      return res.json();
    },
    async _delete(path) {
      const res = await fetch(BASE + path, { method: "DELETE" });
      if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`);
      return res.json();
    },

    // ── Health ──
    async health() {
      const res = await fetch("http://127.0.0.1:8000/health");
      return res.json();
    },

    // ── Users ──
    // 后端仅提供 register + me（开发模式 me 返回第一个用户）
    async register(username, password, email, displayName) {
      const data = await this._post("/users/register", {
        username, password,
        email: email || undefined,
        display_name: displayName || username,
      });
      this.saveUser(data);
      return data;
    },
    // 账号密码登录（后端校验 SHA-256）
    async login(username, password) {
      const data = await this._post("/users/login", { username, password });
      this.saveUser(data);
      return data;
    },

    // ── Documents ──
    async uploadDocument(userId, file) {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(BASE + `/documents/upload?user_id=${userId || _userId}`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `上传失败 (${res.status})`);
      }
      return res.json();
    },
    async listDocuments(userId) {
      return this._get(`/documents?user_id=${userId || _userId}`);
    },
    // 一键自动生成：解析 → 分析（无 Key 走规则）→ 路线 → 计划 → 知识库入库
    async autoGenerate(docId, userId) {
      const uid = userId || _userId;
      return this._post(`/documents/${docId}/auto-generate?user_id=${uid}`, {});
    },

    // ── Routes ──
    async getRoutes() {
      return this._get("/routes");
    },
    async getRoute(id) { return this._get(`/routes/${id}`); },
    async seedRoutes() { return this._post("/routes/seed", {}); },
    // ── Study Plans ──
    async getPlans(userId, date) {
      if (!userId) userId = _userId;
      let url = `/plans/?user_id=${userId}`;
      if (date) url += `&date=${date}`;
      return this._get(url);
    },
    async getDailyPlans(userId) {
      if (!userId) userId = _userId;
      return this._get(`/plans/daily?user_id=${userId}`);
    },
    async getPlanStats(userId) {
      if (!userId) userId = _userId;
      return this._get(`/plans/stats?user_id=${userId}`);
    },
    async togglePlan(planId) {
      return this._patch(`/plans/${planId}/toggle`, {});
    },
    async updatePlan(planId, data) {
      return this._put(`/plans/${planId}`, data);
    },
    async deletePlan(planId) {
      return this._delete(`/plans/${planId}`);
    },
    // 新建一条学习计划（"加入学习计划"按钮使用）
    async addPlan(userId, data) {
      if (!userId) userId = _userId;
      return this._post("/plans/", { user_id: userId, ...data });
    },
    async seedPlans(userId) {
      return this._post(`/plans/seed?user_id=${userId || _userId}`, {});
    },

    // ── Field Notes ──
    async getNotes(userId) {
      if (!userId) userId = _userId;
      return this._get(`/notes/?user_id=${userId}`);
    },
    async createNote(userId, data) {
      if (!userId) userId = _userId;
      return this._post("/notes/", { user_id: userId, ...data });
    },
    async updateNote(noteId, data) {
      return this._put(`/notes/${noteId}`, data);
    },
    async deleteNote(noteId) {
      return this._delete(`/notes/${noteId}`);
    },
    async seedNotes(userId) {
      return this._post(`/notes/seed?user_id=${userId || _userId}`, {});
    },

    // ── Knowledge ──
    async getKnowledgeStats() {
      return this._get("/knowledge/stats");
    },
    async getKnowledgeDocuments() {
      return this._get("/knowledge/documents");
    },
    async uploadKnowledge(file) {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(BASE + "/knowledge/upload", { method: "POST", body: fd });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `上传失败 (${res.status})`);
      }
      return res.json();
    },
    async searchKnowledge(q, filters) {
      const body = { query: q, top_k: 10, ...filters };
      return this._post("/knowledge/search", body);
    },
    async getKnowledgeFilters() {
      return this._get("/knowledge/filters");
    },
    async deleteKnowledgeDocument(docId) {
      return this._delete(`/knowledge/documents/${docId}`);
    },

    // ── AI Chat（SSE 流式，与后端 /intelligence/chat 对齐）──
    async getTutorStream(message, history) {
      const res = await fetch(BASE + "/intelligence/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history: history || [] }),
      });
      return res;
    },
  };
})();
