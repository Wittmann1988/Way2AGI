/**
 * Structured JSON logger for Way2AGI TypeScript modules.
 * Outputs one JSON object per line (JSONL) to stdout.
 * Respects LOG_LEVEL env var (default: "info").
 */

const LEVELS = { debug: 0, info: 1, warn: 2, error: 3 } as const;
type Level = keyof typeof LEVELS;

const currentLevel: Level = (
  (process.env.LOG_LEVEL?.toLowerCase() ?? 'info') as Level
) in LEVELS
  ? (process.env.LOG_LEVEL!.toLowerCase() as Level)
  : 'info';

interface Logger {
  debug(message: string, meta?: Record<string, unknown>): void;
  info(message: string, meta?: Record<string, unknown>): void;
  warn(message: string, meta?: Record<string, unknown>): void;
  error(message: string, meta?: Record<string, unknown>): void;
  metrics(name: string, value: number, meta?: Record<string, unknown>): void;
}

function emit(level: Level, module: string, message: string, meta?: Record<string, unknown>): void {
  if (LEVELS[level] < LEVELS[currentLevel]) return;
  const entry: Record<string, unknown> = {
    timestamp: new Date().toISOString(),
    level,
    module,
    message,
  };
  if (meta && Object.keys(meta).length > 0) {
    entry.metadata = meta;
  }
  process.stdout.write(JSON.stringify(entry) + '\n');
}

export function createLogger(module: string): Logger {
  return {
    debug: (msg, meta?) => emit('debug', module, msg, meta),
    info: (msg, meta?) => emit('info', module, msg, meta),
    warn: (msg, meta?) => emit('warn', module, msg, meta),
    error: (msg, meta?) => emit('error', module, msg, meta),
    metrics: (name, value, meta?) =>
      emit('info', module, `metric:${name}`, { ...meta, metric_name: name, metric_value: value }),
  };
}
