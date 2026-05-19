"""
Base agent — Claude tool-use loop with prompt caching.
All 5 agents inherit from this.
"""
from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Any

from anthropic import APIConnectionError, APIStatusError, RateLimitError
from anthropic.types import Message
from config.settings import claude_client, AGENT_MODELS
from agents.tools import execute_tool
from loguru import logger


class AgentResult:
    def __init__(self, agent_name: str, asset_id: str | None,
                 summary: str, full_reasoning: str, actions_taken: list[dict]):
        self.agent_name   = agent_name
        self.asset_id     = asset_id
        self.summary      = summary
        self.full_reasoning = full_reasoning
        self.actions_taken  = actions_taken
        self.timestamp    = datetime.now(timezone.utc)
        self.duration_s: float = 0.0

    def __str__(self):
        return f"[{self.agent_name}] {self.summary} ({len(self.actions_taken)} actions)"


class BaseAgent:

    name: str = "base_agent"
    role_title: str = "AI Agent"
    max_tool_rounds: int = 6

    def __init__(self, ctx: dict):
        """
        ctx must contain: ts_store, ev_store, wo_store, cep
        """
        self.ctx = {**ctx, "agent_name": self.name}
        self.model = AGENT_MODELS.get(self.name, "claude-sonnet-4-6")
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        raise NotImplementedError

    def _get_tools(self) -> list[dict]:
        raise NotImplementedError

    def _build_user_message(self, trigger: dict | None = None) -> str:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, trigger: dict | None = None) -> AgentResult:
        t0 = time.monotonic()
        logger.info(f"[{self.name}] Starting run")
        user_msg = self._build_user_message(trigger)
        result = self._run_tool_loop(user_msg)
        result.duration_s = round(time.monotonic() - t0, 2)
        logger.info(f"[{self.name}] Done in {result.duration_s}s — {result.summary[:80]}")
        return result

    # ------------------------------------------------------------------
    # Claude tool-use loop
    # ------------------------------------------------------------------

    def _run_tool_loop(self, user_message: str) -> AgentResult:
        messages = [{"role": "user", "content": user_message}]
        tools    = self._get_tools()
        actions: list[dict] = []
        all_texts: list[str] = []   # collect text from every round for full_reasoning

        for round_num in range(self.max_tool_rounds):
            response = self._call_claude(messages, tools)
            messages.append({"role": "assistant", "content": response.content})

            # Capture any text blocks in this round (reasoning, preamble, conclusions)
            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    all_texts.append(block.text.strip())

            if response.stop_reason != "tool_use":
                break

            # Execute all tool calls in this round
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                logger.debug(f"[{self.name}] Tool call: {block.name}({block.input})")
                tool_output = execute_tool(block.name, block.input, self.ctx)
                actions.append({"tool": block.name, "input": block.input, "output": tool_output})
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     tool_output,
                })

            messages.append({"role": "user", "content": tool_results})
        else:
            # max_tool_rounds exhausted without a final text response — ask for summary
            logger.warning(f"[{self.name}] max_tool_rounds exhausted — requesting summary")
            messages.append({"role": "user", "content": "Provide your final findings and recommendations now."})
            response = self._call_claude(messages, tools=[])   # no tools — force text response
            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    all_texts.append(block.text.strip())

        # Join all collected text blocks into one full reasoning string
        full_reasoning = "\n\n".join(all_texts)

        # Summarise: first 200 chars of full reasoning or last action count
        summary = (full_reasoning[:200].strip() if full_reasoning
                   else f"{len(actions)} tool calls executed")

        return AgentResult(
            agent_name=self.name,
            asset_id=None,
            summary=summary,
            full_reasoning=full_reasoning,
            actions_taken=actions,
        )

    # ------------------------------------------------------------------
    # Claude API call with caching + retry
    # ------------------------------------------------------------------

    def _call_claude(self, messages: list, tools: list) -> Message:
        kwargs: dict[str, Any] = {
            "model":      self.model,
            "max_tokens": 4096,
            "system": [
                {
                    "type": "text",
                    "text": self._system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        for attempt in range(3):
            try:
                return claude_client.messages.create(**kwargs)
            except RateLimitError:
                wait = 30 * (attempt + 1)
                logger.warning(f"[{self.name}] Rate limited — waiting {wait}s")
                time.sleep(wait)
            except APIConnectionError as e:
                logger.error(f"[{self.name}] Connection error: {e}")
                time.sleep(5)
            except APIStatusError as e:
                logger.error(f"[{self.name}] API error {e.status_code}: {e.message}")
                raise

        raise RuntimeError(f"[{self.name}] Failed after 3 attempts")
