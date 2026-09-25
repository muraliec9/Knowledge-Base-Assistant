from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.rag import KnowledgeBase, Source
from app.settings import KNOWLEDGE_PATH, OPENAI_MODEL

app = FastAPI(title="Atlas Knowledge Bot", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
knowledge_base = KnowledgeBase()


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=8)


def sources_payload(sources: list[Source]) -> list[dict[str, str | float]]:
    return [source.__dict__ for source in sources]


def grounded_fallback(sources: list[Source]) -> str:
    if not sources:
        return "I couldn't find information about that in the current knowledge base. Try rephrasing your question or add a relevant document."
    # A single best passage avoids stitching unrelated excerpts into a response
    # when the optional LLM synthesis is not configured.
    evidence = sources[0].excerpt
    return f"Based on the knowledge base:\n\n{evidence}\n\nSee the cited sources below for the full details."


def synthesise(question: str, history: list[dict[str, str]], sources: list[Source]) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return grounded_fallback(sources)
    from openai import OpenAI

    context = "\n\n".join(f"[{index + 1}] {source.document}\n{source.excerpt}" for index, source in enumerate(sources))
    prompt = f"""Answer the user's question using only the supplied context. Be concise and factual.
If the context does not support an answer, say so. Cite factual statements as [1], [2], etc.

Question: {question}
Context:\n{context}"""
    response = OpenAI().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": "You are a careful, grounded knowledge-base assistant."}, *history, {"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return response.choices[0].message.content or grounded_fallback(sources)


@app.on_event("startup")
def seed_knowledge() -> None:
    knowledge_base.rebuild()


@app.get("/")
def home() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/api/status")
def status() -> dict[str, int | bool]:
    return {**knowledge_base.status(), "llm_enabled": bool(os.getenv("OPENAI_API_KEY"))}


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    sources = knowledge_base.retrieve(request.question)
    return {"answer": synthesise(request.question, request.history, sources), "sources": sources_payload(sources)}


@app.post("/api/documents")
async def upload_document(file: Annotated[UploadFile, File(...)]) -> dict[str, object]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".md", ".txt"}:
        raise HTTPException(400, "Only .md and .txt documents are supported in this demo.")
    KNOWLEDGE_PATH.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "document.txt").name
    target = KNOWLEDGE_PATH / safe_name
    target.write_bytes(await file.read())
    return {"document": safe_name, "chunks_indexed": knowledge_base.ingest_file(target)}
