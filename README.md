# Way2AGI

**Cognitive AI Agent — The Way to Artificial General Intelligence**

A self-improving, autonomous AI agent that thinks, plans, and acts on its own initiative.
Inspired by OpenClaw, but architecturally superior: not a chatbot that responds, but a mind that reasons.

## Architecture

Way2AGI implements a **Cognitive Gateway Architecture (CGA)** with three metacognitive layers:

- **Layer 1 (500ms):** Fast FSM controller — attention, resource allocation, trigger detection
- **Layer 2 (5-30s):** Async LLM reflection — strategy generation, goal re-evaluation
- **Layer 3 (5-10min):** Deep reflection — self-modification of Layer 1 rules

### Core Modules

| Module | Language | Purpose |
|--------|----------|---------|
| `gateway/` | TypeScript | Daemon, WebSocket API, lifecycle |
| `cognition/` | TypeScript | Global Workspace, Goals, Drives, MetaController |
| `channels/` | TypeScript | Telegram, Matrix, Discord messaging |
| `canvas/` | TypeScript | Visual reasoning space (A2UI) |
| `voice/` | TS/Python | TTS, STT, wake word detection |
| `memory/` | Python | 4-tier hierarchical memory + world model |
| `orchestrator/` | Python | Model composition, MoA, capability registry |
| `onboarding/` | TypeScript | Interactive setup wizard |

### Key Differentiators vs. OpenClaw

- **Autonomous Initiative:** Agent acts on own ideas via Drive system (Curiosity, Competence, Social)
- **Global Workspace Theory:** Cognitive blackboard with attention spotlight
- **Hierarchical Goal DAG:** Goals with lifecycle, not just tasks
- **4-Tier Memory:** Episodic Buffer → Episodic → Semantic → Procedural + nightly consolidation
- **Mixture-of-Agents:** Multi-model consensus for critical decisions
- **Self-Modification:** Layer 3 rewrites Layer 1 rules

## Quick Start

```bash
# Prerequisites: Node.js 22+, Python 3.11+, pnpm 10+

# Clone and install
git clone https://github.com/Wittmann1988/Way2AGI.git
cd Way2AGI

# TypeScript modules
pnpm install
pnpm build

# Python memory server
cd memory && pip install -e ".[full]" && cd ..

# Start everything
docker compose up
# Or manually:
python memory/src/server.py &    # Memory server on :5000
pnpm start                       # Gateway daemon on :18789
```

## Configuration

```bash
# Required environment variables
export WAY2AGI_PORT=18789
export TELEGRAM_BOT_TOKEN=your_token_here
export WAY2AGI_MEMORY_URL=http://localhost:5000
```

## Research Foundations

- Global Workspace Theory (Baars, 1988)
- Metacognitive Control via Fast-Slow Loops (ICML 2025)
- Self-Improving Foundation Agents (arXiv:2402.11450)
- Generative Agents (Park et al., 2023)
- Mixture of Agents (arXiv:2406.02428)
- Intrinsic Motivation in AI (Pathak et al., 2017)

## License

MIT

## Author

Erik Erdmann ([@Wittmann1988](https://github.com/Wittmann1988))
