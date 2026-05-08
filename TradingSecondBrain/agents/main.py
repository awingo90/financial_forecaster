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


_CONFIDENCE_RE = __import__("re").compile(r"^(\s*confidence:\s*)(-?\d+)(\s*)$")
_DEFAULT_CONFIDENCE = 50


def _patch_confidence(body: str, delta: int) -> tuple[str, int]:
    """Apply ``delta`` to the YAML-frontmatter ``confidence:`` line only.

    - If frontmatter is missing, prepend one containing the new value.
    - If the line is missing inside the frontmatter, insert it once.
    - Body occurrences of ``confidence:`` are never touched.
    - Result is clamped to [0, 100].
    """
    lines = body.splitlines()
    fm_start = fm_end = None
    if lines and lines[0].strip() == "---":
        fm_start = 0
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i
                break

    if fm_start is None or fm_end is None:
        new_conf = max(0, min(100, _DEFAULT_CONFIDENCE + delta))
        prefix = ["---", f"confidence: {new_conf}", "---", ""]
        return "\n".join(prefix) + body.lstrip("\n"), new_conf

    target_idx = None
    current = _DEFAULT_CONFIDENCE
    for i in range(fm_start + 1, fm_end):
        m = _CONFIDENCE_RE.match(lines[i])
        if m:
            target_idx, current = i, int(m.group(2))
            break

    new_conf = max(0, min(100, current + delta))
    if target_idx is None:
        lines.insert(fm_start + 1, f"confidence: {new_conf}")
    else:
        m = _CONFIDENCE_RE.match(lines[target_idx])
        lines[target_idx] = f"{m.group(1)}{new_conf}{m.group(3)}"

    return "\n".join(lines) + ("\n" if body.endswith("\n") else ""), new_conf


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

    patched, new_conf = _patch_confidence(body, delta)
    if note:
        patched = patched.rstrip("\n") + f"\n\n<!-- feedback {delta:+d} | {note} -->\n"
    obsidian.write_note(rel, patched)
    return {"thesis_id": thesis_id, "applied_delta": delta, "confidence": new_conf}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agents.main:app", host=settings.api_host, port=settings.api_port, reload=False)
