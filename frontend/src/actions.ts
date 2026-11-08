export type ChatAction = {
  id: string;
  label: string;
  run: () => void;
};

export function createActions(root: HTMLElement, actions: ChatAction[]): void {
  root.classList.add("actions");
  root.replaceChildren(
    ...actions.map((action) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.action = action.id;
      button.textContent = action.label;
      button.addEventListener("click", () => {
        action.run();
      });
      return button;
    }),
  );
}
