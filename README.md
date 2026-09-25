# Atlas Knowledge Bot

A small, demonstrable RAG application for FAQs, policies, guides, and product documentation. It retrieves relevant passages from a persistent Chroma vector database, generates grounded answers, and always displays the supporting source passages.

## What is included

- ChromaDB persistence at `data/chroma`
- Local deterministic embeddings plus keyword-aware reranking: runs offline without downloading a model
- Markdown/text ingestion on startup and through the UI
- Retrieval with source titles, excerpts, and similarity indicators
- Optional OpenAI answer synthesis; a safe extractive answer is used when no key is configured
- Conversation history passed to the optional LLM synthesis call

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env  # optional: add OPENAI_API_KEY for synthesis
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. The first start indexes the curated files in `knowledge/`.

### Enable natural-language synthesis

The bot always retrieves and cites its evidence. Without an LLM key, it returns the most relevant source passage verbatim to remain grounded. To receive a concise, natural-language answer with inline citations, add an approved OpenAI-compatible key to `.env` and restart:

```text
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
```

## Add knowledge

Use the upload control for `.md` and `.txt` files, or copy files into `knowledge/` and restart the app. Each document is split into overlapping passages before indexing. For a demo, keep the content set small and curated (around 5–10 documents).

## Production considerations

Replace `HashEmbeddingFunction` with an approved semantic embedding service; configure `OPENAI_API_KEY` for natural-language synthesis; enforce identity-aware retrieval and document permissions; audit uploads; add evaluation questions for groundedness and citation accuracy; and use a managed vector database with backups and retention controls.
