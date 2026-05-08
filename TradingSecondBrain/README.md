# Trading Second Brain — Agentic Trading Thesis Engine

A **local-first, privacy-preserving** multi-agent research engine that turns an
Obsidian vault into a quantitative second brain. Daily briefs, versioned theses,
backtested ideas, calibration loop — all running on a Mac Mini (or any Linux/macOS
box) with Ollama, Qdrant, n8n, and a small FastAPI service.

> **STATUS: SIMULATED — NOT FOR EXECUTION.** This is research software. No code in
> this repository places real trades. See `obsidian-vault/VAULT.md §2` for the full
> rule list.

---

## 1. Architecture at a Glance

```
                    ┌──────────────────────────┐
                    │   Obsidian Vault (md)    │  ← single source of truth
                    │  Inbox/ Sources/ Theses/ │
                    └───────────┬──────────────┘
                                │ (Local REST API plugin :27124)
       ┌────────────┐           │
       │   n8n      │ ◀─────────┤   PUT/GET notes
       │  :5678     │           │
       └─────┬──────┘           │
             │ POST /brief, /ingest, /reflect, /feedback
             ▼
       ┌──────────────────────────────┐    embeddings    ┌──────────┐
       │ FastAPI agents (:8088)       │ ───────────────▶ │  Ollama  │
       │  Researcher → Analyst →      │                  │  :11434  │
       │  Critic → Trader (CrewAI)    │ ───────────────▶ │  qwen3   │
       └──────────────┬───────────────┘                  │  nomic   │
                      │ vectors                          └──────────┘
                      ▼
                ┌──────────────┐
                │  Qdrant      │
                │  :6333       │
                └──────────────┘
```

- **Obsidian Vault** — the only persistent state.
- **n8n (Docker)** — schedulers + ingestion (Readwise / Telegram / Whisper).
- **Ollama (host-native)** — `qwen3:32b` for reasoning, `nomic-embed-text` for RAG.
- **Qdrant** — vector store; Chroma is supported as a drop-in alternative.
- **FastAPI + CrewAI** — 4-agent pipeline (`agents/crew.py`).
- **launchd / cron** — fire `/brief` weekdays 06:00, `/reflect` Sundays 23:00.

## 2. Folder Map

```
TradingSecondBrain/
├── obsidian-vault/                  ← the vault (open this in Obsidian)
│   ├── VAULT.md                     master system prompt for every agent
│   ├── TRADING_SYSTEM.md            operator playbook & house rules
│   ├── Inbox/                       raw captures
│   ├── Sources/                     articles / podcasts / transcripts / tweets
│   ├── Theses/                      versioned trading theses
│   │   └── _DailyBriefs/            06:00 outputs
│   ├── MarketData/                  daily snapshots (manual or via n8n)
│   ├── Agents/
│   │   ├── Memory/                  per-agent append-only memory
│   │   └── Logs/                    per-run JSON logs
│   ├── Templates/                   Templater templates (Thesis, DailyBrief, …)
│   └── .obsidian/plugins/           plugin configs (committed)
├── agents/                          Python agent system
│   ├── main.py                      FastAPI server
│   ├── crew.py                      CrewAI pipeline
│   ├── rag.py                       Qdrant/Chroma + Ollama embeddings
│   ├── backtester.py                SMA-cross sanity backtester
│   ├── market_data.py               yfinance / Polygon adapter
│   ├── obsidian_client.py           Local REST API client (with FS fallback)
│   ├── schemas.py                   strict pydantic schemas (VAULT.md §7)
│   ├── config.py                    env-driven settings
│   ├── prompts/                     researcher / analyst / critic / trader / reflection
│   ├── Dockerfile
│   └── requirements.txt
├── n8n/workflows/                   4 importable JSON workflows
├── docker-compose.yml               n8n + qdrant + agents (+ optional ollama)
├── cron/                            launchd plists, shell scripts, linux crontab
├── .env.example
├── .gitignore
└── README.md
```

