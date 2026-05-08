"""Multi-agent orchestration using CrewAI.

Four agents run sequentially: Researcher → Analyst → Critic → Trader. Each one
receives the structured AgentOutput from the previous and returns a new
AgentOutput. The crew is wired so the Trader's output is what gets persisted.

Why CrewAI rather than LangGraph here: simpler mental model for a 4-step linear
pipeline. If you need branching/loops (e.g. Critic-loops-back-to-Analyst), swap
to LangGraph by replacing `_build_crew` — the per-agent prompts and tools are
framework-agnostic.
"""
from __future__ import annotations

import json
from datetime import datetime, date
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

from crewai import Agent, Crew, Process, Task
from crewai.llm import LLM
from loguru import logger

from .backtester import sma_cross_backtest
from .config import settings
from .market_data import quick_stats
from .obsidian_client import obsidian
from .rag import retrieve, cite
from .schemas import AgentOutput


# --------------------------------------------------------------------- LLM wiring


def _llm() -> LLM:
    """Use Ollama via OpenAI-compatible endpoint. CrewAI's LLM wrapper handles it."""
    return LLM(
        model=f"ollama/{settings.ollama_reasoning_model}",
        base_url=settings.ollama_base_url,
        temperature=0.2,
    )


# --------------------------------------------------------------------- prompt loader

PROMPTS_DIR = Path(__file__).parent / "prompts"
VAULT = Path(settings.vault_path).expanduser()


def _system_prefix() -> str:
    vault_md = (VAULT / "VAULT.md").read_text(encoding="utf-8") if (VAULT / "VAULT.md").exists() else ""
    trading_md = (VAULT / "TRADING_SYSTEM.md").read_text(encoding="utf-8") if (VAULT / "TRADING_SYSTEM.md").exists() else ""
    return f"=== VAULT.md ===\n{vault_md}\n\n=== TRADING_SYSTEM.md ===\n{trading_md}\n"


def _role_prompt(role: str) -> str:
    p = PROMPTS_DIR / f"{role}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


# --------------------------------------------------------------------- agents


def _make_agent(role: str, goal: str) -> Agent:
    return Agent(
        role=role,
        goal=goal,
        backstory=_system_prefix() + "\n\n" + _role_prompt(role.lower()),
        llm=_llm(),
        allow_delegation=False,
        verbose=True,
        max_iter=4,
    )


def _researcher() -> Agent:
    return _make_agent(
        role="Researcher",
        goal="Surface every relevant signal in the vault and quick market stats. Output a structured AgentOutput JSON only.",
    )


def _analyst() -> Agent:
    return _make_agent(
        role="Analyst",
        goal="Update Bayesian posteriors on the Researcher's claims. Propose 3–5 candidate trade ideas. Output AgentOutput JSON.",
    )


def _critic() -> Agent:
    return _make_agent(
        role="Critic",
        goal="Find disconfirming evidence and apply VAULT.md §6 caps. Append claims with negative weight. Output AgentOutput JSON.",
    )


def _trader() -> Agent:
    return _make_agent(
        role="Trader",
        goal="Run backtests, set sizing/stops/targets per TRADING_SYSTEM.md, write the daily brief and theses. Output AgentOutput JSON.",
    )


# --------------------------------------------------------------------- tasks


def _research_task(question: str, retrieval: list[dict], universe_stats: list[dict]) -> Task:
    desc = dedent(
        f"""
        Operator question: {question}

        ## Retrieved vault context (top {len(retrieval)} chunks)
        {cite(retrieval)}

        ## Quick market stats
        {json.dumps(universe_stats, indent=2)}

        Produce ONLY a JSON object that validates against the AgentOutput schema in
        VAULT.md §7. Do not include any prose outside the JSON. Set agent="Researcher".
        """
    )
    return Task(description=desc, agent=_researcher(),
                expected_output="A single JSON object matching AgentOutput.")


def _analyst_task(prev: str) -> Task:
    desc = dedent(
        f"""
        Previous Researcher output (verbatim):
        ```json
        {prev}
        ```

        Update each claim's posterior, propose 3–5 candidate ideas, set
        agent="Analyst". Return only the JSON object.
        """
    )
    return Task(description=desc, agent=_analyst(),
                expected_output="A single JSON object matching AgentOutput.")


