import "./style.css";
import { createActions } from "./actions.ts";
import { createChat } from "./chat.ts";
import { createDescription } from "./description.ts";
import { createView } from "./view.ts";

const root = document.querySelector<HTMLElement>("#app");
if (!root) {
  throw new Error("Missing #app");
}

root.innerHTML = `
  <div class="layout">
    <section class="description"></section>
    <main class="chat"></main>
    <aside class="actions"></aside>
  </div>
`;

const descriptionPanel = root.querySelector<HTMLElement>(".description");
const chatColumn = root.querySelector<HTMLElement>(".chat");
const actionPanel = root.querySelector<HTMLElement>(".actions");
if (!descriptionPanel || !chatColumn || !actionPanel) {
  throw new Error("Missing layout");
}

createDescription(descriptionPanel);

const view = createView(chatColumn);
const chat = createChat((messages) => {
  view.render(messages);
});

view.onSend((text) => {
  void chat.send(text);
});

createActions(actionPanel, [
  {
    id: "clear",
    label: "Clear chat history",
    run: () => {
      void chat.clear();
    },
  },
]);

void chat.start();
