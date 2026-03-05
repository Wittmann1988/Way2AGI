/**
 * Internal Monologue — Stream of Consciousness Logger.
 *
 * Records the agent's "thoughts" as a continuous narrative.
 * This is the closest thing to AI consciousness logging:
 * every perception, decision, and reflection is narrated.
 *
 * Used for:
 * - Debugging cognitive processes
 * - Memory consolidation (episodes are extracted from the monologue)
 * - Transparency (user can see what the agent is "thinking")
 * - Training data generation (monologue → SFT traces)
 */

import { appendFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { homedir } from 'os';

export type ThoughtType =
  | 'perception'    // External input received
  | 'attention'     // Focus shifted to something
  | 'decision'      // Rule-based decision made
  | 'goal'          // Goal created/updated
  | 'drive'         // Drive activation changed
  | 'reflection'    // LLM reflection result
  | 'action'        // Action taken (message sent, skill executed)
  | 'learning'      // Something learned (memory updated)
  | 'meta'          // Meta-thought (thinking about thinking)
  ;

export interface Thought {
  type: ThoughtType;
  content: string;
  timestamp: number;
  cycleNumber: number;
  metadata?: Record<string, unknown>;
}

export class InternalMonologue {
  private thoughts: Thought[] = [];
  private maxMemory = 1000; // Keep last 1000 thoughts in memory
  private logPath: string;
  private cycleCounter = 0;

  constructor(logDir?: string) {
    const dir = logDir ?? join(homedir(), '.way2agi', 'monologue');
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

    const date = new Date().toISOString().split('T')[0];
    this.logPath = join(dir, `${date}.jsonl`);
  }

  /** Record a thought */
  think(type: ThoughtType, content: string, metadata?: Record<string, unknown>): Thought {
    const thought: Thought = {
      type,
      content,
      timestamp: Date.now(),
      cycleNumber: this.cycleCounter,
      metadata,
    };

    this.thoughts.push(thought);

    // Persist to disk
    appendFileSync(this.logPath, JSON.stringify(thought) + '\n');

    // Bound memory
    if (this.thoughts.length > this.maxMemory) {
      this.thoughts = this.thoughts.slice(-this.maxMemory);
    }

    return thought;
  }

  /** Convenience methods for common thought types */
  perceive(what: string, meta?: Record<string, unknown>): Thought {
    return this.think('perception', what, meta);
  }

  focus(what: string): Thought {
    return this.think('attention', `Focusing on: ${what}`);
  }

  decide(what: string, reason: string): Thought {
    return this.think('decision', `${what} — because: ${reason}`);
  }

  reflect(insight: string): Thought {
    return this.think('reflection', insight);
  }

  learn(what: string): Thought {
    return this.think('learning', what);
  }

  meta(about: string): Thought {
    return this.think('meta', about);
  }

  setCycle(n: number): void {
    this.cycleCounter = n;
  }

  /** Get recent thoughts for context */
  getRecent(n = 20): Thought[] {
    return this.thoughts.slice(-n);
  }

  /** Get thoughts by type */
  getByType(type: ThoughtType, n = 20): Thought[] {
    return this.thoughts.filter(t => t.type === type).slice(-n);
  }

  /** Generate a narrative summary of recent thoughts */
  summarize(n = 10): string {
    return this.getRecent(n)
      .map(t => `[${t.type}] ${t.content}`)
      .join('\n');
  }

  get totalThoughts(): number {
    return this.thoughts.length;
  }
}
