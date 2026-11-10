"""Chunk local markdown and rank it with TF-IDF. FR-RAG-01, FR-RAG-02."""

from __future__ import annotations

import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from northstar.models import Passage

_DOC_ID = re.compile(r"^Document-ID:\s*(\S+)\s*$", re.MULTILINE)
_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def slug(text: str) -> str:
    lowered = text.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return cleaned[:40] or "section"


class KnowledgeBase:
    def __init__(self, knowledge_dir: Path):
        self.knowledge_dir = Path(knowledge_dir)
        if not self.knowledge_dir.is_dir():
            raise FileNotFoundError(f"Knowledge directory not found: {self.knowledge_dir}")
        self.passages = load_passages(self.knowledge_dir)
        if not self.passages:
            raise ValueError(f"No passages found in {self.knowledge_dir}")
        corpus = [f"{item.title}\n{item.heading}\n{item.text}" for item in self.passages]
        self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
        self._matrix = self._vectorizer.fit_transform(corpus)

    def document_ids(self) -> list[str]:
        return sorted({item.document_id for item in self.passages})

    def search(self, query: str, top_k: int = 3) -> list[Passage]:
        cleaned = (query or "").strip()
        if not cleaned:
            return []
        limit = max(1, min(int(top_k), 5))
        scores = cosine_similarity(self._vectorizer.transform([cleaned]), self._matrix).ravel()
        ranked = sorted(
            ((float(score), index) for index, score in enumerate(scores) if score > 0),
            key=lambda item: (-item[0], self.passages[item[1]].passage_id),
        )
        found: list[Passage] = []
        for score, index in ranked[:limit]:
            source = self.passages[index]
            found.append(
                Passage(
                    passage_id=source.passage_id,
                    document_id=source.document_id,
                    title=source.title,
                    heading=source.heading,
                    text=source.text,
                    score=round(score, 4),
                )
            )
        return found


def load_passages(knowledge_dir: Path) -> list[Passage]:
    passages: list[Passage] = []
    for path in sorted(knowledge_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        match = _DOC_ID.search(raw)
        document_id = match.group(1) if match else path.stem.upper()
        title = _title(raw) or document_id
        sections = _sections(raw)
        used: dict[str, int] = {}
        for heading, body in sections:
            base = slug(heading)
            used[base] = used.get(base, 0) + 1
            suffix = base if used[base] == 1 else f"{base}-{used[base]}"
            text = body.strip()
            if not text:
                continue
            passages.append(
                Passage(
                    passage_id=f"{document_id}#{suffix}",
                    document_id=document_id,
                    title=title,
                    heading=heading,
                    text=text,
                )
            )
    return passages


def _title(raw: str) -> str:
    for line in raw.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _sections(raw: str) -> list[tuple[str, str]]:
    matches = list(_HEADING.finditer(raw))
    if not matches:
        body = _DOC_ID.sub("", raw)
        body = re.sub(r"^#\s+.+", "", body, count=1, flags=re.MULTILINE).strip()
        return [("Overview", body)] if body else []
    sections = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        sections.append((match.group(1).strip(), raw[start:end]))
    return sections
