"""FastAPI server. Exposes the agent crew to n8n / cron / curl."""
from __future__ import annotations

from datetime import date

from fastapi import Depends, FastAPI, Header, HTTPException
from loguru import logger

from .config import settings
from .crew import run_daily, run_reflection
from .rag import ingest, retrieve
from .schemas import BriefRequest, BriefResponse


app = FastAPI(
    title="Trading Second Brain — Agent API",
    version="0.1.0",
    description="Local-first multi-agent trading research engine. SIMULATED — NOT FOR EXECUTION.",
)


def _auth(x_api_token: str = Header(default="")) -> None:
    if x_api_token != settings.api_token:
        raise HTTPException(status_code=401, detail="bad token")


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "ollama": settings.ollama_base_url,
        "model": settings.ollama_reasoning_model,
        "vector_backend": settings.vector_backend,
        "vault": str(settings.vault_path),
        "status": "SIMULATED — NOT FOR EXECUTION",
    }


@app.post("/ingest", dependencies=[Depends(_auth)])
def ingest_endpoint() -> dict:
    n = ingest()
    return {"ingested_chunks": n}


@app.post("/query", dependencies=[Depends(_auth)])
def query(q: str, k: int = 12) -> dict:
    return {"hits": retrieve(q, k=k)}


@app.post("/brief", response_model=BriefResponse, dependencies=[Depends(_auth)])
def daily_brief(req: BriefRequest) -> BriefResponse:
    logger.info(f"running daily brief: horizon={req.horizon} universe={req.universe}")
    ao = run_daily(
        question=f"What are the highest-conviction setups for the next {req.horizon} session?",
        universe=req.universe,
    )
    today = date.today().isoformat()
    return BriefResponse(
        date=today,
        regime=next((c.statement for c in ao.claims if "regime" in c.statement.lower()), "unknown"),
        ideas=[ao],
        markdown_path=f"Theses/_DailyBriefs/{today}.md",
        json_log_path=f"Agents/Logs/Trader-{ao.run_id}.json",
        status=ao.status,
    )


@app.post("/reflect", dependencies=[Depends(_auth)])
def reflect() -> dict:
    ao = run_reflection()
    return {"run_id": ao.run_id, "summary": ao.summary, "status": ao.status}


@app.post("/feedback", dependencies=[Depends(_auth)])
def feedback(thesis_id: str, delta: int, note: str = "") -> dict:
    """Accept a voice-note-derived confidence adjustment. n8n posts here after Whisper."""
    if not -50 <= delta <= 50:
        raise HTTPException(status_code=400, detail="delta out of bounds")
    from .obsidian_client import obsidian

    rel = f"Theses/{thesis_id}.md"
    body = obsidian.read_note(rel)
    if not body:
        raise HTTPException(status_code=404, detail="thesis not found")
    # naive frontmatter patch
    new = []
    for line in body.splitlines():
        if line.startswith("confidence:"):
            try:
                cur = int(line.split(":", 1)[1].strip())
            except ValueError:
                cur = 0
            new.append(f"confidence: {max(0, min(100, cur + delta))}")
        else:
            new.append(line)
    new.append(f"\n<!-- feedback {delta:+d} | {note} -->\n")
    obsidian.write_note(rel, "\n".join(new))
    return {"thesis_id": thesis_id, "applied_delta": delta}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agents.main:app", host=settings.api_host, port=settings.api_port, reload=False)
