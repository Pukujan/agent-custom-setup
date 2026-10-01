"""Pass2 embeddings: searchable text vectors in SQLite (local / stub backends)."""

from __future__ import annotations

import hashlib
import math
import os
import struct
from abc import ABC, abstractmethod
from typing import Iterable, List, Optional, Sequence, Tuple

# Fixed dim for hash backend (compact, deterministic)
HASH_DIM = 64


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def pack_vector(vec: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *[float(x) for x in vec])


def unpack_vector(blob: bytes) -> List[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


class EmbedBackend(ABC):
    name: str
    dim: int

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        raise NotImplementedError


class HashingEmbedBackend(EmbedBackend):
    """
    Deterministic local bag-of-features embedder (no network, no secrets).
    Same text → identical vector (cosine == 1). Good default for CI + offline.
    """

    name = "hashing-v1"
    dim = HASH_DIM

    def embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        if not text:
            return vec
        # Normalize whitespace
        tokens = text.lower().split()
        if not tokens:
            tokens = [text.lower()]
        for tok in tokens:
            h = hashlib.sha256(tok.encode("utf-8")).digest()
            # two signed features per token
            idx = int.from_bytes(h[:2], "little") % self.dim
            sign = 1.0 if (h[2] & 1) == 0 else -1.0
            vec[idx] += sign
            idx2 = int.from_bytes(h[3:5], "little") % self.dim
            sign2 = 1.0 if (h[5] & 1) == 0 else -1.0
            vec[idx2] += 0.5 * sign2
        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class SentenceTransformersBackend(EmbedBackend):
    """Optional real local model (nomic / MiniLM) when sentence-transformers is installed."""

    name = "sentence-transformers"
    dim = 384  # overridden after load

    def __init__(self, model_name: Optional[str] = None):
        from sentence_transformers import SentenceTransformer  # type: ignore

        model_name = model_name or os.environ.get(
            "ACS_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self._model = SentenceTransformer(model_name)
        # Probe dim
        probe = self._model.encode(["dim-probe"], normalize_embeddings=True)
        self.dim = int(len(probe[0]))
        self.name = f"sentence-transformers:{model_name}"

    def embed(self, text: str) -> List[float]:
        arr = self._model.encode([text or ""], normalize_embeddings=True)
        return [float(x) for x in arr[0]]


def get_embed_backend(*, force_hash: bool = False) -> EmbedBackend:
    """
    Prefer sentence-transformers when ACS_EMBED_BACKEND=st|sentence-transformers
    and the package imports; otherwise hashing stub.
    Tests should pass force_hash=True or unset env.
    """
    if force_hash:
        return HashingEmbedBackend()
    choice = (os.environ.get("ACS_EMBED_BACKEND") or "auto").lower()
    if choice in ("hash", "hashing", "stub"):
        return HashingEmbedBackend()
    if choice in ("st", "sentence-transformers", "nomic", "auto"):
        if choice != "auto" or os.environ.get("ACS_EMBED_TRY_ST") == "1":
            try:
                return SentenceTransformersBackend(
                    os.environ.get("ACS_EMBED_MODEL")
                )
            except Exception:
                if choice != "auto":
                    # Explicit ST requested but unavailable → still fail closed to hash
                    return HashingEmbedBackend()
        # auto default: hashing (CI-safe, no heavy download)
        return HashingEmbedBackend()
    return HashingEmbedBackend()


def embed_texts(
    texts: Iterable[str], backend: Optional[EmbedBackend] = None
) -> Tuple[EmbedBackend, List[List[float]]]:
    be = backend or get_embed_backend()
    return be, [be.embed(t) for t in texts]
