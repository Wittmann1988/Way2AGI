/** Core types for the Way2AGI cognitive architecture */

export type GoalStatus = 'proposed' | 'active' | 'blocked' | 'completed' | 'abandoned';
export type GoalType = 'research' | 'task' | 'exploration' | 'practice' | 'social' | 'meta';
export type DriveType = 'curiosity' | 'competence' | 'social' | 'autonomy';
export type ReflectionTrigger = 'failure_pattern' | 'novelty_spike' | 'goal_conflict' | 'timer' | 'user_feedback';

export interface Goal {
  id: string;
  type: GoalType;
  description: string;
  status: GoalStatus;
  priority: number; // 0-10
  parentId?: string;
  childIds: string[];
  context: Record<string, unknown>;
  createdAt: number;
  updatedAt: number;
  completedAt?: number;
  source: 'drive' | 'user' | 'reflection' | 'consolidation';
}

export interface DriveState {
  type: DriveType;
  activation: number; // 0.0-1.0
  lastSignal: number;
  history: Array<{ timestamp: number; activation: number }>;
}

export interface WorkspaceItem {
  id: string;
  type: 'perception' | 'goal_update' | 'plan_step' | 'internal_dialogue' | 'skill_request' | 'reflection' | 'drive_signal';
  priority: number;
  payload: unknown;
  timestamp: number;
  sourceModule: string;
  ttl: number; // ms before eviction
}

export interface ReflectionRequest {
  trigger: ReflectionTrigger;
  context: Record<string, unknown>;
  urgency: number; // 0-10
  layer: 2 | 3;
}

export interface MetaControllerState {
  currentFocus: WorkspaceItem | null;
  activeGoals: string[];
  driveStates: Map<DriveType, DriveState>;
  pendingReflections: ReflectionRequest[];
  ruleVersion: number;
  cycleCount: number;
}

export interface CognitiveEvent {
  type: string;
  payload: unknown;
  timestamp: number;
  source: string;
}
