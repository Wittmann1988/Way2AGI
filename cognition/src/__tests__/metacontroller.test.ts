import { describe, it, expect, vi, afterEach } from 'vitest';
import { GlobalWorkspace } from '../workspace.js';
import { GoalManager } from '../goals/manager.js';
import { DriveRegistry } from '../drives/registry.js';
import { MetaController } from '../metacontroller.js';
import type { ReflectionRequest } from '../types.js';

function setup() {
  const workspace = new GlobalWorkspace();
  const goals = new GoalManager(workspace);
  const drives = new DriveRegistry(workspace);
  const controller = new MetaController(workspace, goals, drives);
  return { workspace, goals, drives, controller };
}

describe('MetaController', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('start() / stop() lifecycle', () => {
    it('starts the control loop (interval)', () => {
      vi.useFakeTimers();
      const { controller } = setup();

      controller.start();
      const state1 = controller.getState();
      expect(state1.cycleCount).toBe(0);

      // Advance 500ms to trigger one cycle
      vi.advanceTimersByTime(500);
      expect(controller.getState().cycleCount).toBe(1);

      // Advance another 500ms
      vi.advanceTimersByTime(500);
      expect(controller.getState().cycleCount).toBe(2);

      controller.stop();
    });

    it('stop() stops the loop', () => {
      vi.useFakeTimers();
      const { controller } = setup();

      controller.start();
      vi.advanceTimersByTime(500);
      expect(controller.getState().cycleCount).toBe(1);

      controller.stop();
      vi.advanceTimersByTime(2000);
      // Should still be 1 since loop was stopped
      expect(controller.getState().cycleCount).toBe(1);
    });

    it('start() is idempotent (calling twice does not create double loops)', () => {
      vi.useFakeTimers();
      const { controller } = setup();

      controller.start();
      controller.start(); // second call should be ignored

      vi.advanceTimersByTime(500);
      // Should only have 1 cycle, not 2 (which would happen with double intervals)
      expect(controller.getState().cycleCount).toBe(1);

      controller.stop();
    });

    it('returns idle phase after stop', () => {
      vi.useFakeTimers();
      const { controller } = setup();

      controller.start();
      vi.advanceTimersByTime(500);
      controller.stop();

      expect(controller.getPhase()).toBe('idle');
    });
  });

  describe('cycle() processes workspace items', () => {
    it('selects focus from workspace during cycle', () => {
      vi.useFakeTimers();
      const { workspace, controller } = setup();

      workspace.post({
        type: 'perception',
        priority: 8,
        payload: { data: 'test' },
        sourceModule: 'sensor',
        ttl: 30_000,
      });

      controller.start();
      vi.advanceTimersByTime(500);

      const state = controller.getState();
      expect(state.currentFocus).not.toBeNull();
      // The focus may be the perception or a goal_update (from GoalManager interactions)
      // but currentFocus should be set
      controller.stop();
    });

    it('activates high-priority proposed goals when drive_signal is focused', () => {
      vi.useFakeTimers();
      const { workspace, goals, drives, controller } = setup();

      // Create a proposed goal with priority >= 5
      const goal = goals.create({
        type: 'exploration',
        description: 'Explore something',
        priority: 7,
        source: 'drive',
      });
      expect(goals.getById(goal.id)?.status).toBe('proposed');

      // Signal a drive above threshold to post drive_signal to workspace
      drives.signal({ drive: 'curiosity', activation: 0.9, reason: 'high novelty' });

      controller.start();
      vi.advanceTimersByTime(500);

      // After the cycle, the proposed goal should have been activated
      // (if drive_signal was the highest priority focus)
      controller.stop();

      // The goal may or may not be activated depending on what focus was selected
      // but the mechanism should work for the right conditions
      const updated = goals.getById(goal.id);
      // drive_signal priority = round(0.9*10) = 9, which is high
      // goal_update priority = 7, so drive_signal should win focus
      expect(updated?.status).toBe('active');
    });
  });

  describe('reflection triggers', () => {
    it('triggers failure_pattern reflection after 3 consecutive failures', () => {
      vi.useFakeTimers();
      const { controller } = setup();
      const reflections: ReflectionRequest[] = [];

      controller.onReflection(req => reflections.push(req));

      // Record 3 failures
      controller.recordFailure();
      controller.recordFailure();
      controller.recordFailure();

      // Run a cycle to trigger the check
      controller.start();
      vi.advanceTimersByTime(500);
      controller.stop();

      const failureReflection = reflections.find(r => r.trigger === 'failure_pattern');
      expect(failureReflection).toBeDefined();
      expect(failureReflection!.layer).toBe(2);
      expect(failureReflection!.urgency).toBe(8);
    });

    it('triggers timer reflection every 600 cycles', () => {
      vi.useFakeTimers();
      const { controller } = setup();
      const reflections: ReflectionRequest[] = [];

      controller.onReflection(req => reflections.push(req));

      controller.start();
      // Advance to 600 cycles (600 * 500ms = 300_000ms)
      vi.advanceTimersByTime(300_000);
      controller.stop();

      const timerReflection = reflections.find(r => r.trigger === 'timer');
      expect(timerReflection).toBeDefined();
      expect(timerReflection!.layer).toBe(3);
    });

    it('triggers goal_conflict when >3 active goals', () => {
      vi.useFakeTimers();
      const { goals, controller } = setup();
      const reflections: ReflectionRequest[] = [];

      controller.onReflection(req => reflections.push(req));

      // Create and activate 4 goals
      for (let i = 0; i < 4; i++) {
        const g = goals.create({
          type: 'task',
          description: `goal-${i}`,
          priority: 5 + i,
          source: 'user',
        });
        goals.transition(g.id, 'active');
      }

      controller.start();
      vi.advanceTimersByTime(500);
      controller.stop();

      const conflictReflection = reflections.find(r => r.trigger === 'goal_conflict');
      expect(conflictReflection).toBeDefined();
      expect(conflictReflection!.layer).toBe(2);
      expect(conflictReflection!.urgency).toBe(5);
    });

    it('does NOT trigger goal_conflict with <=3 active goals', () => {
      vi.useFakeTimers();
      const { goals, controller } = setup();
      const reflections: ReflectionRequest[] = [];

      controller.onReflection(req => reflections.push(req));

      // Create and activate exactly 3 goals
      for (let i = 0; i < 3; i++) {
        const g = goals.create({
          type: 'task',
          description: `goal-${i}`,
          priority: 5,
          source: 'user',
        });
        goals.transition(g.id, 'active');
      }

      controller.start();
      vi.advanceTimersByTime(500);
      controller.stop();

      const conflictReflection = reflections.find(r => r.trigger === 'goal_conflict');
      expect(conflictReflection).toBeUndefined();
    });
  });

  describe('getState()', () => {
    it('returns initial state correctly', () => {
      const { controller } = setup();
      const state = controller.getState();

      expect(state.cycleCount).toBe(0);
      expect(state.currentFocus).toBeNull();
      expect(state.activeGoals).toEqual([]);
      expect(state.pendingReflections).toEqual([]);
      expect(state.ruleVersion).toBe(1);
    });
  });

  describe('recordFailure()', () => {
    it('accumulates failures and resets after reflection', () => {
      vi.useFakeTimers();
      const { controller } = setup();
      const reflections: ReflectionRequest[] = [];

      controller.onReflection(req => reflections.push(req));

      // 2 failures: not enough
      controller.recordFailure();
      controller.recordFailure();

      controller.start();
      vi.advanceTimersByTime(500);

      expect(reflections.filter(r => r.trigger === 'failure_pattern')).toHaveLength(0);

      // 1 more failure: now at 3
      controller.recordFailure();
      vi.advanceTimersByTime(500);

      expect(reflections.filter(r => r.trigger === 'failure_pattern')).toHaveLength(1);

      // After triggering, counter resets: 1 more failure should not trigger
      controller.recordFailure();
      vi.advanceTimersByTime(500);

      expect(reflections.filter(r => r.trigger === 'failure_pattern')).toHaveLength(1);

      controller.stop();
    });
  });
});
