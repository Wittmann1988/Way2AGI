/**
 * Onboarding Wizard — Interactive guided setup.
 *
 * Unlike OpenClaw's simple `onboard` command, Way2AGI's wizard
 * teaches the user about the agent's cognitive architecture.
 * "Meet your agent's mind" — transparent AI interaction.
 */

import { createInterface } from 'readline';
import { existsSync, writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { homedir } from 'os';

interface OnboardingConfig {
  userName: string;
  language: string;
  telegramToken?: string;
  matrixHomeserver?: string;
  matrixToken?: string;
  discordToken?: string;
  memoryServerUrl: string;
  llmProvider: string;
  llmApiKey?: string;
  driveWeights: {
    curiosity: number;
    competence: number;
    social: number;
    autonomy: number;
  };
  autonomyLevel: 'cautious' | 'balanced' | 'autonomous';
}

const DEFAULT_CONFIG: OnboardingConfig = {
  userName: 'User',
  language: 'de',
  memoryServerUrl: 'http://localhost:5000',
  llmProvider: 'anthropic',
  driveWeights: {
    curiosity: 0.7,
    competence: 0.5,
    social: 0.4,
    autonomy: 0.3,
  },
  autonomyLevel: 'balanced',
};

export class OnboardingWizard {
  private rl: ReturnType<typeof createInterface>;
  private config: OnboardingConfig;
  private configPath: string;

  constructor() {
    this.rl = createInterface({ input: process.stdin, output: process.stdout });
    this.config = { ...DEFAULT_CONFIG };
    this.configPath = join(homedir(), '.way2agi', 'config.json');
  }

  async run(): Promise<OnboardingConfig> {
    this.printBanner();

    // Step 1: Introduction
    await this.step1_introduction();

    // Step 2: Identity
    await this.step2_identity();

    // Step 3: Messaging Channels
    await this.step3_channels();

    // Step 4: AI Provider
    await this.step4_provider();

    // Step 5: Meet the Mind
    await this.step5_meetTheMind();

    // Step 6: Autonomy Level
    await this.step6_autonomy();

    // Save config
    this.saveConfig();

    this.print('\n=== Setup Complete! ===');
    this.print(`Config saved to: ${this.configPath}`);
    this.print('\nStart with: way2agi start');
    this.print('Health:     curl http://localhost:18789/health\n');

    this.rl.close();
    return this.config;
  }

  private printBanner(): void {
    this.print(`
 ╦ ╦┌─┐┬ ┬┌─┐╔═╗╔═╗╦
 ║║║├─┤└┬┘┌─┘╠═╣║ ╦║
 ╚╩╝┴ ┴ ┴ └─┘╩ ╩╚═╝╩
 Cognitive AI Agent — Setup Wizard
`);
  }

  private async step1_introduction(): Promise<void> {
    this.print('=== Step 1/6: Welcome ===\n');
    this.print('Way2AGI is not a chatbot. It\'s a cognitive agent with:');
    this.print('  - A Global Workspace (like a conscious attention system)');
    this.print('  - Intrinsic Drives (curiosity, competence, social)');
    this.print('  - Hierarchical Goals (it plans and acts autonomously)');
    this.print('  - 4-Tier Memory (buffer, episodic, semantic, procedural)');
    this.print('\nLet\'s configure your agent.\n');
  }

  private async step2_identity(): Promise<void> {
    this.print('=== Step 2/6: Identity ===\n');
    this.config.userName = await this.ask('Your name', 'Erik');
    this.config.language = await this.ask('Language (de/en)', 'de');
  }

  private async step3_channels(): Promise<void> {
    this.print('\n=== Step 3/6: Messaging Channels ===');
    this.print('Connect your agent to messaging platforms.\n');

    const telegram = await this.ask('Telegram Bot Token (from @BotFather, or skip)', '');
    if (telegram) this.config.telegramToken = telegram;

    const discord = await this.ask('Discord Bot Token (or skip)', '');
    if (discord) this.config.discordToken = discord;
  }

  private async step4_provider(): Promise<void> {
    this.print('\n=== Step 4/6: AI Provider ===');
    this.print('Available: anthropic, openai, google, openrouter, ollama, groq\n');

    this.config.llmProvider = await this.ask('Primary LLM provider', 'anthropic');
    const key = await this.ask('API Key (or use existing env var)', '');
    if (key) this.config.llmApiKey = key;
  }

  private async step5_meetTheMind(): Promise<void> {
    this.print('\n=== Step 5/6: Meet Your Agent\'s Mind ===\n');
    this.print('Your agent has 4 intrinsic drives. Adjust their strength:');
    this.print('  0.0 = inactive, 0.5 = moderate, 1.0 = maximum\n');

    const c = await this.ask('Curiosity (explores unknown topics)', '0.7');
    this.config.driveWeights.curiosity = parseFloat(c) || 0.7;

    const comp = await this.ask('Competence (improves weak skills)', '0.5');
    this.config.driveWeights.competence = parseFloat(comp) || 0.5;

    const s = await this.ask('Social (anticipates your needs)', '0.4');
    this.config.driveWeights.social = parseFloat(s) || 0.4;

    const a = await this.ask('Autonomy (acts independently)', '0.3');
    this.config.driveWeights.autonomy = parseFloat(a) || 0.3;
  }

  private async step6_autonomy(): Promise<void> {
    this.print('\n=== Step 6/6: Autonomy Level ===');
    this.print('How independently should your agent act?\n');
    this.print('  cautious  — Always asks before acting');
    this.print('  balanced  — Acts on routine tasks, asks for important ones');
    this.print('  autonomous — Acts freely, reports results\n');

    const level = await this.ask('Level', 'balanced');
    if (['cautious', 'balanced', 'autonomous'].includes(level)) {
      this.config.autonomyLevel = level as OnboardingConfig['autonomyLevel'];
    }
  }

  private saveConfig(): void {
    const dir = dirname(this.configPath);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(this.configPath, JSON.stringify(this.config, null, 2));
  }

  private ask(question: string, defaultVal: string): Promise<string> {
    return new Promise((resolve) => {
      const prompt = defaultVal ? `${question} [${defaultVal}]: ` : `${question}: `;
      this.rl.question(prompt, (answer) => {
        resolve(answer.trim() || defaultVal);
      });
    });
  }

  private print(msg: string): void {
    console.log(msg);
  }
}
