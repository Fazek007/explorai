# Explorai

Explorai is a local chat application. A TypeScript page talks to a Django API, conversations are stored in SQLite, and replies come from a model running through Ollama. The app decides whether a message is small talk or a question. Questions are answered from a small set of notes.

The aim is to ground answers in a much larger set of documents, with the usual retrieval practices, such as chunking, embeddings, and reranking, and to keep that retrieval accurate as the set grows.

It is in active development. [ARCHITECTURE.md](ARCHITECTURE.md) describes how a message is handled.
