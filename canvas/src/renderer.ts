/**
 * Canvas Renderer — Live HTML/CSS/JS execution environment.
 *
 * Creates sandboxed HTML canvases that the agent can generate
 * and update in real-time. Supports:
 * - Mermaid diagrams (goal graphs, architecture)
 * - D3.js visualizations (memory landscape, drive states)
 * - Interactive forms (user input collection)
 * - Code execution playgrounds
 */

export interface CanvasConfig {
  width: number;
  height: number;
  theme: 'dark' | 'light';
}

export interface CanvasArtifact {
  id: string;
  type: 'html' | 'mermaid' | 'svg' | 'markdown';
  content: string;
  title: string;
  createdAt: number;
  updatedAt: number;
}

export class CanvasRenderer {
  private artifacts: Map<string, CanvasArtifact> = new Map();
  private config: CanvasConfig;

  constructor(config?: Partial<CanvasConfig>) {
    this.config = {
      width: 800,
      height: 600,
      theme: 'dark',
      ...config,
    };
  }

  /** Create or update a canvas artifact */
  render(artifact: Omit<CanvasArtifact, 'createdAt' | 'updatedAt'>): CanvasArtifact {
    const existing = this.artifacts.get(artifact.id);
    const full: CanvasArtifact = {
      ...artifact,
      createdAt: existing?.createdAt ?? Date.now(),
      updatedAt: Date.now(),
    };
    this.artifacts.set(artifact.id, full);
    return full;
  }

  /** Generate a goal graph as Mermaid diagram */
  renderGoalGraph(goals: Array<{
    id: string;
    description: string;
    status: string;
    parentId?: string;
  }>): CanvasArtifact {
    const lines = ['graph TD'];
    for (const goal of goals) {
      const style = goal.status === 'active' ? ':::active'
        : goal.status === 'completed' ? ':::done' : '';
      lines.push(`  ${goal.id}["${goal.description}"]${style}`);
      if (goal.parentId) {
        lines.push(`  ${goal.parentId} --> ${goal.id}`);
      }
    }
    lines.push('  classDef active fill:#4CAF50,color:#fff');
    lines.push('  classDef done fill:#9E9E9E,color:#fff');

    return this.render({
      id: 'goal-graph',
      type: 'mermaid',
      content: lines.join('\n'),
      title: 'Goal Graph',
    });
  }

  /** Generate a drive state visualization */
  renderDriveStates(drives: Array<{
    type: string;
    activation: number;
  }>): CanvasArtifact {
    const bars = drives.map(d => {
      const pct = Math.round(d.activation * 100);
      const color = pct > 60 ? '#FF5722' : pct > 30 ? '#FFC107' : '#4CAF50';
      return `<div style="margin:8px 0">
        <span style="display:inline-block;width:100px;color:#ccc">${d.type}</span>
        <div style="display:inline-block;width:200px;height:20px;background:#333;border-radius:4px;overflow:hidden">
          <div style="width:${pct}%;height:100%;background:${color};transition:width 0.3s"></div>
        </div>
        <span style="color:#888;margin-left:8px">${pct}%</span>
      </div>`;
    }).join('\n');

    return this.render({
      id: 'drive-monitor',
      type: 'html',
      content: `<div style="font-family:monospace;padding:16px;background:#1a1a1a;border-radius:8px">
        <h3 style="color:#fff;margin:0 0 12px">Drive States</h3>
        ${bars}
      </div>`,
      title: 'Drive Monitor',
    });
  }

  getArtifact(id: string): CanvasArtifact | undefined {
    return this.artifacts.get(id);
  }

  getAllArtifacts(): CanvasArtifact[] {
    return [...this.artifacts.values()];
  }

  remove(id: string): void {
    this.artifacts.delete(id);
  }
}
