Explorai is a local chat application for trying a model on your own machine.

The interface is a TypeScript page with three panels. The middle panel is the conversation. The backend is Django, and it stores each conversation in SQLite.

Replies come from Llama 3.1 8B through Ollama running on a separate PC. The browser talks only to the Django server, and Django sends the saved messages to the model.

A new conversation starts empty. Clear screen starts another conversation and leaves the old one stored. Wipe chat history deletes every stored conversation.
