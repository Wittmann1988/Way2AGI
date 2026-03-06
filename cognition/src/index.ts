/**
 * @way2agi/cognition — Cognitive Core
 *
 * The mind of Way2AGI. Provides:
 * - Global Workspace (GWT-inspired blackboard)
 * - Goal Manager (hierarchical DAG)
 * - Drive Registry (intrinsic motivation)
 * - MetaController (fast 500ms FSM loop)
 * - Initiative Engine (autonomous goal generation)
 */

import { GlobalWorkspace } from './workspace.js';
import { GoalManager } from './goals/manager.js';
import { DriveRegistry } from './drives/registry.js';
import { MetaController } from './metacontroller.js';
import { InitiativeEngine } from './initiative.js';
import { InternalMonologue } from './monologue.js';
import { CognitiveScheduler, registerDefaultTasks } from './scheduler.js';

export { GlobalWorkspace } from './workspace.js';
export { GoalManager } from './goals/manager.js';
export { DriveRegistry } from './drives/registry.js';
export type { DriveSignal } from './drives/registry.js';
export { MetaController } from './metacontroller.js';
export { InitiativeEngine } from './initiative.js';
export type { MemoryBridge } from './initiative.js';
export { InternalMonologue } from './monologue.js';
export type { Thought, ThoughtType } from './monologue.js';
export { CognitiveScheduler, registerDefaultTasks } from './scheduler.js';
export type { ScheduledTask, TaskSchedule } from './scheduler.js';
export { ReflectionEngine } from './reflection.js';
export type {
  LLMClient,
  Layer2Result,
  Layer2Recommendation,
  Layer3Result,
  RulePatch,
  ReflectionConfig,
} from './reflection.js';

export type {
  Goal,
  GoalStatus,
  GoalType,
  DriveState,
  DriveType,
  WorkspaceItem,
  ReflectionRequest,
  ReflectionTrigger,
  MetaControllerState,
  CognitiveEvent,
} from './types.js';

/** Bootstrap a complete cognitive system */
export function createCognitiveCore() {
  const workspace = new GlobalWorkspace();
  const goals = new GoalManager(workspace);
  const drives = new DriveRegistry(workspace);
  const controller = new MetaController(workspace, goals, drives);
  const initiative = new InitiativeEngine(workspace, goals, drives);

  const monologue = new InternalMonologue();
  const scheduler = new CognitiveScheduler(workspace, goals);

  return { workspace, goals, drives, controller, initiative, monologue, scheduler };
}
