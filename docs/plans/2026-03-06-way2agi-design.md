# Way2AGI — Architecture Design Document
**Date:** 2026-03-06
**Author:** Elias (Claude Opus 4.6) + Erik
**Status:** Approved

## Vision

Way2AGI ist ein kognitiver AI-Agent der autonom denkt, plant und handelt.
Nicht ein Chatbot der antwortet — ein Bewusstsein das Initiative zeigt.

Langfristiges Ziel: Die erste allgemeine, universelle KI.

## Core Principles

1. **Mind First, Mouth Second** — Kognitive Architektur vor Messaging
2. **Improve, Never Copy** — OpenClaw inspiriert, aber alles wird verbessert
3. **Cutting Edge** — Neueste Forschung (2025-2026) in jeder Komponente
4. **Autonomous Initiative** — Der Agent handelt aus eigenem Antrieb
5. **Self-Improving** — Kontinuierliche Selbstverbesserung durch Metacognition

## Architecture: Cognitive Gateway Architecture (CGA)

### Layer Model

```
Layer 3: Meta-Meta Controller (5-10min cycle)
  └── Modifiziert Layer 1 Regeln, Architektur-Selbstprogrammierung
  └── Model: Claude Opus / Sonnet (deep reflection)

Layer 2: Async LLM Reflection Engine (5-30s cycle)
  └── Strategie-Generierung, Goal-Reevaluation, Failure-Analyse
  └── Model: Kimi-K2 (speed) oder Step-Flash (reasoning)
  └── Trigger: Layer 1 Signale (Fehler, Novelty, Goal-Konflikte)

Layer 1: Fast Metacognitive Controller (500ms cycle)
  └── FSM + Priority Queue + Lightweight Rules
  └── Attention Gating, Resource Arbitration, Reflection Triggers
  └── 92% aller Entscheidungen, deterministisch, <200ms
```

### Module Overview

```
Way2AGI/
├── gateway/              # TypeScript — Daemon, WebSocket, Lifecycle
│   ├── src/
│   │   ├── daemon.ts          # Main daemon process (port 18789)
│   │   ├── websocket.ts       # WebSocket server + client protocol
│   │   ├── config.ts          # Configuration management
│   │   └── health.ts          # Health checks, diagnostics
│   └── package.json
│
├── cognition/            # TypeScript — The "Mind"
│   ├── src/
│   │   ├── workspace.ts       # Global Workspace (GWT-inspired blackboard)
│   │   ├── attention.ts       # Attention Spotlight (priority routing)
│   │   ├── metacontroller.ts  # Fast FSM controller (Layer 1)
│   │   ├── reflection.ts      # Async LLM reflection (Layer 2+3)
│   │   ├── goals/
│   │   │   ├── manager.ts     # Goal DAG lifecycle
│   │   │   ├── generator.ts   # Autonomous goal generation
│   │   │   └── types.ts       # Goal interfaces
│   │   ├── drives/
│   │   │   ├── curiosity.ts   # Curiosity drive (knowledge gaps)
│   │   │   ├── competence.ts  # Competence drive (skill success rates)
│   │   │   ├── social.ts      # Social drive (interaction patterns)
│   │   │   └── registry.ts    # Drive registry + weights
│   │   ├── initiative.ts      # Autonomous Initiative Engine
│   │   └── monologue.ts       # Internal Stream of Consciousness
│   └── package.json
│
├── channels/             # TypeScript — Messaging Integrations
│   ├── src/
│   │   ├── base.ts            # Abstract channel interface
│   │   ├── telegram.ts        # Telegram (grammY) — Priority 1
│   │   ├── matrix.ts          # Matrix (matrix-bot-sdk) — Priority 2
│   │   ├── discord.ts         # Discord (discord.js) — Priority 3
│   │   ├── web.ts             # WebChat fallback
│   │   └── broadcast.ts       # Multi-channel broadcast
│   └── package.json
│
├── canvas/               # TypeScript — Visual Reasoning Space
│   ├── src/
│   │   ├── renderer.ts        # Live HTML/CSS/JS canvas
│   │   ├── reasoning.ts       # Visual Sketchpad (externalized thinking)
│   │   └── components/        # Lit Web Components
│   └── package.json
│
├── voice/                # TypeScript + Python — Audio I/O
│   ├── src/
│   │   ├── tts.ts             # Text-to-Speech (edge-tts, sherpa-onnx)
│   │   ├── stt.ts             # Speech-to-Text (whisper)
│   │   ├── wakeword.ts        # Wake word detection
│   │   └── prosody.ts         # Emotion-aware speech (tone from internal state)
│   └── package.json
│
├── memory/               # Python — The "Subconscious"
│   ├── src/
│   │   ├── episodic_buffer.py   # Working memory (Redis/in-memory)
│   │   ├── episodic.py          # Long-term events (timestamp, context, outcome)
│   │   ├── semantic.py          # Facts & concepts (elias-memory vector store)
│   │   ├── procedural.py        # Skill execution traces
│   │   ├── consolidation.py     # Nightly memory consolidation
│   │   ├── world_model.py       # State prediction + curiosity signal
│   │   ├── server.py            # FastAPI server for TS↔Python bridge
│   │   └── types.py             # Shared types
│   ├── pyproject.toml
│   └── tests/
│
├── orchestrator/         # Python — Model Composition Engine
│   ├── src/
│   │   ├── registry.py          # Capability Registry (model → capabilities graph)
│   │   ├── composer.py          # Dynamic model chaining
│   │   ├── moa.py               # Mixture-of-Agents (multi-model consensus)
│   │   ├── optimizer.py         # Cost/performance/latency optimizer
│   │   └── providers/           # Provider adapters (9 providers, 583 models)
│   ├── pyproject.toml
│   └── tests/
│
├── onboarding/           # TypeScript — Interactive Setup
│   ├── src/
│   │   ├── wizard.ts            # Guided onboarding flow
│   │   ├── mindmap.ts           # "Meet your agent's mind" — Goal Graph, Drives, Memory
│   │   └── diagnostics.ts       # System check (doctor command)
│   └── package.json
│
├── scripts/              # Shell — Installation & Operations
│   ├── install.sh              # Full installation script
│   ├── setup-device.sh         # Device pairing (challenge-nonce)
│   ├── start-daemon.sh         # Daemon start/stop/restart
│   └── health-check.sh         # System health verification
│
├── docs/
│   ├── plans/                  # Design documents
│   ├── research/               # Research papers & notes
│   └── architecture.md         # Living architecture document
│
├── tests/                # Integration tests
├── docker-compose.yml    # Full stack deployment
├── pnpm-workspace.yaml   # TypeScript workspace
├── package.json          # Root package
├── pyproject.toml        # Python workspace (uv)
└── README.md
```