## 3. Prerequisites (Mac Mini specific)

```bash
# Homebrew tools
brew install git python@3.11 jq curl
brew install --cask obsidian docker

# Ollama (host-native = best on Apple Silicon)
brew install ollama
ollama serve &                     # leave running, or `brew services start ollama`

# Pull models (reasoning + embeddings)
ollama pull qwen3:32b              # or `deepseek-r1:32b` if you prefer
ollama pull nomic-embed-text

# Optional voice ingest
brew install ffmpeg
pip3 install -U openai-whisper     # for n8n workflow 01 + 04
```

> Disk usage: `qwen3:32b` ≈ 19 GB, `nomic-embed-text` ≈ 280 MB, Qdrant + n8n
> images ≈ 600 MB. Reserve ~30 GB free.

## 4. First-time Setup

```bash
# 1. Place the project where the launchd scripts expect it.
mkdir -p ~/TradingSecondBrain
git clone <this-repo> ~/TradingSecondBrain   # or copy these files into it
cd ~/TradingSecondBrain

# 2. Configure environment
cp .env.example .env
# edit .env: set OBSIDIAN_API_KEY (after step 5), API_TOKEN, optional POLYGON_API_KEY

# 3. Install Python deps for native runs (skip if you only use docker-compose)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r agents/requirements.txt

# 4. Open the vault in Obsidian once
#   File → Open vault → choose obsidian-vault/
#   Settings → Community plugins → Turn on community plugins → Browse → install:
#       Smart Connections · Local REST API · Dataview · Advanced URI ·
#       Templater · Obsidian Git · Calendar
#   The folder ./obsidian-vault/.obsidian/community-plugins.json already lists them
#   so Obsidian will offer to install them in one click.

# 5. Generate the Local REST API key
#   In Obsidian → Settings → Local REST API → "Copy API Key"
#   Paste it into .env as OBSIDIAN_API_KEY=...
#   Also paste it into .obsidian/plugins/obsidian-local-rest-api/data.json.

# 6. Initialize git inside the vault for auto-commit
cd obsidian-vault && git init && git add -A && git commit -m "vault: bootstrap"
cd ..

# 7. Bring the stack up
docker compose up -d qdrant n8n agents
# (skip `agents` and run uvicorn natively if you prefer hot-reloads:
#  uvicorn agents.main:app --host 127.0.0.1 --port 8088 --reload)

# 8. Sanity-check
curl -s http://127.0.0.1:8088/health | jq
curl -s -X POST http://127.0.0.1:8088/ingest -H "X-API-Token: $API_TOKEN" | jq
curl -s -X POST http://127.0.0.1:8088/brief  -H "X-API-Token: $API_TOKEN" \
     -H "Content-Type: application/json" -d '{"horizon":"swing"}' | jq

# 9. Import n8n workflows
#   Open http://localhost:5678 → Workflows → Import from file
#   Import each file under n8n/workflows/. Activate the ones you want.

# 10. Schedule the daily brief on the host
cp cron/com.tradingsecondbrain.dailybrief.plist  ~/Library/LaunchAgents/
cp cron/com.tradingsecondbrain.weekly-reflect.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.tradingsecondbrain.dailybrief.plist
launchctl load -w ~/Library/LaunchAgents/com.tradingsecondbrain.weekly-reflect.plist
```

On Linux:

```bash
crontab cron/crontab.linux
```

## 5. Daily Loop

| Time         | Trigger                                | What happens                                                                |
|--------------|----------------------------------------|------------------------------------------------------------------------------|
| every 15 min | n8n `01-ingestion`                     | Pulls Readwise / Telegram / Whisper voice-notes → writes to vault           |
| 02:00        | n8n `02-nightly-embed`                 | POST `/ingest` — re-embeds new vault notes into Qdrant                       |
| 06:00 wkdys  | launchd / n8n `03-daily-brief`         | POST `/brief` — runs the 4-agent pipeline, writes brief, pings ntfy         |
| every 5 min  | n8n `04-feedback-loop`                 | Whisper-transcribes voice notes from `Inbox/_feedback/`, applies confidence |
| Sun 23:00    | launchd `weekly-reflect`               | POST `/reflect` — Reflection agent updates calibration + knowledge graph    |

