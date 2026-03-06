/**
 * AI-Driven Scheduler — Dynamic task scheduling.
 *
 * Unlike static cron jobs, Way2AGI's scheduler adjusts timing and priority
 * based on the cognitive state (active goals, drive activations, memory gaps).
 *
 * Tasks can be:
 * - Recurring (like cron, but with adaptive intervals)
 * - One-shot (triggered by goals or drives)
 * - Conditional (runs only when a condition is met)
 */

import type { GlobalWorkspace } from './workspace.js';
import type { GoalManager } from './goals/manager.js';

export interface ScheduledTask {
  id: string;
  name: string;
  description: string;
  handler: () => Promise<void>;
  schedule: TaskSchedule;
  lastRun: number;
  nextRun: number;
  runCount: number;
  enabled: boolean;
  priority: number; // 0-10, dynamically adjusted
}

export type TaskSchedule =
  | { type: 'interval'; baseMs: number; adaptive: boolean }
  | { type: 'cron'; expression: string }
  | { type: 'once'; at: number }
  | { type: 'condition'; check: () => boolean; pollMs: number }
  ;

export class CognitiveScheduler {
  private tasks: Map<string, ScheduledTask> = new Map();
  private timer: ReturnType<typeof setInterval> | null = null;
  private workspace: GlobalWorkspace;
  private goals: GoalManager;
  private tickMs = 1000; // Check every second

  constructor(workspace: GlobalWorkspace, goals: GoalManager) {
    this.workspace = workspace;
    this.goals = goals;
  }

  /** Register a scheduled task */
  register(task: Omit<ScheduledTask, 'lastRun' | 'nextRun' | 'runCount' | 'enabled'>): void {
    const nextRun = this.calculateNextRun(task.schedule);
    this.tasks.set(task.id, {
      ...task,
      lastRun: 0,
      nextRun,
      runCount: 0,
      enabled: true,
    });
  }

  /** Remove a task */
  unregister(id: string): void {
    this.tasks.delete(id);
  }

  /** Enable/disable a task */
  setEnabled(id: string, enabled: boolean): void {
    const task = this.tasks.get(id);
    if (task) task.enabled = enabled;
  }

  /** Start the scheduler loop */
  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => {
      this.tick().catch(err => console.error('[Scheduler] tick error:', err));
    }, this.tickMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  private async tick(): Promise<void> {
    const now = Date.now();

    for (const task of this.tasks.values()) {
      if (!task.enabled) continue;
      if (now < task.nextRun) continue;

      // Check conditional tasks
      if (task.schedule.type === 'condition' && !task.schedule.check()) {
        task.nextRun = now + task.schedule.pollMs;
        continue;
      }

      // Run the task
      try {
        await task.handler();
        task.lastRun = now;
        task.runCount++;

        // Adaptive scheduling: adjust interval based on cognitive state
        task.nextRun = this.calculateNextRun(task.schedule, task);

        // Post success to workspace
        this.workspace.post({
          type: 'internal_dialogue',
          priority: 3,
          payload: { task: task.name, status: 'completed', runCount: task.runCount },
          sourceModule: 'scheduler',
          ttl: 10_000,
        });
      } catch (err) {
        // Post failure to workspace (may trigger reflection)
        this.workspace.post({
          type: 'internal_dialogue',
          priority: 7,
          payload: {
            task: task.name,
            status: 'failed',
            error: err instanceof Error ? err.message : String(err),
          },
          sourceModule: 'scheduler',
          ttl: 30_000,
        });

        // Back off on failure
        task.nextRun = now + (task.schedule.type === 'interval' ? task.schedule.baseMs * 2 : 60_000);
      }

      // Remove one-shot tasks after execution
      if (task.schedule.type === 'once') {
        this.tasks.delete(task.id);
      }
    }
  }

  private calculateNextRun(schedule: TaskSchedule, task?: ScheduledTask): number {
    const now = Date.now();

    switch (schedule.type) {
      case 'interval': {
        let interval = schedule.baseMs;

        // Adaptive: speed up if related goals are active
        if (schedule.adaptive && task) {
          const activeGoals = this.goals.getActive().length;
          if (activeGoals > 5) {
            interval = Math.max(interval * 0.5, 5000); // Speed up, min 5s
          } else if (activeGoals === 0) {
            interval = interval * 2; // Slow down when idle
          }
        }

        return now + interval;
      }

      case 'cron':
        // Simple cron-like parsing (minute-level only for now)
        return now + 60_000; // TODO: proper cron expression parsing

      case 'once':
        return schedule.at;

      case 'condition':
        return now + schedule.pollMs;
    }
  }

  /** Get all registered tasks with status */
  getStatus(): Array<{
    id: string;
    name: string;
    enabled: boolean;
    lastRun: number;
    nextRun: number;
    runCount: number;
  }> {
    return [...this.tasks.values()].map(t => ({
      id: t.id,
      name: t.name,
      enabled: t.enabled,
      lastRun: t.lastRun,
      nextRun: t.nextRun,
      runCount: t.runCount,
    }));
  }

  get taskCount(): number {
    return this.tasks.size;
  }
}

/** Pre-built tasks for Way2AGI */
export function registerDefaultTasks(
  scheduler: CognitiveScheduler,
  memoryUrl: string,
): void {
  // Memory consolidation — every 6 hours, adaptive
  scheduler.register({
    id: 'memory-consolidation',
    name: 'Memory Consolidation',
    description: 'Consolidate episodic memories into semantic/procedural',
    priority: 6,
    schedule: { type: 'interval', baseMs: 6 * 3600_000, adaptive: true },
    handler: async () => {
      const res = await fetch(`${memoryUrl}/memory/consolidate`, { method: 'POST' });
      if (!res.ok) throw new Error(`Consolidation failed: ${res.status}`);
    },
  });

  // Knowledge gap scan — every 30 min, adaptive
  scheduler.register({
    id: 'knowledge-gap-scan',
    name: 'Knowledge Gap Scan',
    description: 'Scan for knowledge gaps to feed the Curiosity Drive',
    priority: 5,
    schedule: { type: 'interval', baseMs: 30 * 60_000, adaptive: true },
    handler: async () => {
      const res = await fetch(`${memoryUrl}/memory/knowledge-gaps`);
      if (!res.ok) throw new Error(`Gap scan failed: ${res.status}`);
      // Results feed into the Initiative Engine via workspace
    },
  });

  // Health check — every 5 min
  scheduler.register({
    id: 'health-check',
    name: 'System Health Check',
    description: 'Verify all components are running',
    priority: 3,
    schedule: { type: 'interval', baseMs: 5 * 60_000, adaptive: false },
    handler: async () => {
      const res = await fetch(`${memoryUrl}/health`);
      if (!res.ok) throw new Error('Memory server unhealthy');
    },
  });
}
