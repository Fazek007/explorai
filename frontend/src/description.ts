const PLACEHOLDER = `Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.`;

export function createDescription(root: HTMLElement, text: string = PLACEHOLDER): void {
  root.classList.add("description");
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  root.replaceChildren(paragraph);
}
