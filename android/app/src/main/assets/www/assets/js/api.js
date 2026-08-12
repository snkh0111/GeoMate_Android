/**
 * GeoMate Android — API Client
 * Connects to embedded backend at http://127.0.0.1:8000
 * Uses fetch() with standard JSON handling.
 */
(function () {
  "use strict";

  const BASE = "http://127.0.0.1:8000/api/v1";
  let _userId = null;

  window.GeoMate = {
    // ── Config ──
    get baseUrl() { return BASE; },
    get userId() { return _userId; },
    setUserId(id) { _userId = id; },

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
    async register(username, email, password, displayName) {
      _userId = null;
      const data = await this._post("/users/register", {
        username, email, password,
        display_name: displayName || username,
      });
      _userId = data.id;
      return data;
    },

    // ── Routes ──
    async getRoutes(page = 1, size = 20) {
      return this._get(`/routes/?page=${page}&size=${size}`);
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
    async seedPlans(userId) {
      return this._post(`/plans/seed?user_id=${userId || _userId}`, {});
    },

    // ── Field Notes ──
    async getNotes(userId, page = 1, size = 20) {
      if (!userId) userId = _userId;
      return this._get(`/notes/?user_id=${userId}&page=${page}&size=${size}`);
    },
    async seedNotes(userId) {
      return this._post(`/notes/seed?user_id=${userId || _userId}`, {});
    },

    // ── Knowledge ──
    async getKnowledgeStats() {
      return this._get("/knowledge/stats");
    },
    async searchKnowledge(q, filters) {
      const body = { query: q, top_k: 10, ...filters };
      return this._post("/knowledge/search", body);
    },
    async getKnowledgeFilters() {
      return this._get("/knowledge/filters");
    },

    // ── AI Chat ──
    async getTutorStream(message, history) {
      const res = await fetch(BASE + "/intelligence/tutor/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history: history || [] }),
      });
      return res;
    },
  };
})();
