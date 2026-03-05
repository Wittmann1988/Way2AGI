/**
 * Drive Monitor — Lit Web Component for visualizing Drive states.
 */

import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface DriveDisplay {
  type: string;
  activation: number;
  lastSignal: number;
}

@customElement('drive-monitor')
export class DriveMonitor extends LitElement {
  @property({ type: Array }) drives: DriveDisplay[] = [];

  static styles = css`
    :host {
      display: block;
      font-family: 'JetBrains Mono', monospace;
      background: #0d1117;
      color: #c9d1d9;
      padding: 16px;
      border-radius: 8px;
    }
    .drive-row {
      display: flex;
      align-items: center;
      margin: 8px 0;
      gap: 12px;
    }
    .drive-label {
      width: 100px;
      font-size: 13px;
      text-transform: capitalize;
    }
    .drive-bar-bg {
      flex: 1;
      height: 24px;
      background: #21262d;
      border-radius: 4px;
      overflow: hidden;
      position: relative;
    }
    .drive-bar {
      height: 100%;
      border-radius: 4px;
      transition: width 0.5s ease, background 0.5s ease;
    }
    .drive-pct {
      width: 45px;
      text-align: right;
      font-size: 12px;
      color: #8b949e;
    }
    h3 { margin: 0 0 12px; color: #a371f7; }
  `;

  private getColor(activation: number): string {
    if (activation > 0.8) return '#f85149';
    if (activation > 0.6) return '#d29922';
    if (activation > 0.3) return '#3fb950';
    return '#388bfd';
  }

  render() {
    return html`
      <h3>Intrinsic Drives</h3>
      ${this.drives.map(d => {
        const pct = Math.round(d.activation * 100);
        return html`
          <div class="drive-row">
            <span class="drive-label">${d.type}</span>
            <div class="drive-bar-bg">
              <div
                class="drive-bar"
                style="width:${pct}%;background:${this.getColor(d.activation)}"
              ></div>
            </div>
            <span class="drive-pct">${pct}%</span>
          </div>
        `;
      })}
    `;
  }
}
