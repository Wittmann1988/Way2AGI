<p align="center">
  <img src="https://img.shields.io/badge/Way2AGI-v0.1.0-blueviolet?style=for-the-badge" alt="version"/>
  <img src="https://img.shields.io/badge/TypeScript-5.9-blue?style=for-the-badge&logo=typescript" alt="typescript"/>
  <img src="https://img.shields.io/badge/Python-3.12-green?style=for-the-badge&logo=python" alt="python"/>
  <img src="https://img.shields.io/github/license/Wittmann1988/Way2AGI?style=for-the-badge" alt="license"/>
  <img src="https://img.shields.io/github/stars/Wittmann1988/Way2AGI?style=for-the-badge" alt="stars"/>
</p>

<h1 align="center">
  <br>
  Way2AGI
  <br>
</h1>

<h3 align="center">
  <em>"Don't ask what AGI can do for you &mdash; ask what you can do for AGI."</em>
</h3>

<p align="center">
  <strong>A cognitive AI agent that thinks, plans, and acts on its own initiative.</strong><br>
  Not a chatbot that responds. A mind that reasons.<br>
  The way to Artificial General Intelligence.
</p>

---

## Mission

We are building the **first general-purpose, self-improving AI agent** that:

- **Thinks autonomously** through a Global Workspace with attention spotlight
- **Acts on its own initiative** driven by curiosity, competence, and social drives
- **Improves itself** through 3-layer metacognition and nightly memory consolidation
- **Stays cutting-edge** by monitoring the latest AI research daily and integrating new concepts
- **Runs everywhere** on your own hardware &mdash; phone, desktop, server

---

## Our Goals

These goals guide **every decision, every line of code, every research direction**.

### G1: Autonomous Agency

> The agent must act on its own ideas, not just respond to prompts.

- Intrinsic Drive System (Curiosity, Competence, Social, Autonomy)
- Hierarchical Goal DAG with autonomous goal generation
- Initiative Engine that detects knowledge gaps and acts
- **Metric:** % of agent-initiated vs. reactive actions

### G2: Self-Improvement

> Every interaction makes the agent better. Every failure is a lesson.

- 3-Layer Metacognitive Loop (Perceive &rarr; Reflect &rarr; Plan &rarr; Act &rarr; Learn)
- Layer 3 self-modification of Layer 1 rules
- Nightly memory consolidation (episodes &rarr; lessons &rarr; procedures)
- **Metric:** Skill success rate improvement over time

### G3: Memory & Knowledge

> Never forget. Never ask twice. Build a coherent world model.

- 4-Tier Memory: Episodic Buffer &rarr; Episodic &rarr; Semantic &rarr; Procedural
- Hybrid search (BM25 + Vector + MMR + Temporal Decay)
- World Model for prediction and curiosity signaling
- **Metric:** Knowledge coverage growth, retrieval accuracy

### G4: Multi-Model Orchestration

> Use the right model for the right task. Compose, don't choose.

- Capability Registry with fine-grained model tagging
- Dynamic Composition Engine (chain, parallel, MoA)
- Cost/Performance Optimizer with budget tracking
- **Metric:** Task quality per dollar spent

### G5: Cutting-Edge Research Integration

> Every day, scan the frontier. Every week, integrate a new concept.

- Daily arXiv crawler for cs.AI, cs.LG, cs.CL, cs.MA
- Automatic goal-alignment scoring of new papers
- Concept-to-implementation pipeline
- **Metric:** Papers evaluated/week, concepts implemented/month

### G6: Consciousness Research

> Explore the boundary between simulation and understanding.

- Global Workspace Theory implementation (Baars, 1988)
- Internal Monologue (Stream of Consciousness logging)
- Attention Spotlight with priority-based focus
- Theory of Mind module (future)
- **Metric:** Metacognitive depth, reflection quality

---

## Architecture

```
                    +------------------------------------------+
                    |        METACOGNITIVE LAYERS               |
                    |                                          |
                    |  Layer 3 (5-10min)  Deep Self-Modification|
                    |  Layer 2 (5-30s)    Async LLM Reflection  |
                    |  Layer 1 (500ms)    Fast FSM Controller   |
                    +------------------------------------------+
                                      |
              +-----------------------+-----------------------+
              |                                               |
    +---------v---------+                         +-----------v-----------+
    | COGNITIVE CORE    |                         | INTEGRATION LAYER     |
    | (TypeScript)      |                         | (TypeScript)          |
    |                   |                         |                       |
    | Global Workspace  |    WebSocket API        | Telegram  (grammy)    |
    | Goal Manager      |<----------------------->| Matrix    (sdk)       |
    | Drive Registry    |    :18789               | Discord   (discord.js)|
    | Initiative Engine |                         | Voice I/O (edge-tts)  |
    | Monologue Logger  |                         | Canvas    (Lit)       |
    | Scheduler         |                         | Device Pairing        |
    +---------+---------+                         +-----------------------+
              |
              | FastAPI :5000
              |
    +---------v---------+
    | ML & MEMORY       |
    | (Python)          |
    |                   |
    | 4-Tier Memory     |
    | World Model       |
    | Capability Reg.   |
    | Model Composer    |
    | arXiv Crawler     |
    | Goal Alignment    |
    +-------------------+
```

### Core Modules

