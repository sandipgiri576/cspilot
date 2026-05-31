from __future__ import annotations

from pathlib import Path
from typing import Any


def greencatai_design_mbh_catalysts(
    output_dir: str,
    search_space: str = "configs/search_space.json",
    scoring: str = "configs/scoring.json",
    library: str | None = None,
    max_candidates: int = 100,
    generations: int = 3,
    population_size: int = 30,
    top_n_xtb: int = 0,
    top_n_orca: int = 0,
) -> dict[str, Any]:
    """Call the public GreenCatAI catalyst-design API."""
    try:
        from greencatai.api import design_mbh_catalysts
    except ImportError:
        return {
            "success": False,
            "output_dir": output_dir,
            "error": "Python package not found: greencatai.",
            "source": "GreenCatAI",
        }

    kwargs: dict[str, Any] = {
        "search_space": search_space,
        "scoring": scoring,
        "output_dir": output_dir,
        "library": library,
        "max_candidates": max_candidates,
        "generations": generations,
        "population_size": population_size,
        "top_n_xtb": top_n_xtb,
        "top_n_orca": top_n_orca,
    }

    try:
        result = design_mbh_catalysts(**kwargs)
    except Exception as exc:
        return {
            "success": False,
            "output_dir": output_dir,
            "parameters": kwargs,
            "error": f"{type(exc).__name__}: {exc}",
            "source": "GreenCatAI",
        }

    payload = _jsonable(result)
    if isinstance(payload, dict):
        payload.setdefault("success", True)
        payload.setdefault("output_dir", str(Path(output_dir)))
        payload.setdefault("source", "GreenCatAI")
        return payload
    return {
        "success": True,
        "output_dir": str(Path(output_dir)),
        "result": payload,
        "source": "GreenCatAI",
    }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    if hasattr(value, "dict"):
        return _jsonable(value.dict())
    if hasattr(value, "__dict__"):
        return _jsonable(vars(value))
    return str(value)
