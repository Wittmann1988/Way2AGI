/**
 * Drive Registry — Intrinsic motivation system.
 *
 * Drives generate autonomous goals based on internal signals.
 * Inspired by intrinsic motivation research (Pathak et al., 2017)
 * and "Self-Improving Foundation Agents" (arXiv:2402.11450).
 */

import type { DriveState, DriveType, GlobalWorkspace } from '../index.js';

export interface DriveSignal {
  drive: DriveType;
  activation: number;
  reason: string;
  suggestedGoal?: {
    type: string;
    description: string;
    priority: number;
  };
}

export class DriveRegistry {
  private drives: Map<DriveType, DriveState> = new Map();
  private workspace: GlobalWorkspace;
  private activationThreshold = 0.6;

  constructor(workspace: GlobalWorkspace) {
    this.workspace = workspace;

    // Initialize all drives at baseline
    const driveTypes: DriveType[] = ['curiosity', 'competence', 'social', 'autonomy'];
    for (const type of driveTypes) {
      this.drives.set(type, {
        type,
        activation: 0.3, // baseline
        lastSignal: Date.now(),
        history: [],
      });
    }
  }

  /** Update a drive's activation level */
  signal(sig: DriveSignal): void {
    const drive = this.drives.get(sig.drive);
    if (!drive) return;

    drive.activation = Math.min(1.0, Math.max(0.0, sig.activation));
    drive.lastSignal = Date.now();
    drive.history.push({ timestamp: Date.now(), activation: sig.activation });

    // Keep history bounded (last 100 entries)
    if (drive.history.length > 100) {
      drive.history = drive.history.slice(-100);
    }

    // If activation exceeds threshold, post to workspace
    if (drive.activation >= this.activationThreshold) {
      this.workspace.post({
        type: 'drive_signal',
        priority: Math.round(sig.activation * 10),
        payload: sig,
        sourceModule: `drive:${sig.drive}`,
        ttl: 15_000,
      });
    }
  }

  /** Get drives that are above activation threshold */
  getActiveDrives(): DriveState[] {
    return [...this.drives.values()]
      .filter(d => d.activation >= this.activationThreshold)
      .sort((a, b) => b.activation - a.activation);
  }

  getState(type: DriveType): DriveState | undefined {
    return this.drives.get(type);
  }

  getAllStates(): DriveState[] {
    return [...this.drives.values()];
  }

  /** Decay all drives slightly (called each cycle to prevent runaway activation) */
  decayAll(factor = 0.995): void {
    for (const drive of this.drives.values()) {
      drive.activation = Math.max(0.1, drive.activation * factor);
    }
  }

  setThreshold(threshold: number): void {
    this.activationThreshold = Math.min(1.0, Math.max(0.0, threshold));
  }
}
