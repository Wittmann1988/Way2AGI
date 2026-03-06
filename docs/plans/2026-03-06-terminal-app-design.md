# Way2AGI Terminal App — Design Document

**Datum:** 2026-03-06
**Autor:** Erik Erdmann + Claude Opus 4.6
**Status:** Approved

## Zwischenziel

Way2AGI wird das beste lokal verfuegbare Agenten-Framework, das sich basierend auf
Nutzung staendig selbst neue Agenten trainiert. Selbstmodelle laufen auf dem Desktop-PC,
werden aus eigenen Traces trainiert (SFT/DPO), und verbessern sich kontinuierlich.

## 1. Ueberblick

Eine installierbare Terminal-Anwendung (Python/Textual) fuer Windows und Linux,
die alle Way2AGI-Features in einem interaktiven TUI zusammenfuehrt:

- Dashboard mit Status und Quick Actions
- Chat mit Streaming, Memory-Anbindung und Modellwechsel
- Settings fuer Provider, API-Keys und Modellauswahl
- Memory Browser (durchsuchen, Stats, Export)
- Training Pipeline (Traces -> Dataset -> Train -> GGUF -> Ollama)
- Diagnostics (Systemcheck)

## 2. Tech-Stack

- **UI:** Python 3.11+ mit `textual` (cross-platform TUI)
- **Installation:** `pip install way2agi`
- **Gateway/Cognition:** Vorgebaute JS-Bundles, Node.js 22+ als optionale Dependency
- **Erster Start:** Umgebungscheck (Node, Python-Pakete), dann Onboarding-Wizard
- **Config:** `~/.way2agi/config.json`

## 3. Default-Konfiguration (Free-First)

Ohne API-Key sofort nutzbar:

| Provider    | Modell              | Kosten | Rolle            |
|-------------|---------------------|--------|------------------|
| OpenRouter  | Step-3.5-Flash      | Gratis | Default Reasoning|
| OpenRouter  | Qwen-Coder          | Gratis | Default Code     |
| Groq        | Kimi-K2             | Gratis | Default Fast     |
| Ollama      | Auto-Detect          | Gratis | Default Lokal    |

**Top 5 konfigurierbar:** Anthropic, OpenAI, Google, Ollama, OpenRouter
**Custom:** OpenAI-kompatible URL + Key (deckt Groq, NVIDIA, xAI, etc.)

## 4. Dashboard (Startscreen)

```
┌─────────────────────────────────────────────────────────┐
│  ╦ ╦┌─┐┬ ┬┌─┐╔═╗╔═╗╦                                  │
│  ║║║├─┤└┬┘┌─┘╠═╣║ ╦║                                  │
│  ╚╩╝┴ ┴ ┴ └─┘╩ ╩╚═╝╩                                  │
│                                                         │
│  Dein persoenlicher KI-Agent der mit dir waechst.       │
│  Way2AGI verbindet freie & lokale Modelle mit echtem    │
│  Gedaechtnis und trainiert sich selbst — aus deiner     │
│  Nutzung, auf deinem PC.                                │
│                                                         │
│  Anders als Chatbots hat Way2AGI einen kognitiven Kern: │
│  Aufmerksamkeitssystem, Selbstbeobachtung und           │
│  Verbesserung, Bewusstseinsentwicklung — und Antriebe   │
│  wie Neugier und Kompetenzstreben die sein Handeln      │
│  lenken — und ein persistentes, aeusserst effizientes    │
│  Gedaechtnis.                                           │
│                                                         │
│  Der Orchestrator waehlt automatisch das beste Modell   │
│  fuer jede Aufgabe: schnelle Modelle fuer einfache      │
│  Fragen, starke fuer komplexe Probleme, mehrere         │
│  gleichzeitig fuer kritische Entscheidungen.            │
│  586 Modelle, 9 Provider — ein Agent der sie alle       │
│  intelligent kombiniert.                                │
│                                                         │
│  Kein Abo noetig. Keine Cloud. Deine Daten.             │
│  Freie Modelle · Lokales Memory · Selbsttraining        │
│  Kognitiver Kern · Multi-Modell Orchestrierung          │
├─ Status ────────────────┬─ Quick Actions ───────────────┤
│ Provider: OpenRouter     │ [C] Chat starten              │
│ Model: Qwen-Coder       │ [S] Settings                  │
│ Memory: 42 Eintraege    │ [M] Memory Browser            │
│ Lokal: 3 Modelle        │ [T] Training Pipeline         │
│ Cognitive: OFF          │ [D] Diagnostics               │
│ Selbstmodelle: 1        │ [Q] Beenden                   │
└─────────────────────────┴───────────────────────────────┘
```

## 5. Chat-Modus

Beim Druecken von [C] wechselt die UI in den Chat-Modus:

```
┌─ Way2AGI Chat ──── Qwen-Coder (OpenRouter) ────────────┐
│ [F1 Settings] [F2 Memory] [F3 Model] [F4 Train] [Esc]  │
├─────────────────────────────────────────────────────────┤
│ Assistant: Hallo! Wie kann ich helfen?                  │
│                                                         │
│ User: Erklaere mir asyncio                              │
│                                                         │
│ Assistant: asyncio ist Pythons Framework fuer...         │
│ [Memory: gespeichert] [Tokens: 342]                     │
├─────────────────────────────────────────────────────────┤
│ > _                                                     │
└─────────────────────────────────────────────────────────┘
```

