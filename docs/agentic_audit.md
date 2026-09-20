# Agentic Architecture Audit

CSPilot now has an iterative agent path in `run` and `graph-run`.
The model chooses one structured action, observes actual tool output and
verification feedback, and then chooses its next action or stops. This follows
the dynamic tool-use pattern in the
[LangGraph workflows and agents guide](https://docs.langchain.com/oss/python/langgraph/workflows-agents).

The scientific tools, verifier, and reporter remain deterministic. Fixed workflows
are reusable tools; the runtime sequence between tool calls is model-selected.
The profile router is still keyword-based, and legacy `--agent-mode multi` means
specialist routing. The new `--multiagent` flag instead runs a model-backed
decomposer, isolated child agent loops, structured summaries, deterministic
aggregation, verification and reporting. Optional bounded concurrency is available.

Implemented: domain Markdown guidance, one-action decisions, observation history,
failure feedback, bounded execution, saved artifacts, and full terminal reports.
The reporter loads field selections from skills and reports only returned values.

Limits: no checkpoint/resume across processes, no human clarification node, no
automatic proof that arbitrary scientific requests were fully satisfied, and no
dependent task-DAG scheduling or inter-agent debate. Reaction aggregation has
explicit physical/data compatibility checks; generic collection completeness still
depends partly on model decomposition. Historical failed attempts keep final verification
failed even after a successful recovery. A model finish decision is not itself
proof of scientific correctness. Default tests mock the model boundary.