## 6. Agents

`agents/crew.py` runs the chain:

1. **Researcher** — breadth, surfaces relevant chunks + market stats.
2. **Analyst** — Bayesian update on each claim, proposes 3–5 candidate ideas.
3. **Critic** — must add disconfirming evidence; applies VAULT.md §6 caps.
4. **Trader** — runs `backtester.sma_cross_backtest`, fills sizing per house rules,
   writes the Markdown brief; stamps every output `SIMULATED — NOT FOR EXECUTION`.

A weekly **Reflection** agent (not in the daily chain) audits last week's
calibration, updates `Agents/Memory/reflection.md`, and refreshes the
knowledge graph snapshot.

## 7. Risk & Safety

- **Hard-coded caps** in `agents/config.py` mirror `TRADING_SYSTEM.md`. An LLM
  cannot raise them — you can, by editing both files together.
- **No execution path.** The codebase contains zero broker integrations.
- **Privacy.** Cloud LLMs are off unless you set `ALLOW_CLOUD_LLM=true` and
  provide a key. Vault content never leaves the host otherwise.
- **Cool-off rule.** Theses < 24h old are capped at confidence 60.
- **Critic gate.** Theses without disconfirming evidence cap at 60; without a
  backtest cap at 70; with only social sources cap at 50.
- **Auto-commit.** The vault auto-commits every change via the `obsidian-git`
  plugin and the `cron/run_daily.sh` git step. Push is opt-in.

Every agent output ends with the disclaimer in `VAULT.md §9`.

## 8. Troubleshooting

| Symptom                                         | Likely cause / fix                                                       |
|-------------------------------------------------|---------------------------------------------------------------------------|
| `/health` returns 200 but `/brief` 502s         | Ollama model not pulled; `ollama list` should show `qwen3:32b`.           |
| `/ingest` returns 0 chunks                      | `VAULT_PATH` mis-set; check `.env` and that `obsidian-vault` is populated.|
| n8n can't reach FastAPI                         | On Mac, n8n container uses `host.docker.internal`; on Linux add `--network host` or set `--add-host host.docker.internal:host-gateway`.|
| Smart Connections shows wrong embedding count   | Re-trigger from the Smart Connections panel; or `POST /ingest` to rebuild.|
| Obsidian REST `401`                             | The `OBSIDIAN_API_KEY` in `.env` doesn't match `.obsidian/plugins/obsidian-local-rest-api/data.json`.|
| Backtest reports `sample_size=0`                | Ticker has < ~120 sessions of data or `yfinance` rate-limited.           |

## 9. Where to Edit Things

| You want to…                              | Open this                                              |
|-------------------------------------------|--------------------------------------------------------|
| Change the trading style / risk caps      | `obsidian-vault/TRADING_SYSTEM.md`                     |
| Tighten or relax the confidence rubric    | `obsidian-vault/VAULT.md §6`                           |
| Tweak an agent's behavior                 | `agents/prompts/<role>.md`                             |
| Change LLM, embedding model, or backend   | `agents/config.py` + `.env`                            |
| Add a market-data source                  | `agents/market_data.py`                                |
| Add a new agent                           | `agents/crew.py` + new file in `agents/prompts/`       |
| Change daily run time                     | `cron/com.tradingsecondbrain.dailybrief.plist`         |

## 10. License & Disclaimer

This is research software. It is provided as-is, with no warranty. **Nothing in
this repository is investment advice.** All outputs are simulated. The Operator
assumes full responsibility for any decision made on the basis of this material.
