/**
 * Goal Manager — Hierarchical Goal DAG with lifecycle.
 *
 * Goals form a directed acyclic graph. Parent goals decompose into
 * sub-goals. The manager tracks status transitions and notifies
 * the workspace when goals change.
 */

import { v4 as uuid } from 'uuid';
import type { Goal, GoalStatus, GoalType } from '../types.js';
import type { GlobalWorkspace } from '../workspace.js';

export class GoalManager {
  private goals: Map<string, Goal> = new Map();
  private workspace: GlobalWorkspace;

  constructor(workspace: GlobalWorkspace) {
    this.workspace = workspace;
  }

  create(params: {
    type: GoalType;
    description: string;
    priority: number;
    parentId?: string;
    context?: Record<string, unknown>;
    source: Goal['source'];
  }): Goal {
    const goal: Goal = {
      id: uuid(),
      type: params.type,
      description: params.description,
      status: 'proposed',
      priority: Math.min(10, Math.max(0, params.priority)),
      parentId: params.parentId,
      childIds: [],
      context: params.context ?? {},
      createdAt: Date.now(),
      updatedAt: Date.now(),
      source: params.source,
    };

    this.goals.set(goal.id, goal);

    // Link to parent
    if (params.parentId) {
      const parent = this.goals.get(params.parentId);
      if (parent) {
        parent.childIds.push(goal.id);
        parent.updatedAt = Date.now();
      }
    }

    this.workspace.post({
      type: 'goal_update',
      priority: goal.priority,
      payload: { action: 'created', goal },
      sourceModule: 'goal-manager',
      ttl: 60_000,
    });

    return goal;
  }

  transition(goalId: string, newStatus: GoalStatus): boolean {
    const goal = this.goals.get(goalId);
    if (!goal) return false;

    const validTransitions: Record<GoalStatus, GoalStatus[]> = {
      proposed: ['active', 'abandoned'],
      active: ['blocked', 'completed', 'abandoned'],
      blocked: ['active', 'abandoned'],
      completed: [],
      abandoned: [],
    };

    if (!validTransitions[goal.status].includes(newStatus)) return false;

    goal.status = newStatus;
    goal.updatedAt = Date.now();
    if (newStatus === 'completed') goal.completedAt = Date.now();

    this.workspace.post({
      type: 'goal_update',
      priority: goal.priority,
      payload: { action: 'transitioned', goal, newStatus },
      sourceModule: 'goal-manager',
      ttl: 60_000,
    });

    // If completed, check if parent can also be completed
    if (newStatus === 'completed' && goal.parentId) {
      this.checkParentCompletion(goal.parentId);
    }

    return true;
  }

  getActive(): Goal[] {
    return [...this.goals.values()].filter(g => g.status === 'active');
  }

  getByStatus(status: GoalStatus): Goal[] {
    return [...this.goals.values()].filter(g => g.status === status);
  }

  getById(id: string): Goal | undefined {
    return this.goals.get(id);
  }

  getTopPriority(n = 5): Goal[] {
    return this.getActive()
      .sort((a, b) => b.priority - a.priority)
      .slice(0, n);
  }

  /** Get all autonomous goals (not user-initiated) */
  getAutonomous(): Goal[] {
    return [...this.goals.values()]
      .filter(g => g.source !== 'user' && g.status === 'active');
  }

  get totalCount(): number {
    return this.goals.size;
  }

  private checkParentCompletion(parentId: string): void {
    const parent = this.goals.get(parentId);
    if (!parent) return;

    const allChildrenDone = parent.childIds.every(cid => {
      const child = this.goals.get(cid);
      return child?.status === 'completed' || child?.status === 'abandoned';
    });

    if (allChildrenDone && parent.childIds.length > 0) {
      this.transition(parentId, 'completed');
    }
  }
}
