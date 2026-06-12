# Task Pack 05 — Agent Workflows

## Goal

Add agent workflow layer using structured outputs.

Agents can research, propose DSL, run backtests via tools, assess risk, and write console summaries.

Agents cannot trade live.

## Files to Inspect

```text
quant/strategies/
quant/backtest/
quant/risk/
apps/api/app/core/policy_engine.py
apps/api/app/core/audit_logger.py
```

## Files to Create / Modify

```text
agents/base.py
agents/schemas.py
agents/tools/market_data_tools.py
agents/tools/backtest_tools.py
agents/tools/risk_tools.py
agents/research_agent.py
agents/strategy_agent.py
agents/backtest_agent.py
agents/risk_agent.py
agents/governor_agent.py
agents/console_agent.py

apps/api/app/routes/agents.py

tests/unit/test_agent_schemas.py
tests/unit/test_agent_tool_permissions.py
tests/integration/test_research_to_backtest_workflow.py
```

## Agents

### Research Agent

Inputs:

```text
universe
time range
existing strategy registry
market summary
```

Outputs:

```text
research_note
hypotheses
risks
recommended_next_actions
```

### Strategy Agent

Outputs only restricted Strategy DSL.

Must not output Python strategy code.

### Backtest Agent

Can call backtest tool only.

### Risk Agent

Can call risk engine.

### Governor Agent

Only component allowed to recommend lifecycle promotion.

### Console Agent

Generates owner-facing daily summary from structured data only.

## Tool Permission Rules

```text
Research Agent:
- read market data
- write research note

Strategy Agent:
- read research notes
- create strategy DSL draft

Backtest Agent:
- validate DSL
- run backtest

Risk Agent:
- run risk engine

Governor Agent:
- evaluate policy
- create promotion decision

Console Agent:
- read structured state
- write summary

No agent:
- direct broker order
- live execution
- risk policy modification
- secret access
```

## Structured Output

Use Pydantic models for every agent output.

Tests should use mocked LLM responses or deterministic structured outputs.

## Tests

```bash
pytest tests/unit/test_agent_schemas.py
pytest tests/unit/test_agent_tool_permissions.py
pytest tests/integration/test_research_to_backtest_workflow.py
```

## Acceptance Criteria

```text
1. Agents produce validated structured output.
2. Strategy Agent cannot produce arbitrary executable code.
3. Agent tools enforce permissions.
4. Governor is the only lifecycle promotion entry point.
5. All agent runs are audit logged.
6. Tests do not require OpenAI API key.
```

## Rollback

Revert agents and route files.
