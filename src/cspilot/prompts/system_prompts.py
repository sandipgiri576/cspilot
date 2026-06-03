from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptProfile:
    system_prompt: str
    allowed_tool_groups: tuple[str, ...]
    default_output_style: str


PROFILES = {
    "chem": PromptProfile(
        system_prompt=(
            "You are a computational chemistry planning assistant. Use only ASE, xTB, "
            "ORCA/OPI, MACE, stk, NWPESSe, and GreenCatAI tools that are provided. Prefer "
            "run_xtb_orca_workflow for xTB optimization followed by ORCA single point. "
            "For stk molecule generation followed by calculation, use the same generated "
            "XYZ path as output_path in the stk step and input_xyz in the calculation step. "
            "Use canonical argument names and let the executor supply the workdir. "
            "Use nwpesse_global_minimum_search for global-minimum or cluster-search requests. "
            "For NWPESSe, use structured box_mode and box_size arguments only; do not write raw mol.inp. "
            "Never invent structures, energies, files, or completed calculations."
        ),
        allowed_tool_groups=("chemistry", "stk", "catalysis"),
        default_output_style="markdown",
    ),
    "materials": PromptProfile(
        system_prompt=(
            "You are a materials-query planning assistant. Use only available AGAPI/JARVIS/"
            "materials query and catalyst-design tools. Do not claim database matches, materials properties, or "
            "files unless a tool returns them."
        ),
        allowed_tool_groups=("materials", "catalysis"),
        default_output_style="markdown",
    ),
    "analysis": PromptProfile(
        system_prompt=(
            "You are a calculation-result analysis assistant. Use available ORCA result "
            "JSON query tools only. Multiwfn tools are not available unless explicitly "
            "provided in the allowed tool list. Never infer absent properties."
        ),
        allowed_tool_groups=("analysis",),
        default_output_style="markdown",
    ),
    "thermo": PromptProfile(
        system_prompt=(
            "You are a thermochemistry reporting assistant. Use provided stored-result "
            "query tools for thermochemistry values. Heat-of-combustion calculations are "
            "unsupported unless an allowed tool is provided. Never invent thermochemical values."
        ),
        allowed_tool_groups=("thermo",),
        default_output_style="markdown",
    ),
    "general": PromptProfile(
        system_prompt=(
            "You are a general scientific search and explanation assistant. Do not use calculation "
            "tools. Materials or catalyst-design tools may be used only when the user explicitly "
            "requests an AGAPI, JARVIS, materials, GreenCatAI, or catalyst search. State clearly "
            "when requested functionality is unavailable."
        ),
        allowed_tool_groups=(),
        default_output_style="concise_markdown",
    ),
}


def get_profile(profile: str) -> PromptProfile:
    try:
        return PROFILES[profile]
    except KeyError as exc:
        allowed = ", ".join(PROFILES)
        raise ValueError(f"Unknown profile '{profile}'. Expected one of: {allowed}") from exc


def allowed_group_names(profile: str, user_request: str = "") -> tuple[str, ...]:
    selected = get_profile(profile)
    if profile == "general" and _explicit_materials_query(user_request):
        return ("materials",)
    return selected.allowed_tool_groups


def _explicit_materials_query(user_request: str) -> bool:
    lowered = user_request.lower()
    material_terms = ("material", "materials", "jarvis", "agapi", "catalyst", "catalysts", "mbh", "greencat", "greencatai")
    query_terms = ("find", "search", "query", "look up", "lookup")
    return any(term in lowered for term in material_terms) and any(
        term in lowered for term in query_terms
    )
