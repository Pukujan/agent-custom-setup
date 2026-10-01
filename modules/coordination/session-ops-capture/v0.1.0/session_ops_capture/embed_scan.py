"""Offline embed similarity: numpy exact scan over float32 BLOBs.

MUST NOT be imported by JEV gate hot-path modules (ambiguity / research / pin).
Used only by Pass2 / batch jobs.
"""
from __future__ import annotations

import struct
from typing import Iterable, List, Sequence, Tuple

def pack_f32(vec: Sequence[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *[float(x) for x in vec])

def unpack_f32(blob: bytes) -> List[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))

def exact_scan(
    query: Sequence[float],
    corpus: Iterable[Tuple[str, bytes]],
    *,
    top_k: int = 5,
) -> List[Tuple[str, float]]:
    """Cosine exact scan. Requires numpy. Offline/batch only."""
    try:
        import numpy as np
    except ImportError as e:
        raise RuntimeError("numpy required for offline embed_scan only") from e
    q = np.asarray(list(query), dtype=np.float32)
    qn = np.linalg.norm(q) or 1.0
    q = q / qn
    scored: List[Tuple[str, float]] = []
    for eid, blob in corpus:
        v = np.frombuffer(blob, dtype=np.float32)
        if v.size != q.size:
            continue
        vn = np.linalg.norm(v) or 1.0
        scored.append((eid, float(np.dot(q, v / vn))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]

