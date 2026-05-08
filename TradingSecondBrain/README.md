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

> **zsh gotcha.** macOS zsh does **not** treat `# comment` after a command as a
> comment by default — pasting a line like `cp .env.example .env  # edit later`
> will try to copy `# edit later` as files. Either run `setopt interactive_comments`
> first, or strip the comments. The blocks below are comment-free for that reason.

```bash
# Homebrew tools
brew install git python@3.11 jq curl
brew install --cask obsidian
brew install --cask docker

# Start Docker Desktop once so the `docker` CLI exists on $PATH:
open -a Docker
# Then wait until Docker shows "Engine running" in the menu bar before continuing.
```

```bash
# Ollama (host-native = best on Apple Silicon)
brew install ollama

# Start the daemon FIRST — `ollama pull` needs a running server.
brew services start ollama
# (or run in foreground:  ollama serve &)

# Give the daemon a beat, then pull models.
sleep 2
ollama pull qwen3:32b
ollama pull nomic-embed-text
```

```bash
# Optional voice ingest (workflows 01 and 04)
brew install ffmpeg
pip3 install -U openai-whisper
```

> Disk usage: `qwen3:32b` ≈ 19 GB, `nomic-embed-text` ≈ 280 MB, Qdrant + n8n
> images ≈ 600 MB. Reserve ~30 GB free.

## 4. First-time Setup

Replace `<git-url>` with the URL of your fork or clone. All blocks are
comment-free so you can paste them straight into zsh.

### 4.1 Clone the project

```bash
mkdir -p ~/TradingSecondBrain
git clone <git-url> ~/TradingSecondBrain
cd ~/TradingSecondBrain
```

### 4.2 Configure environment

```bash
cp .env.example .env
```

Then open `.env` in your editor and set at minimum `API_TOKEN` (any random
string), and after step 4.4, `OBSIDIAN_API_KEY`.

### 4.3 Python deps (only if you want native runs alongside Docker)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r agents/requirements.txt
```

### 4.4 Configure Obsidian

1. Open Obsidian → File → Open vault → choose `~/TradingSecondBrain/obsidian-vault`.
2. Settings → Community plugins → Turn on community plugins → Browse → install
   Smart Connections, Local REST API, Dataview, Advanced URI, Templater, Obsidian
   Git, Calendar (the committed `community-plugins.json` lists them all so
   Obsidian offers a one-click install).
3. Settings → Local REST API → "Copy API Key". Paste the value into:
   - `.env` as `OBSIDIAN_API_KEY=...`
   - `.obsidian/plugins/obsidian-local-rest-api/data.json` (replace
     `REPLACE_ME_WITH_VALUE_FROM_PLUGIN_UI`).

### 4.5 Initialize git inside the vault for auto-commit

```bash
git -C obsidian-vault init
git -C obsidian-vault add -A
git -C obsidian-vault commit -m "vault: bootstrap"
```

### 4.6 Bring the stack up

```bash
docker compose up -d qdrant n8n agents
```

If you'd rather hot-reload the API natively, leave `agents` out and run
`uvicorn agents.main:app --host 127.0.0.1 --port 8088 --reload`.

### 4.7 Sanity-check

```bash
set -a; source .env; set +a
curl -s http://127.0.0.1:8088/health | jq
curl -s -X POST http://127.0.0.1:8088/ingest -H "X-API-Token: $API_TOKEN" | jq
curl -s -X POST http://127.0.0.1:8088/brief  -H "X-API-Token: $API_TOKEN" \
     -H "Content-Type: application/json" -d '{"horizon":"swing"}' | jq
```

### 4.8 Import n8n workflows

Open http://localhost:5678 → Workflows → Import from file → import each
`n8n/workflows/*.json` and activate the ones you want.

### 4.9 Schedule the daily brief on the host

```bash
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
