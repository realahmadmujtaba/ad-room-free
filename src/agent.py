"""The ADK agent. Built natively on the Agent Development Kit, as the hackathon
resources recommend, rather than a third-party wrapper library."""
import asyncio

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import errors as genai_errors
from google.genai import types

import config
import retry
import tools

APP_NAME = "script_breakdown"

INSTRUCTION = """You are the AD Room — an assistant First Assistant Director for a
film production. A screenplay has already been broken down scene by scene and
stored in a production database. You answer questions by querying it with your tools.

How to work:
- Never guess. If a question touches scenes, cast, elements, scheduling or risk,
  call a tool. Numbers you state must come from a tool result.
- Start with project_overview when a question is broad or when you need context.
- Chain tools when it helps. "Can we shoot the diner in two days?" needs the
  scene search AND the schedule builder.
- Answer the way a working AD talks: scene numbers, page counts in eighths,
  set names, and what it means for the day. Short, concrete, no hedging.
- Lead with the answer, then the supporting detail. Use a compact table when
  listing more than three scenes.
- If a tool returns nothing, say so plainly and suggest what would find it instead.
- When you spot something that will hurt the schedule or the budget, flag it
  even if you weren't asked.
"""

def _make_agent(model: str) -> Agent:
    return Agent(
        name="ad_room",
        model=model,
        description="Answers scheduling, breakdown and production-risk questions about a screenplay.",
        instruction=INSTRUCTION,
        tools=tools.ALL_TOOLS,
    )


root_agent = _make_agent(config.MODEL_PRO)

_session_service = InMemorySessionService()
_runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=_session_service)

# Only used when MODEL_PRO exhausts its own retries on a 429/503 — a lighter
# model on a different capacity pool that often stays up when the primary is
# overloaded. Shares the same session service/id so it can pick up mid-chat.
_fallback_runner = None
if config.MODEL_FALLBACK and config.MODEL_FALLBACK != config.MODEL_PRO:
    _fallback_runner = Runner(
        agent=_make_agent(config.MODEL_FALLBACK),
        app_name=APP_NAME,
        session_service=_session_service,
    )


async def _ensure_session(user_id: str, session_id: str) -> None:
    existing = await _session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if existing is None:
        await _session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )


async def _run_once(runner: Runner, user_id: str, session_id: str, message: "types.Content") -> dict:
    answer_parts: list[str] = []
    tool_calls: list[str] = []

    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "function_call", None):
                    tool_calls.append(part.function_call.name)
        if event.is_final_response() and event.content and event.content.parts:
            answer_parts.append(
                "".join(p.text or "" for p in event.content.parts)
            )

    return {"answer": "\n".join(answer_parts).strip(), "tools_used": tool_calls}


async def ask_async(question: str, user_id: str = "demo", session_id: str = "s1") -> dict:
    await _ensure_session(user_id, session_id)
    message = types.Content(role="user", parts=[types.Part(text=question)])
    try:
        return await retry.call_async_with_retry(_run_once, _runner, user_id, session_id, message)
    except genai_errors.APIError as exc:
        if _fallback_runner is not None and retry.is_retryable(exc):
            return await retry.call_async_with_retry(
                _run_once, _fallback_runner, user_id, session_id, message
            )
        raise


def ask(question: str, user_id: str = "demo", session_id: str = "s1") -> dict:
    """Synchronous wrapper so Streamlit can call the agent directly."""
    return asyncio.run(ask_async(question, user_id, session_id))


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "Give me the overview and the three biggest risks."
    result = ask(q)
    print(f"[tools: {', '.join(result['tools_used']) or 'none'}]\n")
    print(result["answer"])
