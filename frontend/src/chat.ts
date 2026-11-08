import {
  ApiError,
  createConversation,
  getConversation,
  sendMessage,
  wipeHistory,
  type Conversation,
} from "./api.ts";
import type { Message } from "./types.ts";

const STORAGE_KEY = "explorai.conversationId";
const UNAVAILABLE = "The model is unavailable.";

export type ChatListener = (messages: Message[]) => void;

export function createChat(onChange: ChatListener) {
  const messages: Message[] = [];
  let conversationId = "";

  function notify(): void {
    onChange([...messages]);
  }

  function replace(next: Message[]): void {
    messages.splice(0, messages.length, ...next);
    notify();
  }

  function showUnavailable(): void {
    replace([{ id: crypto.randomUUID(), role: "assistant", text: UNAVAILABLE }]);
  }

  function remember(conversation: Conversation): void {
    conversationId = conversation.id;
    localStorage.setItem(STORAGE_KEY, conversation.id);
    replace(conversation.messages);
  }

  async function start(): Promise<void> {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        remember(await getConversation(stored));
        return;
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) {
          showUnavailable();
          return;
        }
      }
    }

    try {
      remember(await createConversation());
    } catch {
      showUnavailable();
    }
  }

  async function send(text: string): Promise<void> {
    const trimmed = text.trim();
    if (!trimmed || !conversationId) {
      return;
    }

    messages.push({ id: crypto.randomUUID(), role: "user", text: trimmed });
    notify();

    try {
      const reply = await sendMessage(conversationId, trimmed);
      messages.push({
        id: crypto.randomUUID(),
        role: "assistant",
        text: reply.text,
      });
      notify();
    } catch {
      messages.push({
        id: crypto.randomUUID(),
        role: "assistant",
        text: UNAVAILABLE,
      });
      notify();
    }
  }

  async function clearScreen(): Promise<void> {
    try {
      remember(await createConversation());
    } catch {
      showUnavailable();
    }
  }

  async function wipe(): Promise<void> {
    try {
      await wipeHistory();
      remember(await createConversation());
    } catch {
      showUnavailable();
    }
  }

  return { start, send, clearScreen, wipe };
}
