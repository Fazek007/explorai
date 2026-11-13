import { renderMarkdown } from "./markdown.ts";
import type { Message } from "./types.ts";

export function createView(root: HTMLElement) {
  root.innerHTML = `
    <ol class="messages"></ol>
    <form class="composer">
      <input type="text" name="message" aria-label="Message" autocomplete="off" />
      <button type="submit">Send</button>
    </form>
  `;

  const list = root.querySelector<HTMLOListElement>(".messages");
  const form = root.querySelector<HTMLFormElement>(".composer");
  const input = form?.querySelector<HTMLInputElement>("input");

  if (!list || !form || !input) {
    throw new Error("Chat markup is missing");
  }

  let send: (text: string) => void = () => {};

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = input.value;
    input.value = "";
    send(text);
  });

  return {
    render(messages: Message[]): void {
      if (messages.length === 0) {
        const hint = document.createElement("p");
        hint.className = "empty-hint";
        hint.textContent =
          "Text Explorai to get to know all about this application.";
        list.replaceChildren(hint);
        return;
      }
      list.replaceChildren(
        ...messages.map((message) => {
          const item = document.createElement("li");
          item.className = `message message-${message.role}`;
          item.innerHTML = renderMarkdown(message.text);
          return item;
        }),
      );
      list.scrollTop = list.scrollHeight;
    },
    onSend(handler: (text: string) => void): void {
      send = handler;
    },
  };
}
