/**
 * Global Workspace — the cognitive blackboard.
 *
 * Inspired by Bernard Baars' Global Workspace Theory (GWT).
 * All cognitive modules post items here. The Attention Spotlight
 * selects the most relevant item and broadcasts it to all subscribers.
 */

import { Subject, Observable } from 'rxjs';
import { filter, map } from 'rxjs/operators';
import { v4 as uuid } from 'uuid';
import type { WorkspaceItem, CognitiveEvent } from './types.js';

const DEFAULT_TTL = 30_000; // 30s
const MAX_ITEMS = 256;

export class GlobalWorkspace {
  private items: Map<string, WorkspaceItem> = new Map();
  private bus = new Subject<CognitiveEvent>();
  private spotlight: WorkspaceItem | null = null;

  post(item: Omit<WorkspaceItem, 'id' | 'timestamp'>): string {
    const id = uuid();
    const entry: WorkspaceItem = {
      ...item,
      id,
      timestamp: Date.now(),
      ttl: item.ttl ?? DEFAULT_TTL,
    };

    this.items.set(id, entry);
    this.evictExpired();

    // Keep workspace bounded — O(n) scan instead of O(n log n) sort
    if (this.items.size > MAX_ITEMS) {
      let lowestKey: string | null = null;
      let lowestPriority = Infinity;
      for (const [key, it] of this.items) {
        if (it.priority < lowestPriority) {
          lowestPriority = it.priority;
          lowestKey = key;
        }
      }
      if (lowestKey) this.items.delete(lowestKey);
    }

    this.bus.next({
      type: 'workspace:posted',
      payload: entry,
      timestamp: entry.timestamp,
      source: item.sourceModule,
    });

    return id;
  }

  /** Attention spotlight selects highest-priority item */
  selectFocus(): WorkspaceItem | null {
    this.evictExpired();
    if (this.items.size === 0) return null;

    // O(n) scan for highest priority instead of O(n log n) sort
    let highest: WorkspaceItem | null = null;
    for (const item of this.items.values()) {
      if (!highest || item.priority > highest.priority) {
        highest = item;
      }
    }

    this.spotlight = highest;

    this.bus.next({
      type: 'workspace:focus',
      payload: this.spotlight,
      timestamp: Date.now(),
      source: 'workspace',
    });

    return this.spotlight;
  }

  getCurrentFocus(): WorkspaceItem | null {
    return this.spotlight;
  }

  getItemsByType(type: WorkspaceItem['type']): WorkspaceItem[] {
    return [...this.items.values()].filter(i => i.type === type);
  }

  remove(id: string): void {
    this.items.delete(id);
  }

  /** Observable stream of all workspace events */
  observe(): Observable<CognitiveEvent> {
    return this.bus.asObservable();
  }

  /** Filtered observable for specific event types */
  on(eventType: string): Observable<CognitiveEvent> {
    return this.bus.pipe(filter(e => e.type === eventType));
  }

  get size(): number {
    return this.items.size;
  }

  private evictExpired(): void {
    const now = Date.now();
    for (const [id, item] of this.items) {
      if (now - item.timestamp > item.ttl) {
        this.items.delete(id);
      }
    }
  }
}
