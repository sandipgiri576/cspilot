"""Turn a multi-molecule request into a bounded, validated set of independent jobs."""

from __future__ import annotations

from typing import Any, Literal

from agents import Agent, AgentOutputSchema, FunctionTool, ModelSettings, Runner
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cspilot.llm import create_llm_model


class Subtask(BaseModel):
    """Describe one independent molecular calculation or analysis."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    request: str = Field(min_length=1, max_length=4000)
    smiles: str | None = None
    input_xyz: str | None = None
    charge: int = 0
    mult: int = Field(default=1, ge=1, le=9)
    coefficient: float = Field(default=1, gt=0, le=1e6, allow_inf_nan=False)
    role: Literal["reactant", "product", "candidate"] = "candidate"


class Decomposition(BaseModel):
    """Describe a bounded set of independent scientific subtasks."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["collection", "reaction", "conformers"] = "collection"
    property: Literal["enthalpy", "gibbs_free_energy", "final_energy_hartree"] = "enthalpy"
    method: str = Field(default="r2scan-3c", pattern=r"^[A-Za-z0-9+*()_,.\-]+$")
    basis: str = Field(default="def2-SVP", pattern=r"^[A-Za-z0-9+*()_,.\-]+$")
    phase: Literal["gas"] = "gas"
    temperature_kelvin: float = 298.15
    pressure_atm: float = 1.0
    subtasks: list[Subtask] | None = Field(
        default=None,
        min_length=1,
        max_length=8,
        description="One job per independent molecule/species; null only when blocked_reason is set.",
    )
    blocked_reason: str | None = None

    @model_validator(mode="after")
    def validate_jobs(self) -> Decomposition:
        """Validate subtask identities and supported aggregation conditions."""
        if self.blocked_reason:
            if self.subtasks:
                raise ValueError("Blocked decompositions cannot schedule jobs")
            return self
        if not self.subtasks or len({s.id for s in self.subtasks}) != len(self.subtasks):
            raise ValueError(
                "Nonblocked requests MUST include 1-8 subtasks with unique safe IDs; create one per species"
            )
        if self.temperature_kelvin != 298.15 or self.pressure_atm != 1.0:
            raise ValueError("This first version supports only 298.15 K and 1 atm")
        if self.kind == "reaction":
            if {s.role for s in self.subtasks} != {"reactant", "product"}:
                raise ValueError("Reactions need reactants and products, not candidates")
            if any(not s.smiles for s in self.subtasks):
                raise ValueError("Reaction species require SMILES for identity and balance checks")
        if self.kind == "conformers":
            if len(self.subtasks) < 2 or any(
                not s.input_xyz or not s.smiles for s in self.subtasks
            ):
                raise ValueError(
                    "Conformer comparison needs explicit XYZ files and molecular SMILES"
                )
            if len({(s.smiles, s.charge, s.mult) for s in self.subtasks}) != 1:
                raise ValueError("Conformers must have the same identity, charge and multiplicity")
        return self


async def decompose_request(
    request: str, model: str | None = None, base_url: str | None = None
) -> Decomposition:
    """Decompose a request into independent, structured scientific subtasks."""

    async def submit(context: Any, arguments: str) -> str:
        """Validate and serialize a model-submitted decomposition."""
        return Decomposition.model_validate_json(arguments).model_dump_json()

    agent = Agent(
        name="cspilot_decomposer",
        model=create_llm_model(model=model, base_url=base_url),
        tools=[
            FunctionTool(
                name="submit_decomposition",
                description="Submit independent jobs or a blocked reason.",
                params_json_schema=AgentOutputSchema(Decomposition).json_schema(),
                on_invoke_tool=submit,
            )
        ],
        model_settings=ModelSettings(
            tool_choice="required", parallel_tool_calls=False, max_tokens=4096
        ),
        tool_use_behavior="stop_on_first_tool",
        instructions="""Decompose the request into at most eight INDEPENDENT scientific agent jobs.
Do not calculate or invent results. Each child has an iterative allowlisted tool loop.
Use collection for independent molecule screening or analysis; preserve every requested operation.
COLLECTION jobs can be inspection, identifier lookup, Multiwfn or calculations. Inspection
does NOT require any optimization, ORCA, or frequencies. Repeated inspection is allowed.
Example: inspect two files -> kind=collection, one inspect request and input_xyz per file.
Subtask keys are EXACTLY id, request, smiles, input_xyz, charge, mult, coefficient, role.
Never use label, name, phase or task as subtask keys. For inspection use request="Inspect
the supplied water XYZ and report its formula", role="candidate", smiles=null.
The property/method fields are ignored for collection. Do not apply reaction rules to collection.
Use reaction for stoichiometric reaction enthalpy/Gibbs/electronic energy; one job per species/side.
Use positive coefficients and reactant/product roles, preserving the explicit balanced equation.
Return actual molecular SMILES for reaction identity checks, not names or molecular formulas.
Oxygen O2 ground state is triplet: SMILES [O][O], charge=0, mult=3. Water O, methane C,
carbon dioxide O=C=O are neutral singlets. Other radicals require correct charge/spin, not singlet defaults.
ONLY reaction/conformer thermochemistry jobs must optimize AND calculate frequencies
at the SAME requested ORCA method. Electronic-energy-only jobs need no frequencies.
Default method r2scan-3c, gas phase at 298.15 K and 1 atm. Never represent liquid water
combustion/HHV as gas-phase combustion/LHV. If requested phase/conditions unsupported, block.
Use conformers only for user-supplied distinct existing XYZ files of the same molecule.
Do not invent input filenames or imply conformer searching is implemented here.
For dependencies beyond independent species calculations + aggregation, missing identity/spin,
ambiguous reactions, unavailable analyses, or >8 jobs: return no subtasks and blocked_reason.
For a reaction you MUST populate subtasks with every reactant AND product. Do not
return just reaction settings with empty subtasks. For CH4 + 2 O2 -> CO2 + 2 H2O,
create four tasks: methane (C,reactant,1,0,1), oxygen ([O][O],reactant,2,0,3),
carbon_dioxide (O=C=O,product,1,0,1), water (O,product,2,0,1), where each tuple is
SMILES,role,coefficient,charge,mult. Set each request to optimize and compute its
enthalpy. The aggregator, NOT a child, calculates the reaction sum.
Preserve input paths exactly. Each request is self-contained and must not depend on another child.
For identifier-only questions use collection and do not request a calculation.
Call submit_decomposition once. Do not write prose or schema definitions.
""",
    )
    # One bounded repair attempt for provider schema errors, with explicit feedback.
    prompt = request
    for attempt in range(2):
        try:
            result = await Runner.run(agent, prompt, max_turns=2)
            if isinstance(result.final_output, Decomposition):
                return result.final_output
            if isinstance(result.final_output, str):
                return Decomposition.model_validate_json(result.final_output)
            return Decomposition.model_validate(result.final_output)
        except Exception as exc:
            if attempt:
                raise
            prompt = (
                request
                + "\nPrevious decomposition was invalid. Correct the schema, do not execute jobs.\n"
                + " ".join(str(exc).split())[:1500]
            )
    raise RuntimeError("No decomposition produced")
