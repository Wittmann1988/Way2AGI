/**
 * Reflection Engine — Layers 2 & 3.
 *
 * Layer 2 (5-30s): Fast LLM reflection for failure analysis,
 *   goal reevaluation, and novelty assessment.
 * Layer 3 (5-10min): Deep self-modification — rule changes
 *   and full strategy reviews.
 *
 * Receives ReflectionRequests from the MetaController and
 * posts results back into the GlobalWorkspace.
 */

import type {
  ReflectionRequest,
  ReflectionTrigger,
  WorkspaceItem,
  Goal,
} from './types.js';
import type { GlobalWorkspace } from './workspace.js';
import type { GoalManager } from './goals/manager.js';

// ── LLM Client Interface ──────────────────────────────────────────

export interface LLMClient {
  complete(params: {
    model: string;
    system: string;
    prompt: string;
    maxTokens?: number;
  }): Promise<string>;
}

// ── Reflection Result Types ────────────────────────────────────────

export interface Layer2Result {
  trigger: ReflectionTrigger;
  analysis: string;
  recommendations: Layer2Recommendation[];
  confidence: number; // 0-1
  durationMs: number;
}

export interface Layer2Recommendation {
  action: 'abandon_goal' | 'reprioritize_goal' | 'create_goal' | 'unblock_goal' | 'ignore';
  goalId?: string;
  description: string;
  newPriority?: number;
  goalParams?: {
    type: Goal['type'];
    description: string;
    priority: number;
    source: Goal['source'];
  };
}

export interface Layer3Result {
  trigger: ReflectionTrigger;
  analysis: string;
  rulePatches: RulePatch[];
  strategyInsights: string[];
  confidence: number;
  durationMs: number;
}

export interface RulePatch {
  id: string;
  description: string;
  condition: string; // human-readable condition
  action: string;    // human-readable action
  priority: number;
}

// ── Configuration ──────────────────────────────────────────────────

export interface ReflectionConfig {
  layer2Model: string;
  layer3Model: string;
  layer2MaxTokens: number;
  layer3MaxTokens: number;
  maxConcurrentReflections: number;
}

const DEFAULT_CONFIG: ReflectionConfig = {
  layer2Model: 'kimi-k2-groq',
  layer3Model: 'claude-sonnet-4-6',
  layer2MaxTokens: 1024,
  layer3MaxTokens: 4096,
  maxConcurrentReflections: 2,
};

// ── Reflection Engine ──────────────────────────────────────────────

export class ReflectionEngine {
  private workspace: GlobalWorkspace;
  private goals: GoalManager;
  private llm: LLMClient;
  private config: ReflectionConfig;
  private activeReflections = 0;
  private history: Array<Layer2Result | Layer3Result> = [];