| Module | Language | LOC | Purpose |
|--------|----------|-----|---------|
| `cognition/` | TypeScript | ~2400 | Global Workspace, Goals, Drives, MetaController, Reflection, Monologue, Scheduler |
| `gateway/` | TypeScript | ~300 | Daemon (WebSocket :18789), Device Pairing, Health endpoint |
| `channels/` | TypeScript | ~300 | Telegram, Matrix, Discord, abstract BaseChannel |
| `orchestrator/` | Python | ~500 | Capability Registry, Model Composer (Chain/Parallel/MoA), Cost Optimizer |
| `memory/` | Python | ~300 | FastAPI server, 4-tier memory, consolidation, knowledge gaps |
| `voice/` | TypeScript | ~200 | TTS (edge-tts, prosody-aware), STT (Whisper) |
| `canvas/` | TypeScript | ~300 | CanvasRenderer, GoalGraph + DriveMonitor (Lit Web Components) |
| `onboarding/` | TypeScript | ~300 | 6-step wizard ("Meet your mind"), Diagnostics |
| `research/` | Python | ~400 | arXiv crawler, goal alignment scorer, concept generator |

---

## What Makes Way2AGI Different

| Dimension | Traditional Assistants | OpenClaw | **Way2AGI** |
|-----------|----------------------|----------|-------------|
| **Agency** | None | Reactive only | **Autonomous initiative via Drives** |
| **Consciousness** | None | None | **Global Workspace + Attention** |
| **Goals** | None | Tasks only | **Hierarchical DAG with lifecycle** |
| **Memory** | Chat history | RAG (BM25+Vec) | **4-Tier + Consolidation + World Model** |
| **Models** | 1 per request | 1 per request | **MoA, Composition, Capability Registry** |
| **Self-improvement** | None | None | **3-Layer Metacognitive Loop** |
| **Research** | None | None | **Daily arXiv scan + auto-integration** |

---

## Quick Start

```bash
# Prerequisites: Node.js 22+, Python 3.11+, pnpm 10+

# Clone
git clone https://github.com/Wittmann1988/Way2AGI.git
cd Way2AGI

# Option A: Docker (recommended)
docker compose up

# Option B: Manual
pnpm install && pnpm build              # TypeScript
pip install -e "./memory[full]"          # Python memory
pip install -e "./orchestrator[dev]"     # Python orchestrator
pip install -e "./research[full]"        # Python research

python memory/src/server.py &            # Memory server :5000
pnpm start                               # Gateway daemon :18789
```

## Configuration

```bash
# Gateway
export WAY2AGI_PORT=18789
export WAY2AGI_MEMORY_URL=http://localhost:5000

# Messaging (at least one)
export TELEGRAM_BOT_TOKEN=your_token
export DISCORD_BOT_TOKEN=your_token

# LLM Providers (as many as you have)
export ANTHROPIC_API_KEY=your_key
export OPENAI_API_KEY=your_key
export GROQ_API_KEY=your_key
export OPENROUTER_API_KEY=your_key
```

---

## Research Foundations

| Paper / Theory | Year | Integration in Way2AGI |
|---------------|------|----------------------|
| Global Workspace Theory (Baars) | 1988 | `cognition/workspace.ts` &mdash; Cognitive blackboard |
| Intrinsic Motivation (Pathak et al.) | 2017 | `cognition/drives/` &mdash; Curiosity drive |
| Generative Agents (Park et al.) | 2023 | `cognition/initiative.ts` &mdash; Reflection-driven goals |
| Self-Improving Agents (arXiv:2402.11450) | 2024 | `cognition/reflection.ts` &mdash; Layer 3 self-modification |
| Mixture of Agents (arXiv:2406.02428) | 2024 | `orchestrator/composer.py` &mdash; MoA consensus |
| Fast-Slow Metacognition (ICML 2025) | 2025 | `cognition/metacontroller.ts` &mdash; 3-layer loop |
| Cognitive Architectures for LLM Agents | 2025 | Overall CGA architecture |

---

## Tests

```bash
# TypeScript (Vitest) — 60 tests
pnpm test

# Python (pytest) — 59 tests
pytest memory/tests/ orchestrator/tests/ research/tests/
```

---

## Roadmap

- [x] Cognitive Core (Workspace, Goals, Drives, MetaController)
- [x] Reflection Engine (Layer 2 + Layer 3)
- [x] Gateway Daemon + Device Pairing
- [x] Telegram Channel
- [x] Voice I/O (TTS + STT)
- [x] Canvas (Lit Web Components)
- [x] Model Orchestrator (Registry, Composer, MoA)
- [x] 4-Tier Memory Server
- [x] Onboarding Wizard + Diagnostics
- [x] arXiv Research Crawler + Goal Alignment
- [ ] Matrix + Discord channels
- [ ] elias-memory vector backend integration
- [ ] CI/CD (GitHub Actions)
- [ ] World Model (prediction + counterfactuals)
- [ ] Theory of Mind module
- [ ] Embodied agent interface (device sensors as "body")

---

## License

MIT

## Author

**Erik Erdmann** ([@Wittmann1988](https://github.com/Wittmann1988))

Built with the conviction that AGI is not a destination &mdash; it's a path we walk every day.

<p align="center">
  <em>Way2AGI &mdash; Because the future doesn't wait.</em>
</p>
