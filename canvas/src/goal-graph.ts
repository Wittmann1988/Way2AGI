/**
 * Goal Graph View — Lit Web Component for visualizing the Goal DAG.
 */

import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

interface GoalNode {
  id: string;
  description: string;
  status: string;
  priority: number;
  source: string;
  childIds: string[];
}

@customElement('goal-graph-view')
export class GoalGraphView extends LitElement {
  @property({ type: Array }) goals: GoalNode[] = [];
  @state() private selectedGoal: GoalNode | null = null;

  static styles = css`
    :host {
      display: block;
      font-family: 'JetBrains Mono', monospace;
      background: #0d1117;
      color: #c9d1d9;
      padding: 16px;
      border-radius: 8px;
    }
    .goal-node {
      display: inline-block;
      padding: 8px 12px;
      margin: 4px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      border: 1px solid #30363d;
      transition: all 0.2s;
    }
    .goal-node:hover { border-color: #58a6ff; }
    .goal-node.active { background: #1a4d2e; border-color: #3fb950; }
    .goal-node.proposed { background: #2d1b00; border-color: #d29922; }
    .goal-node.completed { background: #161b22; color: #8b949e; }
    .goal-node.blocked { background: #3d1114; border-color: #f85149; }
    .source-badge {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 3px;
      margin-left: 6px;
    }
    .source-badge.drive { background: #7c3aed; }
    .source-badge.user { background: #2563eb; }
    .source-badge.reflection { background: #059669; }
    h3 { margin: 0 0 12px; color: #58a6ff; }
    .detail {
      margin-top: 12px;
      padding: 12px;
      background: #161b22;
      border-radius: 6px;
      font-size: 13px;
    }
  `;

  render() {
    const grouped = {
      active: this.goals.filter(g => g.status === 'active'),
      proposed: this.goals.filter(g => g.status === 'proposed'),
      completed: this.goals.filter(g => g.status === 'completed'),
      blocked: this.goals.filter(g => g.status === 'blocked'),
    };

    return html`
      <h3>Goal Graph (${this.goals.length} total)</h3>
      ${Object.entries(grouped).map(([status, goals]) => goals.length ? html`
        <div>
          <small style="color:#8b949e">${status.toUpperCase()} (${goals.length})</small>
          <div>
            ${goals.map(g => html`
              <span
                class="goal-node ${g.status}"
                @click=${() => this.selectedGoal = g}
              >
                ${g.description.slice(0, 40)}
                <span class="source-badge ${g.source}">${g.source}</span>
              </span>
            `)}
          </div>
        </div>
      ` : '')}
      ${this.selectedGoal ? html`
        <div class="detail">
          <strong>${this.selectedGoal.description}</strong><br>
          Status: ${this.selectedGoal.status} | Priority: ${this.selectedGoal.priority}/10<br>
          Source: ${this.selectedGoal.source} | Children: ${this.selectedGoal.childIds.length}
        </div>
      ` : ''}
    `;
  }
}
