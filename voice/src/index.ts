/**
 * @way2agi/voice — Voice I/O Module
 *
 * Prosody-aware: the agent's internal state influences speech tone.
 * - Curious → rising intonation, faster pace
 * - Confident → steady, measured delivery
 * - Uncertain → slower, hedging markers
 */

export { TTSEngine, type TTSOptions } from './tts.js';
export { STTEngine, type STTResult } from './stt.js';
