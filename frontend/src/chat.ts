import { reply } from "./api.ts";
import type { Message, Role } from "./types.ts";

const STORAGE_KEY = "explorai.messages";

export type ChatListener = (messages: Message[]) => void;

function nextId(): string {
  return crypto.randomUUID();
}

function isRole(value: unknown): value is Role {
  return value === "user" || value === "assistant";
}

function isMessage(value: unknown): value is Message {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const message = value as Record<string, unknown>;
  return (
    typeof message.id === "string" &&
    isRole(message.role) &&
    typeof message.text === "string"
  );
}

function loadMessages(): Message[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }

    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed) || !parsed.every(isMessage)) {
      return [];
    }

    return parsed;
  } catch {
    return [];
  }
}

function saveMessages(messages: Message[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
  } catch {
    // The list still updates on screen if the browser refuses storage.
  }
}

export function createChat(onChange: ChatListener) {
  const messages: Message[] = [];

  function notify(): void {
    saveMessages(messages);
    onChange([...messages]);
  }

  async function start(): Promise<void> {
    const stored = loadMessages();
    if (stored.length > 0) {
      messages.push(...stored);
      notify();
      return;
    }

    const text = await reply();
    messages.push({ id: nextId(), role: "assistant", text });
    notify();
  }

  async function send(text: string): Promise<void> {
    const trimmed = text.trim();
    if (!trimmed) {
      return;
    }

    messages.push({ id: nextId(), role: "user", text: trimmed });
    notify();

    const answer = await reply();
    messages.push({ id: nextId(), role: "assistant", text: answer });
    notify();
  }

  async function clear(): Promise<void> {
    messages.length = 0;
    const text = await reply();
    messages.push({ id: nextId(), role: "assistant", text });
    notify();
  }

  return { start, send, clear };
}
