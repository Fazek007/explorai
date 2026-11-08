import DOMPurify from "dompurify";
import { marked } from "marked";

const ALLOWED_URI = /^(?:https?:|mailto:)/i;

export function renderMarkdown(text: string): string {
  const html = marked.parse(text, { async: false, gfm: true });
  return DOMPurify.sanitize(html, {
    FORBID_TAGS: ["img", "style", "form", "input", "iframe", "object", "embed"],
    ALLOWED_URI_REGEXP: ALLOWED_URI,
  });
}
