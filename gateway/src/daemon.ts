#!/usr/bin/env node
/**
 * Way2AGI Gateway Daemon.
 *
 * Central process that runs the cognitive core and exposes:
 * - WebSocket API (port 18789) for clients/channels/devices
 * - HTTP health endpoint
 * - Manages lifecycle of all cognitive modules
 */

import { WebSocketServer, WebSocket } from 'ws';
import { createServer } from 'http';
import { createCognitiveCore } from '@way2agi/cognition';

const PORT = parseInt(process.env.WAY2AGI_PORT ?? '18789', 10);
const VERSION = '0.1.0';

interface ClientConnection {
  ws: WebSocket;
  id: string;
  role: 'client' | 'channel' | 'device';
  name: string;
  connectedAt: number;
}

async function main() {
  console.log(`[Way2AGI] Starting Cognitive Gateway Daemon v${VERSION}`);
  console.log(`[Way2AGI] Port: ${PORT}`);

  // Bootstrap cognitive core
  const { workspace, goals, drives, controller, initiative } = createCognitiveCore();

  const clients = new Map<string, ClientConnection>();

  // HTTP server for health checks
  const httpServer = createServer((req, res) => {
    if (req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'ok',
        version: VERSION,
        uptime: process.uptime(),
        cognitive: {
          workspaceItems: workspace.size,
          activeGoals: goals.getActive().length,
          totalGoals: goals.totalCount,
          drives: drives.getAllStates().map(d => ({
            type: d.type,
            activation: d.activation.toFixed(2),
          })),
          controllerPhase: controller.getPhase(),
          cycleCount: controller.getState().cycleCount,
        },
        connections: clients.size,
      }));
      return;
    }
    res.writeHead(404);
    res.end();
  });

  // WebSocket server (max 1MB messages to prevent DoS)
  const wss = new WebSocketServer({ server: httpServer, maxPayload: 1024 * 1024 });

  wss.on('connection', (ws, req) => {
    const id = crypto.randomUUID();
    const client: ClientConnection = {
      ws,
      id,
      role: 'client',
      name: 'unknown',
      connectedAt: Date.now(),
    };
    clients.set(id, client);

    console.log(`[Gateway] Client connected: ${id}`);

    ws.on('message', (data) => {
      try {
        const msg = JSON.parse(data.toString());
        handleMessage(client, msg);
      } catch {
        ws.send(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });

    ws.on('close', () => {
      clients.delete(id);
      console.log(`[Gateway] Client disconnected: ${id}`);
    });

    // Send welcome
    ws.send(JSON.stringify({
      type: 'welcome',
      id,
      version: VERSION,
      cognitive: {
        activeGoals: goals.getActive().length,
        drives: drives.getAllStates().map(d => d.type),
      },
    }));
  });

  function handleMessage(client: ClientConnection, msg: Record<string, unknown>) {
    const type = msg.type as string;

    switch (type) {
      case 'identify': {
        const allowedRoles: ClientConnection['role'][] = ['client', 'channel', 'device'];
        const requestedRole = msg.role as string;
        client.role = allowedRoles.includes(requestedRole as any) ? requestedRole as ClientConnection['role'] : 'client';
        // Sanitize name: alphanumeric, dash, underscore only (max 32 chars)
        const rawName = (msg.name as string) ?? 'unknown';
        client.name = rawName.replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 32) || 'unknown';
        break;
      }

      case 'perception':
        // External input enters the workspace
        workspace.post({
          type: 'perception',
          priority: (msg.priority as number) ?? 5,
          payload: msg.payload,
          sourceModule: `channel:${client.name}`,
          ttl: 30_000,
        });
        break;

      case 'goal:create':
        goals.create({
          type: (msg.goalType as any) ?? 'task',
          description: (msg.description as string) ?? '',
          priority: (msg.priority as number) ?? 5,
          source: 'user',
          context: (msg.context as Record<string, unknown>) ?? {},
        });
        break;

      case 'status':
        client.ws.send(JSON.stringify({
          type: 'status',
          cognitive: controller.getState(),
          goals: goals.getTopPriority(10),
          drives: drives.getAllStates(),
        }));
        break;
    }
  }

  // Broadcast workspace events to all connected clients
  workspace.observe().subscribe(event => {
    const msg = JSON.stringify({ type: 'cognitive:event', event });
    for (const client of clients.values()) {
      if (client.ws.readyState === WebSocket.OPEN) {
        try {
          client.ws.send(msg);
        } catch {
          // Client may have disconnected between readyState check and send
        }
      }
    }
  });

  // Set up Layer 2/3 reflection handler
  controller.onReflection(async (req) => {
    console.log(`[Reflection] Layer ${req.layer} triggered: ${req.trigger} (urgency: ${req.urgency})`);
    // TODO: Call LLM via orchestrator for actual reflection
    // For now, log it
    workspace.post({
      type: 'reflection',
      priority: req.urgency,
      payload: req,
      sourceModule: `reflection:layer${req.layer}`,
      ttl: 60_000,
    });
  });

  // Start cognitive systems
  controller.start();
  initiative.start();

  httpServer.listen(PORT, () => {
    console.log(`[Way2AGI] Gateway running on port ${PORT}`);
    console.log(`[Way2AGI] Health: http://localhost:${PORT}/health`);
    console.log(`[Way2AGI] WebSocket: ws://localhost:${PORT}`);
    console.log(`[Way2AGI] Cognitive core active — MetaController + Initiative Engine running`);
  });

  // Graceful shutdown
  const shutdown = () => {
    console.log('\n[Way2AGI] Shutting down...');
    controller.stop();
    initiative.stop();
    wss.close();
    httpServer.close();
    process.exit(0);
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch(err => {
  console.error('[Way2AGI] Fatal error:', err);
  process.exit(1);
});
