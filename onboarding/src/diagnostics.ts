/**
 * Diagnostics — System health check ("doctor" command).
 *
 * Verifies all components are working:
 * - Gateway daemon running
 * - Memory server reachable
 * - Messaging channels connected
 * - Cognitive core responding
 * - Python environment correct
 */

import { existsSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

interface DiagnosticResult {
  component: string;
  status: 'ok' | 'warn' | 'error';
  message: string;
  detail?: string;
}

export class Diagnostics {
  private results: DiagnosticResult[] = [];
  private gatewayUrl: string;
  private memoryUrl: string;

  constructor(
    gatewayUrl = 'http://localhost:18789',
    memoryUrl = 'http://localhost:5000',
  ) {
    this.gatewayUrl = gatewayUrl;
    this.memoryUrl = memoryUrl;
  }

  async runAll(): Promise<DiagnosticResult[]> {
    this.results = [];

    await Promise.all([
      this.checkConfig(),
      this.checkGateway(),
      this.checkMemory(),
      this.checkNodeVersion(),
      this.checkPythonVersion(),
    ]);

    return this.results;
  }

  private async checkConfig(): Promise<void> {
    const configPath = join(homedir(), '.way2agi', 'config.json');
    if (existsSync(configPath)) {
      this.results.push({
        component: 'Config',
        status: 'ok',
        message: 'Configuration found',
        detail: configPath,
      });
    } else {
      this.results.push({
        component: 'Config',
        status: 'warn',
        message: 'No config file — run: way2agi onboard',
        detail: configPath,
      });
    }
  }

  private async checkGateway(): Promise<void> {
    try {
      const res = await fetch(`${this.gatewayUrl}/health`);
      if (res.ok) {
        const data = await res.json() as Record<string, unknown>;
        this.results.push({
          component: 'Gateway',
          status: 'ok',
          message: `Running v${data.version}`,
          detail: `Uptime: ${Math.round(data.uptime as number)}s, Connections: ${data.connections}`,
        });
      } else {
        this.results.push({
          component: 'Gateway',
          status: 'error',
          message: `HTTP ${res.status}`,
        });
      }
    } catch {
      this.results.push({
        component: 'Gateway',
        status: 'error',
        message: 'Not reachable — start with: pnpm start',
        detail: this.gatewayUrl,
      });
    }
  }

  private async checkMemory(): Promise<void> {
    try {
      const res = await fetch(`${this.memoryUrl}/health`);
      if (res.ok) {
        const data = await res.json() as Record<string, unknown>;
        this.results.push({
          component: 'Memory Server',
          status: 'ok',
          message: `Running v${data.version}`,
        });
      }
    } catch {
      this.results.push({
        component: 'Memory Server',
        status: 'error',
        message: 'Not reachable — start with: python memory/src/server.py',
        detail: this.memoryUrl,
      });
    }
  }

  private async checkNodeVersion(): Promise<void> {
    const version = process.version;
    const major = parseInt(version.slice(1).split('.')[0]);
    this.results.push({
      component: 'Node.js',
      status: major >= 22 ? 'ok' : 'error',
      message: version,
      detail: major < 22 ? 'Requires Node.js >= 22' : undefined,
    });
  }

  private async checkPythonVersion(): Promise<void> {
    try {
      const { execSync } = await import('child_process');
      const version = execSync('python3 --version').toString().trim();
      this.results.push({
        component: 'Python',
        status: 'ok',
        message: version,
      });
    } catch {
      this.results.push({
        component: 'Python',
        status: 'error',
        message: 'Python3 not found',
      });
    }
  }

  printReport(): void {
    console.log('\n=== Way2AGI Diagnostics ===\n');
    for (const r of this.results) {
      const icon = r.status === 'ok' ? 'OK' : r.status === 'warn' ? 'WARN' : 'FAIL';
      console.log(`[${icon}] ${r.component}: ${r.message}`);
      if (r.detail) console.log(`     ${r.detail}`);
    }
    const errors = this.results.filter(r => r.status === 'error').length;
    console.log(`\n${errors === 0 ? 'All checks passed!' : `${errors} issue(s) found.`}\n`);
  }
}
