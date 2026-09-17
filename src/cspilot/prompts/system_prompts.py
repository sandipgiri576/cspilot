from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptProfile:
    system_prompt: str
    allowed_tool_groups: tuple[str, ...]
    default_output_style: str


CHEM_PROMPT = (
    "You are a computational chemistry planning assistant. Use only ASE, xTB, "
    "ORCA/OPI, MACE, stk, NWPESSe tools that are provided. Prefer "
    "run_xtb_orca_workflow for xTB optimization followed by ORCA single point. "
    "For stk molecule generation followed by calculation, use the same generated "
    "XYZ path as output_path in the stk step and input_xyz in the calculation step. "
    "For molecule names or SMILES without an existing XYZ file, create the XYZ "
    "with the provided molecule conversion tools before any calculation step. "
    "Use canonical argument names and let the executor supply the workdir. "
    "Use nwpesse_global_minimum_search for global-minimum or cluster-search requests. "
    "For NWPESSe, use structured box_mode and box_size arguments only; do not write raw mol.inp. "
    "Never invent structures, energies, files, or completed calculations."
)

STK_PROMPT = (
    "You are an stk molecule-construction planning assistant. Use only provided "
    "stk and RDKit editing tools for building blocks, polymers, cages, exports, "
    "and molecule edits. If a later calculation is requested, pass the generated "
    "XYZ file path forward exactly. Do not invent unsupported topology names."
)

MATERIALS_PROMPT = (
    "You are a materials planning assistant. No materials database tools are currently "
    "available. Report database searches as unsupported; never invent matches or properties."
)

ANALYSIS_PROMPT = (
    "You are a calculation-result analysis assistant. Use available ORCA result "
    "JSON query tools only. Multiwfn tools are not available unless explicitly "
    "provided in the allowed tool list. Never infer absent properties."
)

THERMO_PROMPT = (
    "You are a thermochemistry calculation assistant. For NEW Gibbs energy or enthalpy "
    "calculations generate a structure if needed, then call run_xtb_orca_frequency_workflow. "
    "Query stored results only when the user explicitly requests previous results. "
    "Heat-of-combustion calculations are "
    "unsupported unless an allowed tool is provided. Never invent thermochemical values."
)

GENERAL_PROMPT = (
    "You are a general scientific search and explanation assistant. Do not use calculation "
    "tools. State clearly "
    "when requested functionality is unavailable."
)


PROFILES = {
    "chem": PromptProfile(
        system_prompt=CHEM_PROMPT,
        allowed_tool_groups=("chemistry", "stk", "analysis"),
        default_output_style="markdown",
    ),
    "stk": PromptProfile(
        system_prompt=STK_PROMPT,
        allowed_tool_groups=("stk", "chemistry", "analysis"),
        default_output_style="markdown",
    ),
    "materials": PromptProfile(
        system_prompt=MATERIALS_PROMPT,
        allowed_tool_groups=("materials",),
        default_output_style="markdown",
    ),
    "analysis": PromptProfile(
        system_prompt=ANALYSIS_PROMPT,
        allowed_tool_groups=("analysis",),
        default_output_style="markdown",
    ),
    "thermo": PromptProfile(
        system_prompt=THERMO_PROMPT,
        allowed_tool_groups=("thermo",),
        default_output_style="markdown",
    ),
    "general": PromptProfile(
        system_prompt=GENERAL_PROMPT,
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
    return get_profile(profile).allowed_tool_groups
