import { describe, it, expect, vi } from 'vitest';
import { GlobalWorkspace } from '../workspace.js';
import type { CognitiveEvent } from '../types.js';

describe('GlobalWorkspace', () => {
  function makeWorkspace() {
    return new GlobalWorkspace();
  }

  describe('post()', () => {
    it('adds an item and returns an id', () => {
      const ws = makeWorkspace();
      const id = ws.post({
        type: 'perception',
        priority: 5,
        payload: { data: 'hello' },
        sourceModule: 'test',
        ttl: 10_000,
      });

      expect(id).toBeTypeOf('string');
      expect(id.length).toBeGreaterThan(0);
      expect(ws.size).toBe(1);
    });

    it('increments size for each posted item', () => {
      const ws = makeWorkspace();
      ws.post({ type: 'perception', priority: 1, payload: null, sourceModule: 'a', ttl: 30_000 });
      ws.post({ type: 'goal_update', priority: 2, payload: null, sourceModule: 'b', ttl: 30_000 });
      ws.post({ type: 'drive_signal', priority: 3, payload: null, sourceModule: 'c', ttl: 30_000 });
      expect(ws.size).toBe(3);
    });

    it('assigns default TTL when omitted', () => {
      const ws = makeWorkspace();
      ws.post({ type: 'perception', priority: 5, payload: {}, sourceModule: 'test' } as any);
      const items = ws.getItemsByType('perception');
      expect(items).toHaveLength(1);
      expect(items[0].ttl).toBe(30_000);
    });
  });

  describe('selectFocus()', () => {
    it('returns null on empty workspace', () => {
      const ws = makeWorkspace();
      expect(ws.selectFocus()).toBeNull();
    });

    it('selects the item with highest priority', () => {
      const ws = makeWorkspace();
      ws.post({ type: 'perception', priority: 3, payload: 'low', sourceModule: 'a', ttl: 30_000 });
      ws.post({ type: 'goal_update', priority: 9, payload: 'high', sourceModule: 'b', ttl: 30_000 });
      ws.post({ type: 'drive_signal', priority: 5, payload: 'mid', sourceModule: 'c', ttl: 30_000 });

      const focus = ws.selectFocus();
      expect(focus).not.toBeNull();
      expect(focus!.priority).toBe(9);
      expect(focus!.payload).toBe('high');
    });

    it('updates getCurrentFocus() after selection', () => {
      const ws = makeWorkspace();
      expect(ws.getCurrentFocus()).toBeNull();

      ws.post({ type: 'perception', priority: 7, payload: 'x', sourceModule: 'a', ttl: 30_000 });
      ws.selectFocus();

      const focus = ws.getCurrentFocus();
      expect(focus).not.toBeNull();
      expect(focus!.priority).toBe(7);
    });
  });

  describe('TTL eviction', () => {
    it('evicts expired items on post()', () => {
      const ws = makeWorkspace();
      const now = Date.now();

      // Post an item with a very short TTL
      ws.post({ type: 'perception', priority: 1, payload: 'old', sourceModule: 'a', ttl: 1 });

      // Wait just enough for TTL to expire, then post another
      vi.spyOn(Date, 'now').mockReturnValue(now + 50);
      ws.post({ type: 'perception', priority: 2, payload: 'new', sourceModule: 'b', ttl: 30_000 });

      // The expired item should have been evicted
      expect(ws.size).toBe(1);
      const items = ws.getItemsByType('perception');
      expect(items).toHaveLength(1);
      expect(items[0].payload).toBe('new');

      vi.restoreAllMocks();
    });

    it('evicts expired items on selectFocus()', () => {
      const ws = makeWorkspace();
      const now = Date.now();

      ws.post({ type: 'perception', priority: 5, payload: 'ephemeral', sourceModule: 'a', ttl: 1 });
      expect(ws.size).toBe(1);

      vi.spyOn(Date, 'now').mockReturnValue(now + 50);
      const focus = ws.selectFocus();
      expect(focus).toBeNull();
      expect(ws.size).toBe(0);

      vi.restoreAllMocks();
    });
  });

  describe('MAX_ITEMS bounding', () => {
    it('evicts lowest-priority item when exceeding 256 items', () => {
      const ws = makeWorkspace();

      // Fill workspace to MAX_ITEMS (256)
      for (let i = 0; i < 256; i++) {
        ws.post({
          type: 'perception',
          priority: i + 1, // priorities 1..256
          payload: `item-${i}`,
          sourceModule: 'test',
          ttl: 60_000,
        });
      }
      expect(ws.size).toBe(256);

      // Post one more with high priority
      ws.post({
        type: 'perception',
        priority: 999,
        payload: 'overflow',
        sourceModule: 'test',
        ttl: 60_000,
      });

      // Should still be at MAX_ITEMS (256), lowest priority evicted
      expect(ws.size).toBe(256);

      // The item with priority 1 (lowest) should be gone
      const items = ws.getItemsByType('perception');
      const priorities = items.map(i => i.priority);
      expect(priorities).not.toContain(1);
      expect(priorities).toContain(999);
    });
  });

  describe('observe()', () => {
    it('emits workspace:posted events when items are posted', () => {
      const ws = makeWorkspace();
      const events: CognitiveEvent[] = [];

      ws.observe().subscribe(e => events.push(e));

      ws.post({ type: 'perception', priority: 5, payload: 'test', sourceModule: 'mod', ttl: 10_000 });

      expect(events).toHaveLength(1);
      expect(events[0].type).toBe('workspace:posted');
      expect(events[0].source).toBe('mod');
    });

    it('emits workspace:focus events when selectFocus is called', () => {
      const ws = makeWorkspace();
      const events: CognitiveEvent[] = [];

      ws.observe().subscribe(e => events.push(e));

      ws.post({ type: 'perception', priority: 5, payload: 'x', sourceModule: 'a', ttl: 30_000 });
      ws.selectFocus();

      // 1 posted event + 1 focus event
      expect(events).toHaveLength(2);
      expect(events[1].type).toBe('workspace:focus');
      expect(events[1].source).toBe('workspace');
    });

    it('on() filters to specific event types', () => {
      const ws = makeWorkspace();
      const focusEvents: CognitiveEvent[] = [];

      ws.on('workspace:focus').subscribe(e => focusEvents.push(e));

      ws.post({ type: 'perception', priority: 5, payload: 'x', sourceModule: 'a', ttl: 30_000 });
      ws.selectFocus();

      // Should only have the focus event, not the posted event
      expect(focusEvents).toHaveLength(1);
      expect(focusEvents[0].type).toBe('workspace:focus');
    });
  });

  describe('remove()', () => {
    it('removes an item by id', () => {
      const ws = makeWorkspace();
      const id = ws.post({ type: 'perception', priority: 5, payload: 'x', sourceModule: 'a', ttl: 30_000 });
      expect(ws.size).toBe(1);

      ws.remove(id);
      expect(ws.size).toBe(0);
    });
  });

  describe('getItemsByType()', () => {
    it('returns only items matching the given type', () => {
      const ws = makeWorkspace();
      ws.post({ type: 'perception', priority: 1, payload: 'a', sourceModule: 'a', ttl: 30_000 });
      ws.post({ type: 'goal_update', priority: 2, payload: 'b', sourceModule: 'b', ttl: 30_000 });
      ws.post({ type: 'perception', priority: 3, payload: 'c', sourceModule: 'c', ttl: 30_000 });

      const perceptions = ws.getItemsByType('perception');
      expect(perceptions).toHaveLength(2);
      expect(perceptions.every(i => i.type === 'perception')).toBe(true);
    });
  });
});