def _critic_task(prev: str, disconfirm_retrieval: list[dict]) -> Task:
    desc = dedent(
        f"""
        Previous Analyst output:
        ```json
        {prev}
        ```

        Disconfirming-evidence retrieval bundle:
        {cite(disconfirm_retrieval)}

        Apply VAULT.md §6 caps. Append at least one disconfirming claim per idea.
        Set agent="Critic" and status="REVIEWED" if approved, else "DRAFT".
        Return only the JSON object.
        """
    )
    return Task(description=desc, agent=_critic(),
                expected_output="A single JSON object matching AgentOutput.")


def _trader_task(prev: str, backtests: dict[str, dict]) -> Task:
    desc = dedent(
        f"""
        Previous Critic output:
        ```json
        {prev}
        ```

        Backtests already run for each candidate ticker:
        ```json
        {json.dumps(backtests, indent=2)}
        ```

        Fill in `risk` (sizing/stop/target/horizon) per TRADING_SYSTEM.md house
        rules. Apply event-week halving if applicable. Set agent="Trader" and
        status="SIMULATED — NOT FOR EXECUTION". Return only the JSON object.
        """
    )
    return Task(description=desc, agent=_trader(),
                expected_output="A single JSON object matching AgentOutput.")


# --------------------------------------------------------------------- helpers


def _parse_output(raw: str) -> AgentOutput:
    """CrewAI returns a string. Extract the JSON, validate, return AgentOutput."""
    txt = raw.strip()
    # Tolerate ```json fences
    if txt.startswith("```"):
        txt = txt.split("```", 2)[1]
        if txt.startswith("json"):
            txt = txt[4:]
        txt = txt.rsplit("```", 1)[0]
    data = json.loads(txt)
    return AgentOutput.model_validate(data)


def _candidate_tickers(ao: AgentOutput) -> list[str]:
    out: list[str] = []
    for a in ao.actions:
        t = a.payload.get("ticker") if isinstance(a.payload, dict) else None
        if t and t not in out:
            out.append(t)
    return out


def _default_universe() -> list[str]:
    return ["SPY", "QQQ", "IWM", "XLK", "XLE", "XLF", "TLT", "GLD"]


# --------------------------------------------------------------------- main entry


def run_daily(question: str = "What are the highest-conviction setups for tomorrow?",
              universe: list[str] | None = None) -> AgentOutput:
    run_id = str(uuid4())
    today = date.today().isoformat()
    universe = universe or _default_universe()

    # 1. Retrieve vault context for the question
    retrieval = retrieve(question, k=12)

    # 2. Pre-compute quick market stats
    universe_stats = []
    for t in universe:
        try:
            universe_stats.append(quick_stats(t))
        except Exception as e:
            logger.warning(f"stats failed for {t}: {e}")

    # 3. Researcher
    researcher_task = _research_task(question, retrieval, universe_stats)
    researcher_crew = Crew(agents=[researcher_task.agent], tasks=[researcher_task],
                           process=Process.sequential, verbose=True)
    researcher_raw = str(researcher_crew.kickoff())
    researcher_out = _parse_output(researcher_raw)
    obsidian.write_run_log("Researcher", run_id, researcher_out.model_dump_json(indent=2))
    obsidian.append_to_memory("researcher", researcher_out.summary, run_id)

    # 4. Analyst
    analyst_task = _analyst_task(researcher_out.model_dump_json())
    analyst_crew = Crew(agents=[analyst_task.agent], tasks=[analyst_task],
                        process=Process.sequential, verbose=True)
    analyst_raw = str(analyst_crew.kickoff())
    analyst_out = _parse_output(analyst_raw)
    obsidian.write_run_log("Analyst", run_id, analyst_out.model_dump_json(indent=2))
    obsidian.append_to_memory("analyst", analyst_out.summary, run_id)

    # 5. Critic — pull a disconfirming-evidence retrieval bundle
    disc_query = f"evidence against: {analyst_out.summary}"
    disc_hits = retrieve(disc_query, k=8)
    critic_task = _critic_task(analyst_out.model_dump_json(), disc_hits)
    critic_crew = Crew(agents=[critic_task.agent], tasks=[critic_task],
                       process=Process.sequential, verbose=True)
    critic_raw = str(critic_crew.kickoff())
    critic_out = _parse_output(critic_raw)
    obsidian.write_run_log("Critic", run_id, critic_out.model_dump_json(indent=2))
    obsidian.append_to_memory("critic", critic_out.summary, run_id)

    # 6. Trader — backtest each candidate, then ask LLM to fill risk
    backtests: dict[str, dict] = {}
    for t in _candidate_tickers(critic_out) or universe[:5]:
        try:
            r = sma_cross_backtest(t)
            backtests[t] = r.__dict__
        except Exception as e:
            logger.warning(f"backtest failed {t}: {e}")
            backtests[t] = {"error": str(e), "ran": False}

    trader_task = _trader_task(critic_out.model_dump_json(), backtests)
    trader_crew = Crew(agents=[trader_task.agent], tasks=[trader_task],
                       process=Process.sequential, verbose=True)
    trader_raw = str(trader_crew.kickoff())
    trader_out = _parse_output(trader_raw)
    trader_out.status = "SIMULATED — NOT FOR EXECUTION"
    obsidian.write_run_log("Trader", run_id, trader_out.model_dump_json(indent=2))
    obsidian.append_to_memory("trader", trader_out.summary, run_id)

    # 7. Render & persist Markdown brief
    brief_md = render_brief(trader_out, today, run_id, backtests)
    brief_path = f"Theses/_DailyBriefs/{today}.md"
    obsidian.write_note(brief_path, brief_md)

    return trader_out


