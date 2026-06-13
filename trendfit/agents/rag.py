"""Pipeline RAG (Retrieval-Augmented Generation) para Buffett Jr.

Carrega PDFs/TXTs de docs/books/, chunka em blocos de ~500 tokens,
indexa via TF-IDF com similaridade cosseno. Cache em JSON+npy evita reindexação.

LINHA VERMELHA: RAG é contexto puro, nunca sinal de trading.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_MAX_QUERY_LEN = 1000
_PDF_MAGIC = b"%PDF"


@dataclass
class RagResult:
    """Resultado de busca RAG."""
    chunk: str
    source: str
    score: float


class RagIndex:
    """Indexa PDFs/TXTs de docs/books/ e retorna chunks relevantes por query."""

    _CHUNK_TARGET_TOKENS = 500
    _CACHE_META_FILENAME = "rag_index_meta.json"
    _CACHE_VECTORS_FILENAME = "rag_index_vectors.npy"

    def __init__(self, books_dir: str | Path = "docs/books", cache_dir: str | Path = "db"):
        self.books_dir = Path(books_dir).resolve()
        self.cache_dir = Path(cache_dir).resolve()
        self._meta_path = self.cache_dir / self._CACHE_META_FILENAME
        self._vectors_path = self.cache_dir / self._CACHE_VECTORS_FILENAME

        self._chunks: list[tuple[str, str]] = []  # [(text, source), ...]
        self._tfidf_vectors: np.ndarray | None = None
        self._vocab: dict[str, int] | None = None

        self._try_load_cache()
        if not self._chunks:
            self.load_books()

    def load_books(self) -> None:
        """Carrega e chunka todos os arquivos em docs/books/."""
        if not self.books_dir.exists():
            logger.info("Pasta books nao existe, criando...")
            self.books_dir.mkdir(parents=True, exist_ok=True)
            return

        # .md e .txt são tratados como texto puro (a biblioteca destilada do brain é .md)
        txt_files = sorted(self.books_dir.glob("*.txt")) + sorted(self.books_dir.glob("*.md"))
        pdf_files = sorted(self.books_dir.glob("*.pdf"))

        if not txt_files and not pdf_files:
            logger.info("Nenhum arquivo em books_dir")
            return

        for txt_file in txt_files:
            self._load_txt(txt_file)

        for pdf_file in pdf_files:
            self._load_pdf(pdf_file)

        if self._chunks:
            logger.info("Carregados %d chunks de %d textos e %d PDFs", len(self._chunks), len(txt_files), len(pdf_files))
            self._build_index()
            self._save_cache()
        else:
            logger.info("Nenhum chunk carregado")

    def _load_txt(self, filepath: Path) -> None:
        """Carrega e chunka um arquivo .txt."""
        try:
            text = filepath.read_text(encoding="utf-8")
            chunks = self._chunk_text(text)
            source_name = filepath.name
            for chunk in chunks:
                self._chunks.append((chunk, source_name))
            logger.debug("Carregado %d chunks de %s", len(chunks), source_name)
        except Exception as exc:
            logger.error("Erro ao carregar TXT %s: %s", filepath.name, exc)

    def _load_pdf(self, filepath: Path) -> None:
        """Carrega e chunka um arquivo .pdf com validacao de magic bytes."""
        try:
            with open(filepath, "rb") as f:
                magic = f.read(4)
            if magic != _PDF_MAGIC:
                logger.warning("Arquivo %s nao e PDF valido (magic bytes incorretos), pulando", filepath.name)
                return
        except OSError as exc:
            logger.error("Erro ao ler %s: %s", filepath.name, exc)
            return

        try:
            import PyPDF2
        except ImportError:
            logger.warning("PyPDF2 nao disponivel, pulando %s", filepath.name)
            return

        try:
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            chunks = self._chunk_text(text)
            source_name = filepath.name
            for chunk in chunks:
                self._chunks.append((chunk, source_name))
            logger.debug("Carregado %d chunks de %s", len(chunks), source_name)
        except Exception as exc:
            logger.error("Erro ao carregar PDF %s: %s", filepath.name, exc)

    def _chunk_text(self, text: str) -> list[str]:
        """Chunka texto em blocos de ~500 tokens (paragrafos)."""
        text = re.sub(r"\n\n+", "\n\n", text.strip())
        paragraphs = text.split("\n\n")

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            if not para.strip():
                continue

            tokens = self._estimate_tokens(para)

            if tokens > self._CHUNK_TARGET_TOKENS:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0

                sentences = re.split(r"[.!?]+", para)
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    sent_tokens = self._estimate_tokens(sent)
                    if current_tokens + sent_tokens > self._CHUNK_TARGET_TOKENS and current_chunk:
                        chunks.append("\n\n".join(current_chunk))
                        current_chunk = [sent]
                        current_tokens = sent_tokens
                    else:
                        current_chunk.append(sent)
                        current_tokens += sent_tokens
            elif current_tokens + tokens > self._CHUNK_TARGET_TOKENS:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_tokens = tokens
            else:
                current_chunk.append(para)
                current_tokens += tokens

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return [c for c in chunks if c.strip()]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text.split())

    def _tokenize(self, text: str) -> dict[str, int]:
        words = re.findall(r"\b\w+\b", text.lower())
        freq: dict[str, int] = {}
        for word in words:
            freq[word] = freq.get(word, 0) + 1
        return freq

    def _build_index(self) -> None:
        if not self._chunks:
            return

        self._vocab = {}
        doc_freqs: dict[str, int] = {}
        doc_term_freqs: list[dict[str, int]] = []

        for chunk, _ in self._chunks:
            term_freq = self._tokenize(chunk)
            doc_term_freqs.append(term_freq)
            for term in term_freq:
                doc_freqs[term] = doc_freqs.get(term, 0) + 1

        for i, term in enumerate(sorted(doc_freqs.keys())):
            self._vocab[term] = i

        n_docs = len(self._chunks)
        tfidf_vectors: list[list[float]] = []

        for term_freq in doc_term_freqs:
            vec = [0.0] * len(self._vocab)
            for term, freq in term_freq.items():
                if term in self._vocab:
                    idx = self._vocab[term]
                    idf = np.log(1 + n_docs / doc_freqs[term])
                    vec[idx] = freq * idf

            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = [v / norm for v in vec]
            tfidf_vectors.append(vec)

        self._tfidf_vectors = np.array(tfidf_vectors, dtype=np.float32)
        logger.debug("Indice TF-IDF construido: %d docs, %d termos", len(self._chunks), len(self._vocab))

    def search(self, query: str, top_k: int = 3) -> list[RagResult]:
        """Busca chunks relevantes.

        Args:
            query: Pergunta/consulta (max 1000 chars)
            top_k: Numero de top resultados

        Returns:
            Lista de RagResult ordenada por relevancia (decrescente)

        Raises:
            ValueError: Se query ultrapassar limite de tamanho
        """
        if len(query) > _MAX_QUERY_LEN:
            raise ValueError(f"query muito longa ({len(query)} chars, max {_MAX_QUERY_LEN})")

        if not self._chunks or self._tfidf_vectors is None or self._vocab is None:
            logger.info("Indice vazio ou nao construido")
            return []

        query_freq = self._tokenize(query)
        query_vec = [0.0] * len(self._vocab)
        n_docs = len(self._chunks)

        for term, freq in query_freq.items():
            if term in self._vocab:
                idx = self._vocab[term]
                doc_count = sum(1 for chunk, _ in self._chunks if term in self._tokenize(chunk))
                idf = np.log(1 + n_docs / doc_count)
                query_vec[idx] = freq * idf

        query_norm = np.linalg.norm(query_vec)
        if query_norm > 0:
            query_vec = [v / query_norm for v in query_vec]
        query_arr = np.array(query_vec, dtype=np.float32)

        scores = self._tfidf_vectors @ query_arr
        top_indices = np.argsort(scores)[::-1][:top_k]

        results: list[RagResult] = []
        for idx in top_indices:
            if scores[idx] > 0:
                chunk, source = self._chunks[idx]
                results.append(RagResult(chunk=chunk, source=source, score=float(scores[idx])))

        return results

    def _save_cache(self) -> None:
        """Salva indice em cache (JSON + npy). Nao usa pickle."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            meta = {
                "chunks": self._chunks,
                "vocab": self._vocab,
            }
            self._meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            if self._tfidf_vectors is not None:
                np.save(str(self._vectors_path), self._tfidf_vectors)
            logger.debug("Cache salvo em %s", self.cache_dir)
        except Exception as exc:
            logger.warning("Erro ao salvar cache: %s", exc)

    def _try_load_cache(self) -> bool:
        """Carrega indice do cache (JSON + npy). Nao usa pickle."""
        if not self._meta_path.exists() or not self._vectors_path.exists():
            return False

        try:
            meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
            self._chunks = [tuple(item) for item in meta.get("chunks", [])]  # type: ignore[misc]
            self._vocab = meta.get("vocab")
            self._tfidf_vectors = np.load(str(self._vectors_path))
            logger.debug("Cache carregado de %s", self.cache_dir)
            return bool(self._chunks)
        except Exception as exc:
            logger.warning("Erro ao carregar cache: %s", exc)
            return False
