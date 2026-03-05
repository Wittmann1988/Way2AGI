/**
 * Abstract Channel interface.
 *
 * All messaging channels (Telegram, Discord, Matrix, etc.) implement this.
 * Channels are treated as "sensory-motor" modules — they perceive input
 * and can output responses. The cognitive core decides WHAT to respond.
 */

export interface IncomingMessage {
  channelId: string;
  channelType: string;
  senderId: string;
  senderName: string;
  text: string;
  media?: {
    type: 'image' | 'audio' | 'video' | 'document' | 'voice';
    url?: string;
    data?: Buffer;
    mimeType?: string;
  };
  replyTo?: string;
  groupId?: string;
  timestamp: number;
  raw: unknown;
}

export interface OutgoingMessage {
  text: string;
  targetId: string;
  replyTo?: string;
  media?: {
    type: 'image' | 'audio' | 'document';
    data: Buffer;
    filename?: string;
    mimeType?: string;
  };
  markdown?: boolean;
}

export interface ChannelStatus {
  connected: boolean;
  channelType: string;
  activeChats: number;
  lastActivity: number;
}

export abstract class BaseChannel {
  abstract readonly type: string;
  abstract readonly name: string;

  abstract start(): Promise<void>;
  abstract stop(): Promise<void>;
  abstract send(msg: OutgoingMessage): Promise<void>;
  abstract getStatus(): ChannelStatus;

  protected onMessage?: (msg: IncomingMessage) => void;

  /** Register handler for incoming messages */
  onIncoming(handler: (msg: IncomingMessage) => void): void {
    this.onMessage = handler;
  }
}
