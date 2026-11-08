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
      list.replaceChildren(
        ...messages.map((message) => {
          const item = document.createElement("li");
          item.className = `message message-${message.role}`;
          item.textContent = message.text;
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
