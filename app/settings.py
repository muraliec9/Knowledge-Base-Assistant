from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_PATH = Path(os.getenv("KNOWLEDGE_PATH", ROOT / "knowledge"))
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", ROOT / "data" / "chroma"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
