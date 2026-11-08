import type { Message, Role } from "./types.ts";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export type Conversation = {
  id: string;
  messages: Message[];
};

export type Reply = {
  text: string;
  model: string;
  sources: unknown[];
};

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

function isConversation(value: unknown): value is Conversation {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const conversation = value as Record<string, unknown>;
  return (
    typeof conversation.id === "string" &&
    Array.isArray(conversation.messages) &&
    conversation.messages.every(isMessage)
  );
}

function isReply(value: unknown): value is Reply {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const reply = value as Record<string, unknown>;
  return (
    typeof reply.text === "string" &&
    typeof reply.model === "string" &&
    Array.isArray(reply.sources)
  );
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError(0, "The model is unavailable.");
  }
  if (!response.ok) {
    throw new ApiError(response.status, "The model is unavailable.");
  }
  return response;
}

export async function createConversation(): Promise<Conversation> {
  const response = await request("/api/conversations/", { method: "POST" });
  const body: unknown = await response.json();
  if (!isConversation(body)) {
    throw new ApiError(response.status, "The model is unavailable.");
  }
  return body;
}

export async function getConversation(id: string): Promise<Conversation> {
  const response = await request(`/api/conversations/${id}/`);
  const body: unknown = await response.json();
  if (!isConversation(body)) {
    throw new ApiError(response.status, "The model is unavailable.");
  }
  return body;
}

export async function sendMessage(id: string, text: string): Promise<Reply> {
  const response = await request(`/api/conversations/${id}/messages/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const body: unknown = await response.json();
  if (!isReply(body)) {
    throw new ApiError(response.status, "The model is unavailable.");
  }
  return body;
}

export async function wipeHistory(): Promise<void> {
  await request("/api/conversations/", { method: "DELETE" });
}
