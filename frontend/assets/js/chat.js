/**
 * GeoMate Android — 地质助手对话功能
 * 调用后端 SSE 流式接口 /api/v1/intelligence/tutor/stream
 */
(function () {
  "use strict";

  const flow = document.querySelector(".chat-flow");
  const input = document.querySelector('input[placeholder*="输入地质问题"]');
  const sendBtn = document.querySelector('button[aria-label="发送问题"]');
  let history = []; // 对话历史 [{role, content}]

  function addUserBubble(text) {
    const row = document.createElement("div");
    row.className = "msg-row msg-row--right";
    row.innerHTML = `<div class="chat-bubble max-w-[85%] bg-primary text-primary-foreground rounded-lg rounded-tr-sm px-4 py-3 text-[14px] leading-relaxed">${escapeHtml(text)}</div>`;
    flow.appendChild(row);
    scrollToBottom();
    return row;
  }

  function addBotBubble() {
    const row = document.createElement("div");
    row.className = "msg-row";
    row.innerHTML = `
      <div class="w-8 h-8 rounded-full bg-primary text-primary-foreground inline-flex items-center justify-center shrink-0" aria-hidden="true">
        <i data-lucide="bot" class="w-4 h-4"></i>
      </div>
      <div class="chat-bubble max-w-[85%] bg-card border border-border rounded-lg rounded-tl-sm px-4 py-3 text-[14px] leading-relaxed text-foreground">
        <p class="typing-dots">思考中<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></p>
      </div>`;
    flow.appendChild(row);
    if (window.lucide) lucide.createIcons();
    scrollToBottom();
    return row;
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function scrollToBottom() {
    window.scrollTo(0, document.body.scrollHeight);
  }

  async function sendMessage(text) {
    const message = (text || input.value || "").trim();
    if (!message) return;

    // 清空输入框
    input.value = "";
    addUserBubble(message);
    history.push({ role: "user", content: message });

    const botRow = addBotBubble();
    const botTextEl = botRow.querySelector("p");
    let fullAnswer = "";

    try {
      const res = await fetch(
        "http://127.0.0.1:8000/api/v1/intelligence/chat",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, history }),
        }
      );

      if (!res.ok) throw new Error("HTTP " + res.status);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // 按行解析 SSE
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) continue;
          const payload = trimmed.slice(5).trim();
          if (payload === "[DONE]") continue;

          try {
            const evt = JSON.parse(payload);
            // LLM 流式块与知识库 fallback 都带 content 字段
            if ((evt.type === "llm" || evt.type === "text") && evt.content) {
              fullAnswer += evt.content;
              botTextEl.textContent = fullAnswer;
              botTextEl.classList.remove("typing-dots");
              scrollToBottom();
            } else if (evt.type === "error") {
              botTextEl.textContent = "出错了：" + (evt.error || "未知错误");
              botTextEl.classList.remove("typing-dots");
            }
          } catch (e) {
            /* 忽略非 JSON 行 */
          }
        }
      }

      if (!fullAnswer) {
        botTextEl.textContent = "暂无回答，请稍后再试。";
        botTextEl.classList.remove("typing-dots");
      } else {
        history.push({ role: "assistant", content: fullAnswer });
      }
    } catch (e) {
      console.error("Chat failed:", e);
      botTextEl.textContent = "连接后端失败，请确认服务已启动。";
      botTextEl.classList.remove("typing-dots");
    }
  }

  // 绑定事件
  if (sendBtn) {
    sendBtn.addEventListener("click", function () { sendMessage(); });
  }
  if (input) {
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); sendMessage(); }
    });
  }

  // 建议问题按钮
  const chips = document.querySelectorAll('[aria-label="建议问题"] .gm-chip');
  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      sendMessage(chip.textContent.trim());
    });
  });
})();
