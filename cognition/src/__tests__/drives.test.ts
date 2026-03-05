import { describe, it, expect } from 'vitest';
import { GlobalWorkspace } from '../workspace.js';
import { DriveRegistry } from '../drives/registry.js';
import type { DriveSignal } from '../drives/registry.js';

function setup() {
  const workspace = new GlobalWorkspace();
  const drives = new DriveRegistry(workspace);
  return { workspace, drives };
}

describe('DriveRegistry', () => {
  describe('initialization', () => {
    it('initializes all four drives at baseline 0.3', () => {
      const { drives } = setup();
      const all = drives.getAllStates();
      expect(all).toHaveLength(4);

      for (const drive of all) {
        expect(drive.activation).toBeCloseTo(0.3);
        expect(drive.history).toEqual([]);
        expect(['curiosity', 'competence', 'social', 'autonomy']).toContain(drive.type);
      }
    });
  });

  describe('signal()', () => {
    it('updates drive activation level', () => {
      const { drives } = setup();

      drives.signal({ drive: 'curiosity', activation: 0.8, reason: 'new data' });

      const state = drives.getState('curiosity');
      expect(state?.activation).toBeCloseTo(0.8);
    });

    it('clamps activation to [0.0, 1.0]', () => {
      const { drives } = setup();

      drives.signal({ drive: 'curiosity', activation: 1.5, reason: 'overflow' });
      expect(drives.getState('curiosity')?.activation).toBeCloseTo(1.0);

      drives.signal({ drive: 'curiosity', activation: -0.5, reason: 'underflow' });
      expect(drives.getState('curiosity')?.activation).toBeCloseTo(0.0);
    });

    it('appends to history', () => {
      const { drives } = setup();

      drives.signal({ drive: 'competence', activation: 0.5, reason: 'r1' });
      drives.signal({ drive: 'competence', activation: 0.7, reason: 'r2' });

      const state = drives.getState('competence');
      expect(state?.history).toHaveLength(2);
      expect(state?.history[0].activation).toBe(0.5);
      expect(state?.history[1].activation).toBe(0.7);
    });

    it('posts to workspace when activation >= threshold (0.6)', () => {
      const { workspace, drives } = setup();

      // Below threshold - should NOT post
      drives.signal({ drive: 'curiosity', activation: 0.5, reason: 'below' });
      expect(workspace.getItemsByType('drive_signal')).toHaveLength(0);

      // At threshold - should post
      drives.signal({ drive: 'curiosity', activation: 0.6, reason: 'at' });
      expect(workspace.getItemsByType('drive_signal')).toHaveLength(1);

      // Above threshold - should post
      drives.signal({ drive: 'curiosity', activation: 0.9, reason: 'above' });
      expect(workspace.getItemsByType('drive_signal')).toHaveLength(2);
    });

    it('ignores signals for unknown drive types', () => {
      const { drives } = setup();
      // Should not throw
      drives.signal({ drive: 'nonexistent' as any, activation: 0.8, reason: 'nope' });
      expect(drives.getState('nonexistent' as any)).toBeUndefined();
    });
  });

  describe('getActiveDrives()', () => {
    it('returns empty array when all drives below threshold', () => {
      const { drives } = setup();
      // Default activation is 0.3, threshold is 0.6
      expect(drives.getActiveDrives()).toHaveLength(0);
    });

    it('returns drives above threshold, sorted by activation descending', () => {
      const { drives } = setup();

      drives.signal({ drive: 'curiosity', activation: 0.7, reason: 'x' });
      drives.signal({ drive: 'autonomy', activation: 0.9, reason: 'y' });
      drives.signal({ drive: 'social', activation: 0.5, reason: 'z' }); // below threshold

      const active = drives.getActiveDrives();
      expect(active).toHaveLength(2);
      expect(active[0].type).toBe('autonomy');
      expect(active[0].activation).toBeCloseTo(0.9);
      expect(active[1].type).toBe('curiosity');
      expect(active[1].activation).toBeCloseTo(0.7);
    });

    it('respects custom threshold set via setThreshold()', () => {
      const { drives } = setup();

      drives.setThreshold(0.4);
      drives.signal({ drive: 'curiosity', activation: 0.45, reason: 'x' });

      expect(drives.getActiveDrives()).toHaveLength(1);
    });
  });

  describe('decayAll()', () => {
    it('reduces activation by the decay factor', () => {
      const { drives } = setup();

      drives.signal({ drive: 'curiosity', activation: 0.8, reason: 'high' });
      drives.decayAll(0.9); // 0.8 * 0.9 = 0.72

      expect(drives.getState('curiosity')?.activation).toBeCloseTo(0.72);
    });

    it('does not decay below 0.1 (floor)', () => {
      const { drives } = setup();

      // Set activation very low
      drives.signal({ drive: 'curiosity', activation: 0.05, reason: 'low' });
      drives.decayAll(0.5); // 0.05 * 0.5 = 0.025, but floor is 0.1

      expect(drives.getState('curiosity')?.activation).toBeCloseTo(0.1);
    });

    it('uses default factor of 0.995', () => {
      const { drives } = setup();

      drives.signal({ drive: 'curiosity', activation: 1.0, reason: 'max' });
      drives.decayAll(); // 1.0 * 0.995 = 0.995

      expect(drives.getState('curiosity')?.activation).toBeCloseTo(0.995);
    });

    it('decays all drives, not just one', () => {
      const { drives } = setup();

      drives.signal({ drive: 'curiosity', activation: 0.8, reason: 'a' });
      drives.signal({ drive: 'competence', activation: 0.7, reason: 'b' });
      drives.signal({ drive: 'social', activation: 0.6, reason: 'c' });
      drives.signal({ drive: 'autonomy', activation: 0.5, reason: 'd' });

      drives.decayAll(0.9);

      expect(drives.getState('curiosity')?.activation).toBeCloseTo(0.72);
      expect(drives.getState('competence')?.activation).toBeCloseTo(0.63);
      expect(drives.getState('social')?.activation).toBeCloseTo(0.54);
      expect(drives.getState('autonomy')?.activation).toBeCloseTo(0.45);
    });
  });

  describe('history bounding', () => {
    it('keeps history at max 100 entries', () => {
      const { drives } = setup();

      for (let i = 0; i < 110; i++) {
        drives.signal({ drive: 'curiosity', activation: i / 110, reason: `signal-${i}` });
      }

      const state = drives.getState('curiosity');
      expect(state?.history).toHaveLength(100);

      // Should keep the last 100 entries (indices 10-109)
      expect(state?.history[0].activation).toBeCloseTo(10 / 110);
      expect(state?.history[99].activation).toBeCloseTo(109 / 110);
    });
  });

  describe('setThreshold()', () => {
    it('clamps threshold to [0.0, 1.0]', () => {
      const { drives } = setup();

      drives.setThreshold(1.5);
      // All drives should be below threshold now
      drives.signal({ drive: 'curiosity', activation: 1.0, reason: 'max' });
      expect(drives.getActiveDrives()).toHaveLength(1); // threshold clamped to 1.0, activation is 1.0

      drives.setThreshold(-0.5);
      // Threshold is 0, all drives should be active
      expect(drives.getActiveDrives().length).toBeGreaterThan(0);
    });
  });
});
