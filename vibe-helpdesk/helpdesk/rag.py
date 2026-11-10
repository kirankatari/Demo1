"""Local TF-IDF retrieval over the fictional IT documents. No vector database."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MIN_SCORE = 0.08


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    doc_id: str
    title: str
    heading: str
    text: str
    score: float

    def as_dict(self) -> dict:
        excerpt = plain_text(self.text, limit=700)
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "heading": self.heading,
            "excerpt": excerpt,
            "score": round(self.score, 4),
        }


def plain_text(text: str, limit: int = 700) -> str:
    """Drop markdown heading marks so quoted guidance reads as prose."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if stripped:
            lines.append(stripped)
    excerpt = " ".join(lines)
    if len(excerpt) > limit:
        excerpt = excerpt[:limit].rstrip() + "..."
    return excerpt


def _title_of(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback.replace("-", " ").title()


def load_chunks(directory: Path) -> list[Hit]:
    chunks: list[Hit] = []
    for path in sorted(directory.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        title = _title_of(raw, path.stem)
        sections = re.split(r"\n(?=## )", raw)
        for index, section in enumerate(sections):
            body = section.strip()
            if len(body) < 40:
                continue
            heading = body.splitlines()[0].lstrip("#").strip()
            chunks.append(
                Hit(
                    chunk_id=f"{path.stem}#{index}",
                    doc_id=path.stem,
                    title=title,
                    heading=heading,
                    text=body,
                    score=0.0,
                )
            )
    if not chunks:
        raise FileNotFoundError(f"No markdown documents in {directory}")
    return chunks


class KnowledgeBase:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.chunks = load_chunks(self.directory)
        self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self._matrix = self._vectorizer.fit_transform(chunk.text for chunk in self.chunks)

    def search(self, query: str, k: int = 4) -> list[Hit]:
        cleaned = " ".join(query.split())
        if len(cleaned) < 2:
            return []
        k = max(1, min(int(k), 6))
        scores = cosine_similarity(
            self._vectorizer.transform([cleaned]), self._matrix
        ).ravel()
        order = scores.argsort()[::-1]
        hits: list[Hit] = []
        for index in order[:k]:
            score = float(scores[index])
            if score < MIN_SCORE:
                continue
            chunk = self.chunks[index]
            hits.append(
                Hit(
                    chunk.chunk_id,
                    chunk.doc_id,
                    chunk.title,
                    chunk.heading,
                    chunk.text,
                    score,
                )
            )
        if not hits:
            return []
        # Drop weak neighbors so a 0.09 hit is not cited next to a 0.40 hit.
        floor = max(MIN_SCORE, hits[0].score * 0.25)
        return [hit for hit in hits if hit.score >= floor]
