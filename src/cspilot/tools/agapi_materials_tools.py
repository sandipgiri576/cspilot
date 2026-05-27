from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv


def agapi_materials_query(query: str, render_html: bool = False) -> dict[str, Any]:
    """Query optional AGAPI materials capabilities when the package is installed."""
    load_dotenv(".env.cspilot")
    try:
        from agapi.agents import AGAPIAgent
    except ImportError:
        return {
            "success": False,
            "query": query,
            "error": "AGAPIAgent is unavailable; install the optional agapi package.",
            "source": "AGAPI",
        }

    api_key = os.getenv("AGAPI_API_KEY")
    if not api_key:
        return {
            "success": False,
            "query": query,
            "error": "AGAPI_API_KEY is not configured.",
            "source": "AGAPI",
        }

    try:
        result = AGAPIAgent(api_key=api_key).query_sync(query, render_html=render_html)
    except Exception as exc:
        return {
            "success": False,
            "query": query,
            "error": f"AGAPI query failed: {exc}",
            "source": "AGAPI",
        }

    # AGAPIAgent displays rendered HTML in notebook contexts but returns its
    # response envelope, rather than the generated HTML markup.
    html = None
    text = str(result) if result is not None else None
    return {
        "success": True,
        "query": query,
        "html": html,
        "text": text,
        "source": "AGAPI",
    }
