/**
 * Metacognitive Controller — Layer 1 (Hybrid Event-Driven + Heartbeat).
 *
 * FSM + Priority Queue. Handles 92% of decisions deterministically.
 * Triggers Layer 2/3 LLM reflection when needed.
 *
 * Event-driven reactions for new workspace items, slow heartbeat (5s)
 * for maintenance (decay, staleness, timer-based reflection).
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
import type { Subscription } from 'rxjs';
import { createLogger } from './logger.js';

type ControllerPhase = 'idle' | 'perceiving' | 'deciding' | 'acting' | 'reflecting';

const HEARTBEAT_INTERVAL = 5_000; // 5s heartbeat for maintenance
const REACTION_DEBOUNCE = 50; // ms — batch items arriving within this window
const REFLECTION_TIMER_MS = 5 * 60 * 1_000; // 5 minutes between timer reflections
const FAILURE_THRESHOLD = 3; // consecutive failures before triggering reflection
const NOVELTY_THRESHOLD = 0.8;
const MAX_PENDING_REFLECTIONS = 20;
const GOAL_CONFLICT_COOLDOWN_MS = 60_000; // 60s between goal_conflict reflections

export class MetaController {
  private workspace: GlobalWorkspace;
  private goals: GoalManager;
  private drives: DriveRegistry;
  private state: MetaControllerState;
  private phase: ControllerPhase = 'idle';
  private timer: ReturnType<typeof setInterval> | null = null;
  private failureCount = 0;
  private onReflectionRequest?: (req: ReflectionRequest) => void;
  private log = createLogger('metacontroller');

  // Event-driven state
  private subscription: Subscription | null = null;
  private pendingReactions: WorkspaceItem[] = [];
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private lastReflectionTime = 0;
  private lastGoalConflictTime = 0;

  // Metrics
  private _reactionsCount = 0;
  private _idleCycles = 0;

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

  /** Start the hybrid control loop (event-driven + heartbeat) */
  start(): void {
    if (this.timer) return;

    this.lastReflectionTime = Date.now();

    // Subscribe to workspace events for immediate reactions
    this.subscription = this.workspace.on('workspace:posted').subscribe(event => {
      const item = event.payload as WorkspaceItem;
      this.pendingReactions.push(item);

      // Debounce: batch items arriving within REACTION_DEBOUNCE ms
      if (!this.debounceTimer) {
        this.debounceTimer = setTimeout(() => {
          this.debounceTimer = null;
          this.flushReactions();
        }, REACTION_DEBOUNCE);
      }
    });

    // Slow heartbeat for maintenance tasks
    this.timer = setInterval(() => this.heartbeat(), HEARTBEAT_INTERVAL);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.subscription) {
      this.subscription.unsubscribe();
      this.subscription = null;
    }
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
  }

  /** Register callback for when reflection is needed (Layer 2/3) */
  onReflection(handler: (req: ReflectionRequest) => void): void {
    this.onReflectionRequest = handler;
  }

  /** Whether the system is idle (nothing to process) */
  get isIdle(): boolean {
    return (
      this.workspace.size === 0 &&
      this.state.activeGoals.length === 0 &&
      this.drives.getActiveDrives().length === 0
    );
  }

  /** Metrics: number of event-driven reaction batches */
  get reactionsCount(): number {
    return this._reactionsCount;
  }

  /** Metrics: number of skipped heartbeat cycles due to idle */
  get idleCycles(): number {
    return this._idleCycles;
  }

  /** Process batched reactions from workspace events */
  private flushReactions(): void {
    const items = this.pendingReactions.splice(0);
    if (items.length === 0) return;

    this._reactionsCount++;
    this.log.debug('reactTo batch', { count: items.length });

    for (const item of items) {
      this.reactTo(item);
    }
  }

  /** React immediately to a single workspace item (event-driven path) */
  private reactTo(item: WorkspaceItem): void {
    try {
      this.phase = 'deciding';
      this.applyRules(item);

      this.phase = 'acting';
      this.processDrives();
    } catch (err) {
      this.log.error('reactTo error', { phase: this.phase, error: String(err) });
    }

    this.phase = 'idle';
  }

  /** Heartbeat — slow maintenance cycle (every 5s) */
  private heartbeat(): void {
    this.state.cycleCount++;

    // If idle, skip heavy processing
    if (this.isIdle) {
      this._idleCycles++;
      if (this.state.cycleCount % 10 === 0) {
        this.log.debug('heartbeat idle', { cycleCount: this.state.cycleCount, idleCycles: this._idleCycles });
      }
      // Still check timer-based reflection even when idle
      this.checkReflectionTriggers();
      return;
    }

    // Full maintenance cycle
    this.cycle();
  }

  /** Single control cycle (~<50ms target) — used by heartbeat for maintenance */
  private cycle(): void {
    if (this.state.cycleCount % 100 === 0) {
      this.log.debug('cycle tick', { cycleCount: this.state.cycleCount });
    }

    try {
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
    } catch (err) {
      this.log.error('phase error', { phase: this.phase, error: String(err) });
    }

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

    // Trigger 2: Timer-based deep reflection (every 5 minutes of wall-clock time)
    const now = Date.now();
    if (now - this.lastReflectionTime >= REFLECTION_TIMER_MS) {
      this.lastReflectionTime = now;
      this.requestReflection('timer', {
        cycleCount: this.state.cycleCount,
        activeGoals: this.state.activeGoals.length,
        ruleVersion: this.state.ruleVersion,
      }, 3, 3);
    }

    // Trigger 3: Goal conflicts (>3 active goals competing for attention, with cooldown)
    const now2 = Date.now();
    if (this.state.activeGoals.length > 3 &&
        now2 - this.lastGoalConflictTime >= GOAL_CONFLICT_COOLDOWN_MS) {
      this.lastGoalConflictTime = now2;
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
    // Bound pending reflections to prevent memory leak
    if (this.state.pendingReflections.length >= MAX_PENDING_REFLECTIONS) {
      this.state.pendingReflections.shift();
    }
    this.state.pendingReflections.push(req);
    this.log.info('reflection triggered', { trigger, urgency, layer, context });
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
