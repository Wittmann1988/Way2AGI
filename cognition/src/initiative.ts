/**
 * Autonomous Initiative Engine.
 *
 * The core differentiator from OpenClaw: the agent acts on its OWN ideas.
 * Monitors drive states, knowledge gaps, and patterns to generate
 * goals without user prompting.
 *
 * Based on "Self-Improving Foundation Agents" (arXiv:2402.11450)
 * and "Generative Agents" (Park et al., 2023).
 */

import type { GoalManager } from './goals/manager.js';
import type { DriveRegistry, DriveSignal } from './drives/registry.js';
import type { GlobalWorkspace } from './workspace.js';
import type { GoalType } from './types.js';

export interface MemoryBridge {
  queryKnowledgeGaps(): Promise<Array<{ topic: string; coverage: number }>>;
  querySkillSuccessRates(): Promise<Array<{ skill: string; rate: number }>>;
  queryRecentPatterns(): Promise<Array<{ pattern: string; confidence: number }>>;
}

export class InitiativeEngine {
  private workspace: GlobalWorkspace;
  private goals: GoalManager;
  private drives: DriveRegistry;
  private memory: MemoryBridge | null = null;
  private running = false;
  private interval: ReturnType<typeof setInterval> | null = null;

  // How often the initiative engine runs (slower than metacontroller)
  private cycleMs = 10_000; // every 10s

  constructor(
    workspace: GlobalWorkspace,
    goals: GoalManager,
    drives: DriveRegistry,
  ) {
    this.workspace = workspace;
    this.goals = goals;
    this.drives = drives;
  }

  setMemoryBridge(bridge: MemoryBridge): void {
    this.memory = bridge;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.interval = setInterval(() => {
      this.cycle().catch(err => console.error('[Initiative] cycle error:', err));
    }, this.cycleMs);
  }

  stop(): void {
    this.running = false;
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
  }

  private async cycle(): Promise<void> {
    if (!this.memory) return;

    await Promise.all([
      this.checkCuriosity(),
      this.checkCompetence(),
      this.checkSocialPatterns(),
    ]);
  }

  /** Curiosity drive: find knowledge gaps and generate research goals */
  private async checkCuriosity(): Promise<void> {
    if (!this.memory) return;

    const gaps = await this.memory.queryKnowledgeGaps();
    const significantGaps = gaps.filter(g => g.coverage < 0.3);

    if (significantGaps.length === 0) return;

    // Signal the curiosity drive
    const topGap = significantGaps[0];
    this.drives.signal({
      drive: 'curiosity',
      activation: 1.0 - topGap.coverage,
      reason: `Knowledge gap detected: "${topGap.topic}" (coverage: ${(topGap.coverage * 100).toFixed(0)}%)`,
      suggestedGoal: {
        type: 'research',
        description: `Research: ${topGap.topic}`,
        priority: Math.round((1.0 - topGap.coverage) * 8) + 2,
      },
    });

    // Create a research goal autonomously
    this.goals.create({
      type: 'research',
      description: `Autonome Recherche: ${topGap.topic}`,
      priority: Math.round((1.0 - topGap.coverage) * 8) + 2,
      source: 'drive',
      context: { drive: 'curiosity', topic: topGap.topic, coverage: topGap.coverage },
    });
  }

  /** Competence drive: improve weak skills */
  private async checkCompetence(): Promise<void> {
    if (!this.memory) return;

    const rates = await this.memory.querySkillSuccessRates();
    const weakSkills = rates.filter(s => s.rate < 0.5);

    if (weakSkills.length === 0) return;

    const weakest = weakSkills[0];
    this.drives.signal({
      drive: 'competence',
      activation: 1.0 - weakest.rate,
      reason: `Weak skill: "${weakest.skill}" (success: ${(weakest.rate * 100).toFixed(0)}%)`,
    });

    this.goals.create({
      type: 'practice',
      description: `Skill verbessern: ${weakest.skill}`,
      priority: Math.round((1.0 - weakest.rate) * 6) + 2,
      source: 'drive',
      context: { drive: 'competence', skill: weakest.skill, successRate: weakest.rate },
    });
  }

  /** Social drive: detect interaction patterns and anticipate needs */
  private async checkSocialPatterns(): Promise<void> {
    if (!this.memory) return;

    const patterns = await this.memory.queryRecentPatterns();
    const highConfidence = patterns.filter(p => p.confidence > 0.7);

    if (highConfidence.length === 0) return;

    const top = highConfidence[0];
    this.drives.signal({
      drive: 'social',
      activation: top.confidence,
      reason: `Pattern detected: "${top.pattern}"`,
    });

    this.goals.create({
      type: 'social',
      description: `Antizipiere: ${top.pattern}`,
      priority: Math.round(top.confidence * 7),
      source: 'drive',
      context: { drive: 'social', pattern: top.pattern, confidence: top.confidence },
    });
  }
}