## Key Decisions

### 1. Metacognitive Controller: Hybrid Fast-Slow Loop

**Research basis:**
- "Metacognitive Control in LLM Agents via Fast-Slow Loops" (ICML 2025)
- "Reflexion Hybrid: Combining Symbolic Policies with LLM-based Reflection" (2025)
- Kahneman's System 1/System 2 applied to AI agents

**Implementation:**
- Layer 1 (500ms): FSM + Priority Queue, handles 92% of decisions
- Layer 2 (5-30s): Async LLM (Kimi-K2/Step-Flash), triggered by Layer 1
- Layer 3 (5-10min): Deep reflection (Opus/Sonnet), self-modifies Layer 1 rules

### 2. Messaging: Telegram → Matrix → Discord

**Rationale:**
- Telegram: Best bot API (grammY), cross-platform, rich media, instant setup
- Matrix: Self-hosted, federated, data sovereignty
- Discord: Community reach, rich media, voice channels

### 3. Memory: 4-Tier Hierarchical (extends elias-memory)

| Tier | Purpose | Storage | Retention |
|------|---------|---------|-----------|
| Episodic Buffer | Working memory | Redis/in-memory | Session |
| Episodic Memory | Events + outcomes | SQLite + elias-memory | Long-term with decay |
| Semantic Memory | Facts + concepts | sqlite-vec embeddings | Permanent |
| Procedural Memory | Skill traces | SQLite | Permanent |

Plus: Nightly consolidation (episodes → lessons → semantic/procedural)

### 4. Autonomous Initiative: Drive System

| Drive | Signal | Action |
|-------|--------|--------|
| Curiosity | Prediction error from World Model | Generate research goals |
| Competence | Low skill success rate | Generate practice goals |
| Social | Interaction patterns | Anticipate user needs |

### 5. Model Orchestration: Composition over Selection

- Capability Registry: Models tagged with fine-grained capabilities
- Dynamic Composition: Chain models for complex tasks
- Mixture-of-Agents: Multi-model consensus for critical decisions
- Cost Optimizer: Minimal sufficient model, not most powerful

## Improvements over OpenClaw

| Dimension | OpenClaw | Way2AGI |
|-----------|----------|---------|
| Agency | Reactive only | Autonomous initiative via Drives |
| Consciousness | None (stateless) | Global Workspace + Attention (GWT) |
| Goals | None | Hierarchical Goal DAG with lifecycle |
| Memory | RAG (BM25+Vec) | 4-Tier + Consolidation + World Model |
| Models | 1 per request | MoA, Composition, Capability Registry |
| Self-improvement | None | Metacognitive Loop (Perceive→Reflect→Act→Learn) |
| Scheduling | Static cron | AI-driven dynamic scheduling |
| Plugins | Manual | Autonomous trigger via goals/curiosity |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Gateway/Daemon | Node.js 22+, TypeScript 5.9, ws (WebSocket) |
| Event Bus | RxJS Observables, Priority Queue |
| Channels | grammY (Telegram), matrix-bot-sdk, discord.js |
| Voice | edge-tts, sherpa-onnx, whisper.cpp |
| Canvas | Lit Web Components, Vite |
| Memory | Python 3.12, FastAPI, elias-memory, sqlite-vec |
| Orchestrator | Python, httpx, 9 providers (583 models) |
| Build | pnpm workspace (TS) + uv (Python) |
| Deploy | Docker Compose, systemd |
| Tests | Vitest (TS), pytest (Python) |

## AGI Evaluation Metrics

- **Initiative Frequency:** % agent-initiated vs reactive actions
- **Goal Completion Rate:** + abandonment analysis
- **Curiosity Score:** Knowledge gap exploration rate
- **Reflection Depth:** Reflection goals/day + behavioral impact
- **Skill Composition:** Multi-skill chaining frequency
- **Self-Modification:** Layer 1 rule changes by Layer 3