def render_brief(ao: AgentOutput, today: str, run_id: str, backtests: dict[str, dict]) -> str:
    """Render the trader's structured output to the DailyBrief Markdown shape."""
    ideas_md = []
    for i, a in enumerate(ao.actions, start=1):
        if a.type not in ("paper_trade", "update_thesis", "watchlist"):
            continue
        p = a.payload or {}
        bt = backtests.get(p.get("ticker", ""), {})
        ideas_md.append(
            "\n".join([
                f"### {i}. [[{today}-{p.get('ticker','?')}-v1]] — confidence: {ao.confidence}/100",
                f"- Side / horizon / size: **{p.get('side','?')}** / {ao.risk.horizon_days}d / {ao.risk.position_size_pct}%",
                f"- Catalyst: {p.get('catalyst','—')}",
                f"- Entry / stop / target: {p.get('entry_zone','—')} / {p.get('stop','—')} / {p.get('target','—')}",
                f"- Backtest: sharpe={bt.get('sharpe', 'n/a')}, max_dd={bt.get('max_dd','n/a')}, trades={bt.get('sample_size','n/a')}",
                f"- Why now: {ao.summary}",
                f"- Action: `{a.type}`",
            ])
        )

    md = f"""---
type: daily_brief
date: {today}
generated_at: {datetime.utcnow().isoformat(timespec='minutes')}Z
run_id: {run_id}
regime: {next((c.statement for c in ao.claims if 'regime' in c.statement.lower()), 'unknown')}
top_ideas: {[a.payload.get('ticker') for a in ao.actions if a.payload]}
status: {ao.status}
tags: [brief]
---

# Daily Brief — {today}

## Macro Snapshot
{ao.summary}

## High-Confidence Ideas
{chr(10).join(ideas_md) if ideas_md else "_No ideas met the confidence floor today._"}

## Invalidation Conditions (apply across the book)
{chr(10).join(f'- {c}' for c in ao.risk.invalidation_conditions) or '- _none specified_'}

## Disclaimer
> This brief is generated by a local research assistant for personal-research
> purposes only. It is not investment advice. All ideas are simulated and require
> independent verification before any real-money action.
> **STATUS: {ao.status}**
"""
    return md


def run_reflection() -> AgentOutput:
    """Weekly run. Reads logs, writes reflection.md and knowledge_graph.md."""
    run_id = str(uuid4())
    # Build reflection prompt
    prompt = dedent(
        f"""
        {_system_prefix()}

        {_role_prompt('reflection')}

        Read recent agent logs and theses you have access to via the vault filesystem.
        Produce ONLY a JSON AgentOutput with agent="Reflection".
        Then in a SEPARATE JSON object under key `__memory_updates__`, return:
        {{
          "reflection_md": "<full markdown for Agents/Memory/reflection.md>",
          "knowledge_graph_md": "<full markdown for Agents/Memory/knowledge_graph.md>"
        }}
        """
    )
    agent = _make_agent("Reflection", "Audit the week and produce calibration + knowledge-graph updates.")
    task = Task(description=prompt, agent=agent,
                expected_output="A single JSON object matching AgentOutput, optionally followed by a __memory_updates__ block.")
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    raw = str(crew.kickoff())
    # Best-effort parse
    try:
        ao = _parse_output(raw.split("__memory_updates__")[0])
    except Exception as e:
        logger.error(f"reflection parse failed: {e}")
        ao = AgentOutput(agent="Reflection", summary="Reflection parse failed; see log.",
                         confidence=0, status="DRAFT")
    obsidian.write_run_log("Reflection", run_id, ao.model_dump_json(indent=2))
    return ao
