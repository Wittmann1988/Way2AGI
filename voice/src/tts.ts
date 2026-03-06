/**
 * Text-to-Speech Engine.
 *
 * Uses Microsoft Edge TTS (free, high quality, many voices/languages).
 * Prosody parameters are derived from the cognitive state.
 */

import { spawn } from 'child_process';

export interface TTSOptions {
  voice?: string;
  rate?: string;   // e.g. "+20%", "-10%"
  pitch?: string;  // e.g. "+5Hz", "-3Hz"
  volume?: string; // e.g. "+10%"
}

export type CognitiveEmotion = 'neutral' | 'curious' | 'confident' | 'uncertain' | 'excited';

const VOICE_DEFAULTS: Record<string, TTSOptions> = {
  neutral: { rate: '+0%', pitch: '+0Hz', volume: '+0%' },
  curious: { rate: '+15%', pitch: '+3Hz', volume: '+5%' },
  confident: { rate: '-5%', pitch: '-2Hz', volume: '+10%' },
  uncertain: { rate: '-10%', pitch: '+1Hz', volume: '-5%' },
  excited: { rate: '+20%', pitch: '+5Hz', volume: '+15%' },
};

export class TTSEngine {
  private defaultVoice: string;

  constructor(defaultVoice = 'de-DE-ConradNeural') {
    this.defaultVoice = defaultVoice;
  }

  /**
   * Synthesize speech with prosody derived from cognitive emotion.
   * Returns audio buffer (MP3).
   */
  async synthesize(
    text: string,
    emotion: CognitiveEmotion = 'neutral',
    options?: TTSOptions,
  ): Promise<Buffer> {
    const prosody = { ...VOICE_DEFAULTS[emotion], ...options };
    const voice = options?.voice ?? this.defaultVoice;

    // Build SSML for prosody control
    const ssml = `
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="de-DE">
  <voice name="${voice}">
    <prosody rate="${prosody.rate}" pitch="${prosody.pitch}" volume="${prosody.volume}">
      ${escapeXml(text)}
    </prosody>
  </voice>
</speak>`.trim();

    return this.callEdgeTTS(ssml, voice);
  }

  /** List available voices */
  async listVoices(): Promise<string[]> {
    return new Promise((resolve, reject) => {
      const proc = spawn('edge-tts', ['--list-voices']);
      let output = '';
      proc.stdout.on('data', (d) => { output += d.toString(); });
      proc.on('close', (code) => {
        if (code !== 0) return reject(new Error(`edge-tts exited with ${code}`));
        const voices = output.split('\n')
          .filter(l => l.startsWith('Name:'))
          .map(l => l.replace('Name: ', '').trim());
        resolve(voices);
      });
    });
  }

  private callEdgeTTS(ssml: string, voice: string): Promise<Buffer> {
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = [];
      const proc = spawn('edge-tts', [
        '--voice', voice,
        '--ssml', ssml,
        '--write-media', '/dev/stdout',
      ]);
      proc.stdout.on('data', (chunk: Buffer) => chunks.push(chunk));
      proc.on('close', (code) => {
        if (code !== 0) return reject(new Error(`edge-tts failed: ${code}`));
        resolve(Buffer.concat(chunks));
      });
      proc.on('error', reject);
    });
  }
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
