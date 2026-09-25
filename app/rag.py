from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import chromadb

from app.settings import CHROMA_PATH, CHUNK_OVERLAP, CHUNK_SIZE, KNOWLEDGE_PATH


@dataclass
class Source:
    title: str
    document: str
    excerpt: str
    score: float


class HashEmbeddingFunction:
    """Small offline embedding function for a predictable, network-free demo.

    It uses signed feature hashing and cosine-normalised vectors.  Swap this for
    a hosted embedding model in production without changing the collection API.
    """

    dimension = 768

    def __call__(self, input: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in input:
            vector = [0.0] * self.dimension
            for token in re.findall(r"[a-z0-9][a-z0-9_-]+", text.lower()):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "big") % self.dimension
                vector[bucket] += 1 if digest[4] % 2 else -1
            length = sum(value * value for value in vector) ** 0.5 or 1.0
            embeddings.append([value / length for value in vector])
        return embeddings


def chunk_text(text: str) -> Iterable[str]:
    clean = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Preserve FAQ/policy sections as retrieval units. A question and its answer
    # should not be separated merely because a character limit was reached.
    sections = [part.strip() for part in re.split(r"(?=^#{1,3}\s+)", clean, flags=re.MULTILINE) if part.strip()]
    for section in sections or [clean]:
        start = 0
        while start < len(section):
            end = min(start + CHUNK_SIZE, len(section))
            if end < len(section):
                boundary = max(section.rfind(". ", start, end), section.rfind("\n", start, end))
                if boundary > start + CHUNK_SIZE // 2:
                    end = boundary + 1
            chunk = section[start:end].strip()
            if chunk:
                yield chunk
            if end == len(section):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)


class KnowledgeBase:
    def __init__(self) -> None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.collection = self.client.get_or_create_collection(
            name="knowledge_base", embedding_function=HashEmbeddingFunction()
        )

    def ingest_file(self, path: Path) -> int:
        text = path.read_text(encoding="utf-8", errors="ignore")
        chunks = list(chunk_text(text))
        if not chunks:
            return 0
        document = path.name
        ids = [f"{document}:{index}" for index in range(len(chunks))]
        self.collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=[{"document": document, "title": path.stem.replace("_", " ").title()}] * len(chunks),
        )
        return len(chunks)

    def ingest_directory(self) -> int:
        count = 0
        for path in KNOWLEDGE_PATH.glob("**/*"):
            if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
                count += self.ingest_file(path)
        return count

    def rebuild(self) -> int:
        """Recreate the index from the checked-in and uploaded knowledge files."""
        self.client.delete_collection("knowledge_base")
        self.collection = self.client.get_or_create_collection(
            name="knowledge_base", embedding_function=HashEmbeddingFunction()
        )
        return self.ingest_directory()

    def retrieve(self, question: str, limit: int = 4) -> list[Source]:
        if not self.collection.count():
            return []
        count = self.collection.count()
        vector_result = self.collection.query(query_texts=[question], n_results=count)
        vector_scores = {
            identifier: max(0.0, 1 - distance / 2)
            for identifier, distance in zip(vector_result["ids"][0], vector_result["distances"][0])
        }
        all_items = self.collection.get(include=["documents", "metadatas"])
        query_terms = set(re.findall(r"[a-z0-9][a-z0-9_-]+", question.lower()))
        documents = all_items["documents"]
        term_sets = [set(re.findall(r"[a-z0-9][a-z0-9_-]+", text.lower())) for text in documents]
        frequency = Counter(term for terms in term_sets for term in terms)

        ranked = []
        for identifier, text, item, terms in zip(all_items["ids"], documents, all_items["metadatas"], term_sets):
            lexical_score = sum(math.log((count + 1) / (frequency[term] + 1)) + 1 for term in query_terms & terms)
            # Exact question terms dominate when present; vector similarity still
            # provides a useful secondary signal for paraphrased questions.
            score = lexical_score + vector_scores.get(identifier, 0.0) * 0.35
            ranked.append((score, text, item))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [
            Source(
                title=item.get("title", item["document"]),
                document=item["document"],
                excerpt=text[:520].replace("\n", " ").strip(),
                score=round(min(1.0, score / 5), 2),
            )
            for score, text, item in ranked[:limit]
        ]

    def status(self) -> dict[str, int]:
        return {"chunks": self.collection.count()}
