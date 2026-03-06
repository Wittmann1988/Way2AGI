/**
 * Telegram Channel — Priority 1.
 *
 * Uses grammY for bot API interaction.
 * Supports: text, voice notes, images, documents, code blocks, inline keyboards.
 */

import { Bot, Context, InputFile } from 'grammy';
import { BaseChannel } from './base.js';
import type { IncomingMessage, OutgoingMessage, ChannelStatus } from './base.js';

export class TelegramChannel extends BaseChannel {
  readonly type = 'telegram';
  readonly name: string;

  private bot: Bot;
  private activeChats = new Set<string>();
  private lastActivity = 0;
  private running = false;

  constructor(token: string, name = 'Way2AGI Telegram') {
    super();
    this.name = name;
    this.bot = new Bot(token);
    this.setupHandlers();
  }

  private setupHandlers(): void {
    // Text messages
    this.bot.on('message:text', (ctx) => {
      this.handleIncoming(ctx, ctx.message.text);
    });

    // Voice messages
    this.bot.on('message:voice', async (ctx) => {
      const file = await ctx.getFile();
      this.handleIncoming(ctx, '[voice]', {
        type: 'voice',
        url: `https://api.telegram.org/file/bot${this.bot.token}/${file.file_path}`,
        mimeType: 'audio/ogg',
      });
    });

    // Photos
    this.bot.on('message:photo', async (ctx) => {
      const photo = ctx.message.photo;
      const largest = photo[photo.length - 1];
      const file = await ctx.api.getFile(largest.file_id);
      this.handleIncoming(ctx, ctx.message.caption ?? '[photo]', {
        type: 'image',
        url: `https://api.telegram.org/file/bot${this.bot.token}/${file.file_path}`,
        mimeType: 'image/jpeg',
      });
    });

    // Documents
    this.bot.on('message:document', async (ctx) => {
      const doc = ctx.message.document;
      const file = await ctx.getFile();
      this.handleIncoming(ctx, ctx.message.caption ?? `[document: ${doc.file_name}]`, {
        type: 'document',
        url: `https://api.telegram.org/file/bot${this.bot.token}/${file.file_path}`,
        mimeType: doc.mime_type ?? 'application/octet-stream',
      });
    });
  }

  private handleIncoming(
    ctx: Context,
    text: string,
    media?: IncomingMessage['media'],
  ): void {
    if (!ctx.from || !ctx.chat) return;

    const chatId = ctx.chat.id.toString();
    this.activeChats.add(chatId);
    this.lastActivity = Date.now();

    const msg: IncomingMessage = {
      channelId: chatId,
      channelType: 'telegram',
      senderId: ctx.from.id.toString(),
      senderName: ctx.from.first_name + (ctx.from.last_name ? ` ${ctx.from.last_name}` : ''),
      text,
      media,
      replyTo: ctx.message?.reply_to_message?.message_id?.toString(),
      groupId: ctx.chat.type !== 'private' ? chatId : undefined,
      timestamp: (ctx.message?.date ?? Math.floor(Date.now() / 1000)) * 1000,
      raw: ctx,
    };

    this.onMessage?.(msg);
  }

  async start(): Promise<void> {
    if (this.running) return;
    this.running = true;
    console.log(`[Telegram] Starting bot: ${this.name}`);
    this.bot.start({
      onStart: () => console.log(`[Telegram] Bot running`),
    });
  }

  async stop(): Promise<void> {
    if (!this.running) return;
    this.running = false;
    await this.bot.stop();
    console.log(`[Telegram] Bot stopped`);
  }

  async send(msg: OutgoingMessage): Promise<void> {
    const chatId = msg.targetId;

    if (msg.media) {
      switch (msg.media.type) {
        case 'image':
          await this.bot.api.sendPhoto(chatId, new InputFile(msg.media.data), {
            caption: msg.text,
            parse_mode: msg.markdown ? 'MarkdownV2' : undefined,
          });
          return;
        case 'audio':
          await this.bot.api.sendAudio(chatId, new InputFile(msg.media.data, msg.media.filename), {
            caption: msg.text,
            parse_mode: msg.markdown ? 'MarkdownV2' : undefined,
          });
          return;
        case 'document':
          await this.bot.api.sendDocument(chatId, new InputFile(msg.media.data, msg.media.filename), {
            caption: msg.text,
            parse_mode: msg.markdown ? 'MarkdownV2' : undefined,
          });
          return;
      }
    }

    await this.bot.api.sendMessage(chatId, msg.text, {
      parse_mode: msg.markdown ? 'MarkdownV2' : 'HTML',
      reply_parameters: msg.replyTo ? { message_id: parseInt(msg.replyTo) } : undefined,
    });
  }

  getStatus(): ChannelStatus {
    return {
      connected: this.running,
      channelType: 'telegram',
      activeChats: this.activeChats.size,
      lastActivity: this.lastActivity,
    };
  }
}