### Features v1:
- Streaming-Antworten (Token fuer Token)
- Memory automatisch (jede Konversation wird in Episodic Memory gespeichert)
- Memory-Abruf (relevante Erinnerungen werden vor Antwort semantisch gesucht)
- Modell on-the-fly wechseln (F3)
- Slash-Commands: `/memory search ...`, `/model ...`, `/export`, `/clear`
- Esc zurueck zum Dashboard

## 6. Settings-Screen

```
┌─ Einstellungen ─────────────────────────────────────────┐
│                                                         │
│  Provider         [OpenRouter v]                        │
│  Modell           [Qwen-Coder  v]                       │
│  API Key          [••••••••••••]                         │
│                                                         │
│  ── Lokale Modelle (Ollama) ──                          │
│  Verfuegbar: nemotron (30B), way2agi:latest (2.3GB)     │
│  Standard-Lokal:  [way2agi:latest v]                    │
│                                                         │
│  ── Custom Provider ──                                  │
│  URL:             [                    ]                 │
│  Key:             [                    ]                 │
│                                                         │
│  [Speichern]  [Zurueck]                                 │
└─────────────────────────────────────────────────────────┘
```

## 7. Memory (vollstaendig)

### Automatisches Verhalten:
- **Speichern:** Jede Konversation -> Episodic Memory (elias-memory Backend)
- **Abrufen:** Vor jeder Antwort: semantische Suche nach relevantem Kontext
- **Consolidation:** Regelmaessig Lessons aus Episoden extrahieren

### Memory Browser (F2 / [M]):
- Durchsuchen aller 4 Tiers (Buffer, Episodic, Semantic, Procedural)
- Statistiken (Anzahl, Themen-Verteilung, Knowledge Gaps)
- Export (JSON, SFT-Format fuer Training)
- Loeschen einzelner Eintraege

## 8. Training Pipeline

```
┌─ Training Pipeline ─────────────────────────────────────┐
│                                                         │
│  1. Traces sammeln       [142 gesammelt]                │
│  2. Dataset erstellen    [erik1988/way2agi-traces]       │
│  3. Training starten     [SFT auf lokaler GPU]          │
│  4. GGUF konvertieren    [Q4_K_M]                       │
│  5. Deploy zu Ollama     [way2agi:latest]                │
│                                                         │
│  Letztes Training: 2026-03-06 (Loss: 0.847)            │
│  Selbstmodelle: way2agi:latest (2.3GB)                  │
│                                                         │
│  [S] Jetzt starten  [A] Auto-Training ON/OFF           │
└─────────────────────────────────────────────────────────┘
```

### Auto-Training:
- Wenn genug neue Traces (500+): automatisch Training anstoessen
- Pipeline: Traces -> HF Dataset -> SFT/DPO -> GGUF -> Ollama
- Neue Selbstmodelle sofort als lokales Modell verfuegbar
- Spaeter: Spezialisierte Agenten (Code-Agent, Research-Agent, etc.)

## 9. Phased Rollout

| Phase | Inhalt | Ziel |
|-------|--------|------|
| **v1.0 (MVP)** | Dashboard + Chat + Settings + Memory + Diagnostics | Nutzbarer Chat mit Memory |
| **v1.1** | Training Pipeline UI + Auto-Training | Selbstverbesserung |
| **v1.2** | Cognitive Core als opt-in (`--cognitive`) | Autonomes Handeln |
| **v1.3** | Multi-Agent (selbst-trainierte Spezialisten) | Agent-Ecosystem |

## 10. Dateistruktur

```
way2agi/
├── cli/
│   ├── __init__.py
│   ├── __main__.py         # Entry-Point: python -m way2agi
│   ├── app.py              # Textual App (Router zwischen Screens)
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── dashboard.py    # Startbildschirm mit Header + Status
│   │   ├── chat.py         # Chat-Modus mit Streaming
│   │   ├── settings.py     # Provider/Key/Modell Konfiguration
│   │   ├── memory.py       # Memory Browser + Stats
│   │   └── training.py     # Training Pipeline UI
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── header.py       # Way2AGI Banner + Beschreibungstext
│   │   ├── status.py       # Status-Panel (Provider, Memory, etc.)
│   │   └── chat_log.py     # Scrollable Chat-Verlauf
│   ├── config.py           # ~/.way2agi/config.json Management
│   ├── bootstrap.py        # Umgebungscheck + First-Run Setup
│   └── llm_client.py       # Unified LLM Client (alle Provider)
├── memory/                 # Existierender Memory Server
├── orchestrator/           # Existierender Orchestrator
├── cognition/              # Existierender Cognitive Core (TS)
├── gateway/                # Existierender Gateway (TS)
└── pyproject.toml          # pip install way2agi
```

## 11. Entry-Point

```bash
# Installation
pip install way2agi

# Erster Start (Onboarding)
way2agi

# Direkt Chat
way2agi chat

# Mit Cognitive Core
way2agi --cognitive

# Diagnostics
way2agi doctor
```

## 12. Dependencies (Python)

```
textual>=0.80        # TUI Framework
httpx>=0.27          # Async HTTP (LLM API Calls)
rich>=13.0           # Text-Formatting im Chat
elias-memory>=0.1    # Memory Backend
click>=8.0           # CLI Argument Parsing
```
