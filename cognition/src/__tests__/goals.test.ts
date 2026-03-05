import { describe, it, expect } from 'vitest';
import { GlobalWorkspace } from '../workspace.js';
import { GoalManager } from '../goals/manager.js';
import type { Goal } from '../types.js';

function setup() {
  const workspace = new GlobalWorkspace();
  const goals = new GoalManager(workspace);
  return { workspace, goals };
}

describe('GoalManager', () => {
  describe('create()', () => {
    it('creates a goal with proposed status', () => {
      const { goals } = setup();
      const goal = goals.create({
        type: 'task',
        description: 'Test goal',
        priority: 5,
        source: 'user',
      });

      expect(goal.id).toBeTypeOf('string');
      expect(goal.status).toBe('proposed');
      expect(goal.description).toBe('Test goal');
      expect(goal.type).toBe('task');
      expect(goal.priority).toBe(5);
      expect(goal.source).toBe('user');
      expect(goal.childIds).toEqual([]);
      expect(goal.createdAt).toBeTypeOf('number');
    });

    it('clamps priority to 0-10 range', () => {
      const { goals } = setup();

      const tooHigh = goals.create({
        type: 'task',
        description: 'High',
        priority: 15,
        source: 'user',
      });
      expect(tooHigh.priority).toBe(10);

      const tooLow = goals.create({
        type: 'task',
        description: 'Low',
        priority: -3,
        source: 'user',
      });
      expect(tooLow.priority).toBe(0);
    });

    it('links child to parent', () => {
      const { goals } = setup();

      const parent = goals.create({
        type: 'task',
        description: 'Parent',
        priority: 7,
        source: 'user',
      });

      const child = goals.create({
        type: 'task',
        description: 'Child',
        priority: 5,
        parentId: parent.id,
        source: 'user',
      });

      expect(child.parentId).toBe(parent.id);
      const updatedParent = goals.getById(parent.id);
      expect(updatedParent?.childIds).toContain(child.id);
    });

    it('posts a goal_update event to workspace', () => {
      const { workspace, goals } = setup();
      const events: any[] = [];
      workspace.on('workspace:posted').subscribe(e => events.push(e));

      goals.create({
        type: 'research',
        description: 'Explore topic',
        priority: 6,
        source: 'drive',
      });

      // The workspace.post() inside create() emits a workspace:posted event
      // but since we subscribe on the observable, events pass through
      const goalItems = workspace.getItemsByType('goal_update');
      expect(goalItems.length).toBeGreaterThanOrEqual(1);
    });

    it('increments totalCount', () => {
      const { goals } = setup();
      expect(goals.totalCount).toBe(0);

      goals.create({ type: 'task', description: 'a', priority: 1, source: 'user' });
      goals.create({ type: 'task', description: 'b', priority: 2, source: 'user' });
      expect(goals.totalCount).toBe(2);
    });
  });

  describe('transition()', () => {
    it('transitions proposed -> active', () => {
      const { goals } = setup();
      const goal = goals.create({ type: 'task', description: 'x', priority: 5, source: 'user' });

      const ok = goals.transition(goal.id, 'active');
      expect(ok).toBe(true);
      expect(goals.getById(goal.id)?.status).toBe('active');
    });

    it('transitions active -> completed and sets completedAt', () => {
      const { goals } = setup();
      const goal = goals.create({ type: 'task', description: 'x', priority: 5, source: 'user' });
      goals.transition(goal.id, 'active');

      const ok = goals.transition(goal.id, 'completed');
      expect(ok).toBe(true);

      const updated = goals.getById(goal.id)!;
      expect(updated.status).toBe('completed');
      expect(updated.completedAt).toBeTypeOf('number');
    });

    it('transitions active -> blocked -> active', () => {
      const { goals } = setup();
      const goal = goals.create({ type: 'task', description: 'x', priority: 5, source: 'user' });
      goals.transition(goal.id, 'active');
      goals.transition(goal.id, 'blocked');
      expect(goals.getById(goal.id)?.status).toBe('blocked');

      const ok = goals.transition(goal.id, 'active');
      expect(ok).toBe(true);
      expect(goals.getById(goal.id)?.status).toBe('active');
    });

    it('rejects invalid transitions', () => {
      const { goals } = setup();
      const goal = goals.create({ type: 'task', description: 'x', priority: 5, source: 'user' });

      // proposed -> completed is NOT valid
      expect(goals.transition(goal.id, 'completed')).toBe(false);
      expect(goals.getById(goal.id)?.status).toBe('proposed');

      // proposed -> blocked is NOT valid
      expect(goals.transition(goal.id, 'blocked')).toBe(false);
    });

    it('rejects transitions from terminal states', () => {
      const { goals } = setup();
      const goal = goals.create({ type: 'task', description: 'x', priority: 5, source: 'user' });
      goals.transition(goal.id, 'active');
      goals.transition(goal.id, 'completed');

      // completed -> active is NOT valid
      expect(goals.transition(goal.id, 'active')).toBe(false);
      expect(goals.getById(goal.id)?.status).toBe('completed');
    });

    it('returns false for non-existent goal id', () => {
      const { goals } = setup();
      expect(goals.transition('nonexistent-id', 'active')).toBe(false);
    });
  });

  describe('parent-child completion', () => {
    it('auto-completes parent when all children are completed', () => {
      const { goals } = setup();

      const parent = goals.create({ type: 'task', description: 'parent', priority: 7, source: 'user' });
      goals.transition(parent.id, 'active');

      const child1 = goals.create({ type: 'task', description: 'c1', priority: 5, parentId: parent.id, source: 'user' });
      const child2 = goals.create({ type: 'task', description: 'c2', priority: 5, parentId: parent.id, source: 'user' });

      goals.transition(child1.id, 'active');
      goals.transition(child2.id, 'active');

      goals.transition(child1.id, 'completed');
      // Parent should still be active (child2 not done)
      expect(goals.getById(parent.id)?.status).toBe('active');

      goals.transition(child2.id, 'completed');
      // Now parent should auto-complete
      expect(goals.getById(parent.id)?.status).toBe('completed');
    });

    it('auto-completes parent when last child completes and others are abandoned', () => {
      const { goals } = setup();

      const parent = goals.create({ type: 'task', description: 'parent', priority: 7, source: 'user' });
      goals.transition(parent.id, 'active');

      const child1 = goals.create({ type: 'task', description: 'c1', priority: 5, parentId: parent.id, source: 'user' });
      const child2 = goals.create({ type: 'task', description: 'c2', priority: 5, parentId: parent.id, source: 'user' });

      goals.transition(child1.id, 'active');
      goals.transition(child2.id, 'active');

      // Abandon child2 first (does NOT trigger parent check -- only 'completed' does)
      goals.transition(child2.id, 'abandoned');
      expect(goals.getById(parent.id)?.status).toBe('active');

      // Complete child1 -- now checkParentCompletion fires and sees
      // child1=completed, child2=abandoned -> both terminal -> parent completes
      goals.transition(child1.id, 'completed');
      expect(goals.getById(parent.id)?.status).toBe('completed');
    });

    it('does NOT auto-complete parent with no children', () => {
      const { goals } = setup();

      const parent = goals.create({ type: 'task', description: 'childless', priority: 7, source: 'user' });
      goals.transition(parent.id, 'active');

      // No children to trigger auto-completion
      expect(goals.getById(parent.id)?.status).toBe('active');
    });
  });

  describe('getActive()', () => {
    it('returns only active goals', () => {
      const { goals } = setup();
      goals.create({ type: 'task', description: 'a', priority: 5, source: 'user' });
      const b = goals.create({ type: 'task', description: 'b', priority: 6, source: 'user' });
      const c = goals.create({ type: 'task', description: 'c', priority: 7, source: 'user' });

      goals.transition(b.id, 'active');
      goals.transition(c.id, 'active');

      const active = goals.getActive();
      expect(active).toHaveLength(2);
      expect(active.map(g => g.description).sort()).toEqual(['b', 'c']);
    });
  });

  describe('getTopPriority()', () => {
    it('returns top N active goals sorted by priority descending', () => {
      const { goals } = setup();

      const g1 = goals.create({ type: 'task', description: 'low', priority: 2, source: 'user' });
      const g2 = goals.create({ type: 'task', description: 'high', priority: 9, source: 'user' });
      const g3 = goals.create({ type: 'task', description: 'mid', priority: 5, source: 'user' });

      goals.transition(g1.id, 'active');
      goals.transition(g2.id, 'active');
      goals.transition(g3.id, 'active');

      const top2 = goals.getTopPriority(2);
      expect(top2).toHaveLength(2);
      expect(top2[0].priority).toBe(9);
      expect(top2[1].priority).toBe(5);
    });

    it('defaults to top 5', () => {
      const { goals } = setup();
      for (let i = 0; i < 8; i++) {
        const g = goals.create({ type: 'task', description: `g${i}`, priority: i, source: 'user' });
        goals.transition(g.id, 'active');
      }

      const top = goals.getTopPriority();
      expect(top).toHaveLength(5);
    });
  });

  describe('getAutonomous()', () => {
    it('returns active goals not from user source', () => {
      const { goals } = setup();

      const userGoal = goals.create({ type: 'task', description: 'user', priority: 5, source: 'user' });
      const driveGoal = goals.create({ type: 'exploration', description: 'drive', priority: 5, source: 'drive' });
      const reflGoal = goals.create({ type: 'meta', description: 'reflect', priority: 5, source: 'reflection' });

      goals.transition(userGoal.id, 'active');
      goals.transition(driveGoal.id, 'active');
      goals.transition(reflGoal.id, 'active');

      const autonomous = goals.getAutonomous();
      expect(autonomous).toHaveLength(2);
      expect(autonomous.every(g => g.source !== 'user')).toBe(true);
    });

    it('excludes non-active autonomous goals', () => {
      const { goals } = setup();

      // proposed (not active) drive goal
      goals.create({ type: 'exploration', description: 'proposed-drive', priority: 5, source: 'drive' });

      const activeGoal = goals.create({ type: 'task', description: 'active-drive', priority: 5, source: 'drive' });
      goals.transition(activeGoal.id, 'active');

      const autonomous = goals.getAutonomous();
      expect(autonomous).toHaveLength(1);
      expect(autonomous[0].description).toBe('active-drive');
    });
  });
});
