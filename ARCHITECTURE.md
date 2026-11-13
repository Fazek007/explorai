# Architecture

This is how Explorai works today.

## Page

The page is Vite and TypeScript, with three panels. An empty chat shows "Text Explorai to get to know all about this application." The open conversation id is kept in localStorage. The page sends each message to Django and renders the reply as Markdown.

## API

Django stores conversations and messages in SQLite. A new conversation has no messages. Clear screen starts another conversation and leaves the old one stored. Wipe chat history deletes every conversation.

## One turn

The user message is saved first. The turn then builds one block from that message plus the 2 messages before it. With fewer saved messages, the block uses what exists.

That window stays this short for now so the small local models, Llama 3.1 8B and `nomic-embed-text`, are not given a long chat history.

The same block is sent to the classifier. The classifier calls Llama 3.1 8B through Ollama with a JSON schema and temperature 0, so the reply is `{"route": "chat"}` or `{"route": "question"}`.

`chat` skips the notes. The answer prompt is short: respond briefly and naturally, and do not state facts about the notes.

`question`, bad JSON, or a failed classifier call searches the notes with that same block. The answer must come from the passages. If none are kept, the model is told the notes do not contain the answer.

The reply is saved on the conversation and returned to the page.

## Notes

Markdown files in `backend/notes/` are split into paragraphs, embedded with `nomic-embed-text`, and stored as `Chunk` rows. Search keeps the closest 3 chunks with a score of at least 0.5. Re-run `index_notes` after a note changes.

## Logs

Each turn writes one JSON file in `backend/logs/`. The file holds the question, the searched block, the classifier request and reply, the chunk scores, the answer request, and the message Ollama returned. Only the 10 newest files are kept. The folder is gitignored.
