from __future__ import annotations

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from backend.agents.deepsearch.checkpointer import get_deepsearch_checkpointer
from backend.tools.tools import (
    document_page_ocr_tool,
    document_search_tool,
    web_search_temporal_tool,
)

_deepsearch_agent = None


def get_deepsearch_llm() -> ChatOpenAI:
    """Shared ChatOpenAI settings for the ReAct agent and the post-run handoff extractor.

    Returns:
        Configured chat model (gpt-5-mini, same options everywhere).
    """
    return ChatOpenAI(
        model="gpt-5-mini",
        reasoning={"effort": "medium"},
        temperature=0,
    )


def get_deepsearch_agent():
    """Return singleton DeepSearch LangGraph ReAct agent with Postgres checkpointer.

    Returns:
        Compiled agent (tools: document search and temporal web search).
    """
    global _deepsearch_agent
    if _deepsearch_agent is None:
        _deepsearch_agent = create_react_agent(
            model=get_deepsearch_llm(),
            tools=[document_search_tool, document_page_ocr_tool, web_search_temporal_tool],
            checkpointer=get_deepsearch_checkpointer(),
        )
    return _deepsearch_agent
