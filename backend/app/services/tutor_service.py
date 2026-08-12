"""AI Tutor Service — RAG-powered geology teaching assistant.

Orchestrates: user query → knowledge base search → LLM with context → streaming response.
Falls back to knowledge search results when no Anthropic API key is configured.
"""

import json
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import chat_json_stream
from app.ai.prompts.tutor import TUTOR_SYSTEM_PROMPT, TUTOR_WITH_CONTEXT_PROMPT
from app.config import settings
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 3000
DEFAULT_MODEL = "claude-sonnet-5-20251001"


class TutorService:
    """Handles AI tutor conversations with RAG augmentation."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.knowledge = KnowledgeService(db)

    # ── API key check ────────────────────────────────────────

    def _get_api_key(self, api_key: str | None = None) -> str | None:
        """Resolve the effective API key. Returns None if no key available."""
        key = api_key or settings.ANTHROPIC_API_KEY
        if not key or key == "your-api-key-here":
            return None
        return key

    # ── Search context ───────────────────────────────────────

    async def _search_context(self, query: str) -> str:
        """Search knowledge base and format results as context string."""
        try:
            response = await self.knowledge.search(
                query=query, top_k=3, auto_filter=True,
            )
            results = response.results
            if not results:
                return ""

            parts = []
            total_chars = 0
            for r in results:
                snippet = r.content[:800]
                header = f"【来源：{r.document_title or '未知文档'}】"
                if r.section_title:
                    header += f" — {r.section_title}"
                if r.category:
                    header += f" [{r.category}]"
                part = f"{header}\n{snippet}"
                if total_chars + len(part) > MAX_CONTEXT_CHARS:
                    remaining = MAX_CONTEXT_CHARS - total_chars
                    if remaining > 100:
                        parts.append(f"{header}\n{snippet[:remaining]}...")
                    break
                parts.append(part)
                total_chars += len(part)

            return "\n\n---\n\n".join(parts)
        except Exception as e:
            logger.warning("Knowledge search failed for tutor: %s", e)
            return ""

    # ── Build conversation ───────────────────────────────────

    def _build_messages(
        self,
        user_message: str,
        history: list[dict] | None,
        context: str,
    ) -> list[dict]:
        """Build the messages array for the LLM call."""
        messages = []

        # Include recent history (last 6 turns = 12 messages max)
        if history:
            recent = history[-12:]
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        return messages

    # ── Streaming chat ───────────────────────────────────────

    async def chat_stream(
        self,
        message: str,
        history: list[dict] | None = None,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
    ) -> AsyncGenerator[str, None]:
        """Stream an AI tutor response with RAG context.

        Yields SSE-formatted strings: "data: {json}\n\n"
        Ends with "data: [DONE]\n\n"
        """
        key = self._get_api_key(api_key)

        if key is None:
            # No API key → fall back to knowledge search formatted as teaching
            async for chunk in self._fallback_response(message):
                yield chunk
            return

        # Search knowledge base for context
        context = await self._search_context(message)

        # Build system prompt
        if context:
            system_prompt = TUTOR_WITH_CONTEXT_PROMPT.format(context=context)
        else:
            system_prompt = TUTOR_SYSTEM_PROMPT

        # Build conversation messages
        messages = self._build_messages(message, history, context)

        # Build user message with context indicator
        user_content = message

        logger.info(
            "Tutor chat: model=%s history_turns=%d context_chars=%d",
            model, len(history or []), len(context),
        )

        try:
            async for text_chunk in chat_json_stream(
                system_prompt=system_prompt,
                user_message=user_content,
                model=model,
                max_tokens=2048,
                temperature=0.7,
                api_key=key,
            ):
                yield f"data: {json.dumps({'content': text_chunk, 'type': 'llm'})}\n\n"
        except Exception as e:
            logger.exception("LLM call failed in tutor chat")
            yield f"data: {json.dumps({'error': f'AI 服务暂时不可用: {str(e)}', 'type': 'error'})}\n\n"

        yield "data: [DONE]\n\n"

    # ── Fallback: knowledge-based response (no API key) ──────

    async def _fallback_response(self, message: str) -> AsyncGenerator[str, None]:
        """Generate a teaching-style response from knowledge base only."""
        context = await self._search_context(message)

        yield f"data: {json.dumps({'type': 'meta', 'mode': 'knowledge'})}\n\n"

        if context:
            intro = (
                "💡 **知识库检索结果**（未配置 AI 大模型，以下是基于知识库的回答）：\n\n"
                "---\n\n"
            )
            yield f"data: {json.dumps({'content': intro, 'type': 'text'})}\n\n"

            # Stream context in chunks to simulate real response
            yield f"data: {json.dumps({'content': context, 'type': 'text'})}\n\n"

            footer = (
                "\n\n---\n\n"
                "> ⚡ **提示**：配置 Anthropic API Key 后，我可以像老师一样用教学口吻为你详细讲解。\n"
                "> 在 `backend/.env` 中设置 `ANTHROPIC_API_KEY=sk-ant-...` 即可启用 AI 助教模式。"
            )
            yield f"data: {json.dumps({'content': footer, 'type': 'text'})}\n\n"
        else:
            no_result = (
                "抱歉，知识库中没有找到相关内容，而且 AI 大模型也未配置。\n\n"
                "你可以尝试：\n"
                "· 使用更具体的地质术语提问（如「花岗岩怎么鉴定」、「罗盘怎么用」）\n"
                "· 上传地质实习 PDF 资料到「知识中心」\n"
                "· 在 backend/.env 中配置 ANTHROPIC_API_KEY 启用 AI 助教\n\n"
                "如果配置了 API Key，我可以像真正的老师一样回答你的问题！"
            )
            yield f"data: {json.dumps({'content': no_result, 'type': 'text'})}\n\n"

        yield "data: [DONE]\n\n"
