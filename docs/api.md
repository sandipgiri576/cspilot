# Python Entry Points

| Entry point | Responsibility |
| --- | --- |
| cspilot.graph.run_graph_agent | Run the bounded agent loop and return JSON-safe final state |
| cspilot.graph.build_graph | Compile the LangGraph action/observation graph |
| cspilot.agents.planner.decide_next_action | Select one structured action from observations |
| cspilot.agents.planner.create_plan | Generate a complete saved plan for explicit execution |
| cspilot.agents.executor.execute_plan | Execute a saved allowlisted plan without a model |
| cspilot.agents.reporter.generate_report | Render execution data using domain report fields |
| cspilot.skill_loader.SkillLoader | Load common and profile Markdown by role |
| cspilot.tools.registry.call_tool | Normalize arguments and invoke an allowed tool |

See [Tools](tools.md) for deterministic scientific integrations and
[Agent Usage](agent_usage.md) for loop limits, artifacts, and skills.
