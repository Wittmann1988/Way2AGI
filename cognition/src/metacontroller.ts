/**
 * Metacognitive Controller — Layer 1 (Fast Loop, 500ms).
 *
 * FSM + Priority Queue. Handles 92% of decisions deterministically.
 * Triggers Layer 2/3 LLM reflection when needed.
 *
 * Based on "Metacognitive Control in LLM Agents via Fast-Slow Loops" (ICML 2025)
 * and "Reflexion Hybrid" (2025).
 */

import type {
  MetaControllerState,
  ReflectionRequest,
  ReflectionTrigger,
  WorkspaceItem,
} from './types.js';
import type { GlobalWorkspace } from './workspace.js';
import type { GoalManager } from './goals/manager.js';
import type { DriveRegistry } from './drives/registry.js';

type ControllerPhase = 'idle' | 'perceiving' | 'deciding' | 'acting' | 'reflecting';

const CYCLE_INTERVAL = 500; // ms
const FAILURE_THRESHOLD = 3; // consecutive failures before triggering reflection
const NOVELTY_THRESHOLD = 0.8;

export class MetaController {
  private workspace: GlobalWorkspace;
  private goals: GoalManager;
  private drives: DriveRegistry;
  private state: MetaControllerState;
  private phase: ControllerPhase = 'idle';
  private timer: ReturnType<typeof setInterval> | null = null;
  private failureCount = 0;
  private onReflectionRequest?: (req: ReflectionRequest) => void;

  constructor(
    workspace: GlobalWorkspace,
    goals: GoalManager,
    drives: DriveRegistry,
  ) {
    this.workspace = workspace;
    this.goals = goals;
    this.drives = drives;
    this.state = {
      currentFocus: null,
      activeGoals: [],
      driveStates: new Map(),
      pendingReflections: [],
      ruleVersion: 1,
      cycleCount: 0,
    };
  }

  /** Start the fast control loop */
  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => this.cycle(), CYCLE_INTERVAL);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  /** Register callback for when reflection is needed (Layer 2/3) */
  onReflection(handler: (req: ReflectionRequest) => void): void {
    this.onReflectionRequest = handler;
  }

  /** Single control cycle (~<50ms target) */
  private cycle(): void {
    this.state.cycleCount++;

    // Phase 1: Perceive — scan workspace
    this.phase = 'perceiving';
    const focus = this.workspace.selectFocus();
    this.state.currentFocus = focus;

    // Phase 2: Decide — apply rules
    this.phase = 'deciding';
    this.applyRules(focus);

    // Phase 3: Act — process drive signals, manage goals
    this.phase = 'acting';
    this.processDrives();
    this.updateGoalStates();

    // Phase 4: Check reflection triggers
    this.phase = 'reflecting';
    this.checkReflectionTriggers();

    // Decay drives slightly each cycle
    this.drives.decayAll();

    this.phase = 'idle';
  }

  private applyRules(focus: WorkspaceItem | null): void {
    if (!focus) return;

    switch (focus.type) {
      case 'drive_signal':
        // High-priority drive → activate proposed goals matching the drive
        this.activateGoalsForDrive(focus);
        break;

      case 'goal_update': {
        const update = focus.payload as { action: string; goal: { status: string } };
        if (update.action === 'transitioned' && update.goal.status === 'completed') {
          this.failureCount = 0; // reset on success
        }
        break;
      }

      case 'perception':
        // External input → check if any drive should respond
        this.evaluatePerception(focus);
        break;
    }
  }

  private activateGoalsForDrive(item: WorkspaceItem): void {
    const proposed = this.goals.getByStatus('proposed');
    for (const goal of proposed) {
      if (goal.priority >= 5) {
        this.goals.transition(goal.id, 'active');
      }
    }
  }

  private evaluatePerception(item: WorkspaceItem): void {
    // Simple novelty check — if payload has a novelty score
    const payload = item.payload as Record<string, unknown>;
    const novelty = (payload?.novelty as number) ?? 0;

    if (novelty > NOVELTY_THRESHOLD) {
      this.drives.signal({
        drive: 'curiosity',
        activation: novelty,
        reason: `High novelty perception: ${JSON.stringify(payload).slice(0, 100)}`,
      });
    }
  }

  private processDrives(): void {
    const activeDrives = this.drives.getActiveDrives();
    this.state.driveStates = new Map(
      this.drives.getAllStates().map(d => [d.type, d]),
    );

    // Update active goals list
    this.state.activeGoals = this.goals.getActive().map(g => g.id);
  }

  private updateGoalStates(): void {
    // Auto-abandon stale goals (>1h without progress)
    const active = this.goals.getActive();
    const now = Date.now();
    for (const goal of active) {
      if (now - goal.updatedAt > 3_600_000) {
        this.goals.transition(goal.id, 'abandoned');
      }
    }
  }

  private checkReflectionTriggers(): void {
    // Trigger 1: Consecutive failures
    if (this.failureCount >= FAILURE_THRESHOLD) {
      this.requestReflection('failure_pattern', { failureCount: this.failureCount }, 8, 2);
      this.failureCount = 0;
    }

    // Trigger 2: Timer-based deep reflection (every 600 cycles = ~5min)
    if (this.state.cycleCount % 600 === 0) {
      this.requestReflection('timer', {
        cycleCount: this.state.cycleCount,
        activeGoals: this.state.activeGoals.length,
        ruleVersion: this.state.ruleVersion,
      }, 3, 3);
    }

    // Trigger 3: Goal conflicts (>3 active goals competing for attention)
    if (this.state.activeGoals.length > 3) {
      this.requestReflection('goal_conflict', {
        goalCount: this.state.activeGoals.length,
      }, 5, 2);
    }
  }

  private requestReflection(
    trigger: ReflectionTrigger,
    context: Record<string, unknown>,
    urgency: number,
    layer: 2 | 3,
  ): void {
    const req: ReflectionRequest = { trigger, context, urgency, layer };
    this.state.pendingReflections.push(req);
    this.onReflectionRequest?.(req);
  }

  recordFailure(): void {
    this.failureCount++;
  }

  getState(): Readonly<MetaControllerState> {
    return this.state;
  }

  getPhase(): ControllerPhase {
    return this.phase;
  }
}