  constructor(
    workspace: GlobalWorkspace,
    goals: GoalManager,
    llm: LLMClient,
    config?: Partial<ReflectionConfig>,
  ) {
    this.workspace = workspace;
    this.goals = goals;
    this.llm = llm;
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Main entry point — called by MetaController when reflection is needed.
   * Routes to Layer 2 or Layer 3 based on the request.
   */
  async reflect(request: ReflectionRequest): Promise<Layer2Result | Layer3Result> {
    if (this.activeReflections >= this.config.maxConcurrentReflections) {
      // Post a notice that reflection was deferred
      this.postToWorkspace('Reflection deferred: concurrency limit reached', request, 2);
      return this.makeDeferredResult(request);
    }

    this.activeReflections++;
    try {
      const result = request.layer === 2
        ? await this.reflectLayer2(request)
        : await this.reflectLayer3(request);

      this.history.push(result);
      // Keep history bounded
      if (this.history.length > 50) this.history.shift();

      return result;
    } finally {
      this.activeReflections--;
    }
  }

  // ── Layer 2: Fast Reflection (5-30s) ──────────────────────────

  private async reflectLayer2(request: ReflectionRequest): Promise<Layer2Result> {
    const start = Date.now();
    const activeGoals = this.goals.getActive();
    const topGoals = this.goals.getTopPriority(5);

    const systemPrompt = LAYER2_SYSTEM;
    const userPrompt = this.buildLayer2Prompt(request, activeGoals, topGoals);

    const raw = await this.llm.complete({
      model: this.config.layer2Model,
      system: systemPrompt,
      prompt: userPrompt,
      maxTokens: this.config.layer2MaxTokens,
    });

    const parsed = this.parseLayer2Response(raw, request.trigger);
    const durationMs = Date.now() - start;

    const result: Layer2Result = {
      ...parsed,
      durationMs,
    };

    // Apply recommendations
    this.applyLayer2Recommendations(result.recommendations);

    // Post summary to workspace
    this.postToWorkspace(
      result.analysis,
      request,
      Math.min(result.confidence * 8, 8),
    );

    return result;
  }

  private buildLayer2Prompt(
    request: ReflectionRequest,
    activeGoals: Goal[],
    topGoals: Goal[],
  ): string {
    const goalSummary = activeGoals.map(g =>
      `[${g.id.slice(0, 8)}] ${g.type}/${g.status} p=${g.priority} "${g.description}"`,
    ).join('\n');

    const topSummary = topGoals.map(g =>
      `[${g.id.slice(0, 8)}] p=${g.priority} "${g.description}"`,
    ).join('\n');

    const contextStr = JSON.stringify(request.context, null, 2);

    switch (request.trigger) {
      case 'failure_pattern':
        return [
          `TRIGGER: failure_pattern (urgency=${request.urgency})`,
          `CONTEXT:\n${contextStr}`,
          `\nACTIVE GOALS (${activeGoals.length}):\n${goalSummary || 'none'}`,
          `\nTOP PRIORITY:\n${topSummary || 'none'}`,
          `\nAnalyze: Why did these goals fail? What should change?`,
          `Respond in the JSON format described in your system prompt.`,
        ].join('\n');

      case 'goal_conflict':
        return [
          `TRIGGER: goal_conflict (urgency=${request.urgency})`,
          `CONTEXT:\n${contextStr}`,
          `\nACTIVE GOALS (${activeGoals.length}):\n${goalSummary}`,
          `\nToo many goals are active and competing. Which should be deprioritized or abandoned?`,
          `Respond in the JSON format described in your system prompt.`,
        ].join('\n');

      case 'novelty_spike':
        return [
          `TRIGGER: novelty_spike (urgency=${request.urgency})`,
          `CONTEXT:\n${contextStr}`,
          `\nACTIVE GOALS (${activeGoals.length}):\n${goalSummary || 'none'}`,
          `\nA novel signal was detected. Is it important enough for a new goal?`,
          `Respond in the JSON format described in your system prompt.`,
        ].join('\n');

      default:
        return [
          `TRIGGER: ${request.trigger} (urgency=${request.urgency})`,
          `CONTEXT:\n${contextStr}`,
          `\nACTIVE GOALS (${activeGoals.length}):\n${goalSummary || 'none'}`,
          `\nReevaluate active goals. Are they still aligned and making progress?`,
          `Respond in the JSON format described in your system prompt.`,
        ].join('\n');
    }
  }

  private parseLayer2Response(raw: string, trigger: ReflectionTrigger): Omit<Layer2Result, 'durationMs'> {
    try {
      // Extract JSON from response (handle markdown code blocks)
      const jsonMatch = raw.match(/```(?:json)?\s*([\s\S]*?)```/) ?? raw.match(/(\{[\s\S]*\})/);
      if (!jsonMatch) throw new Error('No JSON found');

      const parsed = JSON.parse(jsonMatch[1].trim());
      return {
        trigger,
        analysis: parsed.analysis ?? raw.slice(0, 200),
        recommendations: Array.isArray(parsed.recommendations)
          ? parsed.recommendations.map(this.sanitizeRecommendation)
          : [],
        confidence: Math.min(1, Math.max(0, parsed.confidence ?? 0.5)),
      };
    } catch {
      // Graceful degradation: treat entire response as analysis
      return {
        trigger,
        analysis: raw.slice(0, 500),
        recommendations: [],
        confidence: 0.3,
      };
    }
  }

  private sanitizeRecommendation(rec: Record<string, unknown>): Layer2Recommendation {
    const action = rec.action as Layer2Recommendation['action'] ?? 'ignore';
    const valid = ['abandon_goal', 'reprioritize_goal', 'create_goal', 'unblock_goal', 'ignore'];
    return {
      action: valid.includes(action) ? action : 'ignore',
      goalId: typeof rec.goalId === 'string' ? rec.goalId : undefined,
      description: typeof rec.description === 'string' ? rec.description : String(rec.action ?? ''),
      newPriority: typeof rec.newPriority === 'number' ? rec.newPriority : undefined,
      goalParams: rec.goalParams as Layer2Recommendation['goalParams'],
    };
  }

  private applyLayer2Recommendations(recs: Layer2Recommendation[]): void {
    for (const rec of recs) {
      switch (rec.action) {
        case 'abandon_goal':
          if (rec.goalId) this.goals.transition(rec.goalId, 'abandoned');
          break;

        case 'unblock_goal':
          if (rec.goalId) this.goals.transition(rec.goalId, 'active');
          break;

        case 'create_goal':
          if (rec.goalParams) {
            this.goals.create({
              type: rec.goalParams.type,
              description: rec.goalParams.description,
              priority: rec.goalParams.priority,
              source: 'reflection',
            });
          }
          break;

        case 'reprioritize_goal':
          // GoalManager doesn't expose a reprioritize method directly,
          // so we post the intent to the workspace for the MetaController.
          if (rec.goalId && rec.newPriority !== undefined) {
            this.workspace.post({
              type: 'goal_update',
              priority: rec.newPriority,
              payload: {
                action: 'reprioritize_request',
                goalId: rec.goalId,
                newPriority: rec.newPriority,
                source: 'reflection-l2',
              },
              sourceModule: 'reflection-engine',
              ttl: 60_000,
            });
          }
          break;

        case 'ignore':
        default:
          break;
      }
    }
  }

  // ── Layer 3: Deep Self-Modification (5-10min) ─────────────────

  private async reflectLayer3(request: ReflectionRequest): Promise<Layer3Result> {
    const start = Date.now();
    const activeGoals = this.goals.getActive();
    const allGoals = [
      ...this.goals.getByStatus('active'),
      ...this.goals.getByStatus('blocked'),
      ...this.goals.getByStatus('completed').slice(-10),
      ...this.goals.getByStatus('abandoned').slice(-5),
    ];

    const recentL2 = this.history
      .filter((r): r is Layer2Result => 'recommendations' in r)
      .slice(-5);

    const systemPrompt = LAYER3_SYSTEM;
    const userPrompt = this.buildLayer3Prompt(request, allGoals, recentL2);

    const raw = await this.llm.complete({
      model: this.config.layer3Model,
      system: systemPrompt,
      prompt: userPrompt,
      maxTokens: this.config.layer3MaxTokens,
    });

    const parsed = this.parseLayer3Response(raw, request.trigger);
    const durationMs = Date.now() - start;

    const result: Layer3Result = {
      ...parsed,
      durationMs,
    };

    // Post rule patches and insights to workspace
    if (result.rulePatches.length > 0) {
      this.workspace.post({
        type: 'reflection',
        priority: 9, // high priority — rule changes matter
        payload: {
          layer: 3,
          type: 'rule_patches',
          patches: result.rulePatches,
          confidence: result.confidence,
        },
        sourceModule: 'reflection-engine',
        ttl: 300_000, // 5 min TTL for rule patches
      });
    }

    if (result.strategyInsights.length > 0) {
      this.workspace.post({
        type: 'reflection',
        priority: 7,
        payload: {
          layer: 3,
          type: 'strategy_insights',
          insights: result.strategyInsights,
        },
        sourceModule: 'reflection-engine',
        ttl: 300_000,
      });
    }

    return result;
  }

  private buildLayer3Prompt(
    request: ReflectionRequest,
    allGoals: Goal[],
    recentL2: Layer2Result[],
  ): string {
    const goalSummary = allGoals.map(g =>
      `[${g.id.slice(0, 8)}] ${g.type}/${g.status} p=${g.priority} src=${g.source} "${g.description}"`,
    ).join('\n');

    const l2Summary = recentL2.map(r =>
      `L2 (${r.trigger}): confidence=${r.confidence}, recs=${r.recommendations.length}, "${r.analysis.slice(0, 80)}"`,
    ).join('\n');

    const contextStr = JSON.stringify(request.context, null, 2);

    return [
      `DEEP REFLECTION TRIGGER: ${request.trigger} (urgency=${request.urgency})`,
      `CONTEXT:\n${contextStr}`,
      `\nALL GOALS (${allGoals.length}):\n${goalSummary || 'none'}`,
      `\nRECENT LAYER-2 REFLECTIONS:\n${l2Summary || 'none'}`,
      `\nPerform a deep strategic review:`,
      `1. Are the current FSM rules effective? Propose patches if not.`,
      `2. Is the goal system balanced? (types, sources, priorities)`,
      `3. Are there systemic failure patterns?`,
      `4. What strategic adjustments would improve overall performance?`,
      `\nRespond in the JSON format described in your system prompt.`,
    ].join('\n');
  }

  private parseLayer3Response(raw: string, trigger: ReflectionTrigger): Omit<Layer3Result, 'durationMs'> {
    try {
      const jsonMatch = raw.match(/```(?:json)?\s*([\s\S]*?)```/) ?? raw.match(/(\{[\s\S]*\})/);
      if (!jsonMatch) throw new Error('No JSON found');

      const parsed = JSON.parse(jsonMatch[1].trim());
      return {
        trigger,
        analysis: parsed.analysis ?? raw.slice(0, 500),
        rulePatches: Array.isArray(parsed.rulePatches)
          ? parsed.rulePatches.map(this.sanitizeRulePatch)
          : [],
        strategyInsights: Array.isArray(parsed.strategyInsights)
          ? parsed.strategyInsights.filter((s: unknown) => typeof s === 'string')
          : [],
        confidence: Math.min(1, Math.max(0, parsed.confidence ?? 0.5)),
      };
    } catch {
      return {
        trigger,
        analysis: raw.slice(0, 500),
        rulePatches: [],
        strategyInsights: [],
        confidence: 0.2,
      };
    }
  }

  private sanitizeRulePatch(patch: Record<string, unknown>): RulePatch {
    return {
      id: typeof patch.id === 'string' ? patch.id : `patch-${Date.now()}`,
      description: typeof patch.description === 'string' ? patch.description : '',
      condition: typeof patch.condition === 'string' ? patch.condition : '',
      action: typeof patch.action === 'string' ? patch.action : '',
      priority: typeof patch.priority === 'number' ? patch.priority : 5,
    };
  }

  // ── Helpers ───────────────────────────────────────────────────

  private postToWorkspace(analysis: string, request: ReflectionRequest, priority: number): void {
    this.workspace.post({
      type: 'reflection',
      priority,
      payload: {
        layer: request.layer,
        trigger: request.trigger,
        analysis,
      },
      sourceModule: 'reflection-engine',
      ttl: request.layer === 2 ? 60_000 : 300_000,
    });
  }

  private makeDeferredResult(request: ReflectionRequest): Layer2Result | Layer3Result {
    if (request.layer === 2) {
      return {
        trigger: request.trigger,
        analysis: 'Reflection deferred due to concurrency limit.',
        recommendations: [],
        confidence: 0,
        durationMs: 0,
      };
    }
    return {
      trigger: request.trigger,
      analysis: 'Reflection deferred due to concurrency limit.',
      rulePatches: [],
      strategyInsights: [],
      confidence: 0,
      durationMs: 0,
    };
  }

  getHistory(): ReadonlyArray<Layer2Result | Layer3Result> {
    return this.history;
  }

  getActiveReflectionCount(): number {
    return this.activeReflections;
  }

  getConfig(): Readonly<ReflectionConfig> {
    return this.config;
  }

  updateConfig(patch: Partial<ReflectionConfig>): void {
    this.config = { ...this.config, ...patch };
  }
}

// ── System Prompts ─────────────────────────────────────────────────

const LAYER2_SYSTEM = `You are a fast metacognitive reflection module inside an autonomous cognitive architecture.
Your job is to quickly analyze situations and recommend concrete actions.

ALWAYS respond with valid JSON in this exact format:
{
  "analysis": "Brief analysis of the situation (1-3 sentences)",
  "recommendations": [
    {
      "action": "abandon_goal|reprioritize_goal|create_goal|unblock_goal|ignore",
      "goalId": "optional - first 8 chars of goal ID if targeting existing goal",
      "description": "What to do and why",
      "newPriority": 0-10,
      "goalParams": { "type": "research|task|exploration|practice|social|meta", "description": "...", "priority": 0-10, "source": "reflection" }
    }
  ],
  "confidence": 0.0-1.0
}

Rules:
- Be decisive. Pick the most impactful action.
- goalParams is only needed for "create_goal" actions.
- goalId is only needed for actions targeting existing goals.
- Maximum 3 recommendations per response.
- confidence reflects how certain you are about the analysis.`;

const LAYER3_SYSTEM = `You are a deep strategic reflection module inside an autonomous cognitive architecture.
You perform thorough self-modification reviews and propose FSM rule changes.

ALWAYS respond with valid JSON in this exact format:
{
  "analysis": "Thorough analysis of the system state and patterns (3-10 sentences)",
  "rulePatches": [
    {
      "id": "unique-patch-id",
      "description": "What this rule change does",
      "condition": "When this condition is met (human-readable)",
      "action": "Do this action (human-readable)",
      "priority": 0-10
    }
  ],
  "strategyInsights": [
    "Insight about the overall strategy",
    "Another insight"
  ],
  "confidence": 0.0-1.0
}

Rules:
- Be thorough and strategic. Consider second-order effects.
- Rule patches should be concrete enough to implement as FSM transitions.
- Strategy insights should identify systemic patterns, not individual goal issues.
- Maximum 5 rule patches and 5 strategy insights per response.
- confidence reflects certainty about the proposed changes.`;
