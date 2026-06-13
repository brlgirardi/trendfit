"""Memória de teses do Buffett Jr — julgamento ADAPTÁVEL (pedido do Bruno).

"Nossa regra precisa ser adaptável, tudo pode mudar — precisamos retestar."
Aqui o assessor registra a leitura dele (tese + nível de alerta + evidências) e,
quando o cenário muda, REAVALIA: confirma ou refuta. É a parte do Brain que aprende.

Persistência: SQLite (db/buffett_brain.db, gitignored). Desacoplado do engine.
LINHA VERMELHA: tese é julgamento do assessor — nunca sinal mecânico nem ordem.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# status possíveis de uma tese ao longo do tempo
STATUS_OPEN = "aberta"
STATUS_CONFIRMED = "confirmada"
STATUS_REFUTED = "refutada"
_VALID_STATUS = {STATUS_OPEN, STATUS_CONFIRMED, STATUS_REFUTED}


@dataclass
class Thesis:
    """Uma tese registrada do assessor."""

    id: int
    asset: str
    thesis: str
    alert_level: int          # 1 (tranquilo) a 10 (perigo extremo)
    evidence: str
    status: str
    created_at: str
    reviewed_at: str | None = None
    review_note: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "asset": self.asset, "thesis": self.thesis,
            "alert_level": self.alert_level, "evidence": self.evidence,
            "status": self.status, "created_at": self.created_at,
            "reviewed_at": self.reviewed_at, "review_note": self.review_note,
        }


class ThesisStore:
    """Armazena e reavalia as teses do Buffett Jr (SQLite)."""

    def __init__(self, db_path: str | Path = "db/buffett_brain.db"):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS theses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    alert_level INTEGER NOT NULL,
                    evidence TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'aberta',
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    review_note TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.commit()

    def record(self, asset: str, thesis: str, alert_level: int,
               evidence: str = "") -> int:
        """Registra uma nova tese (status aberta). Retorna o id."""
        level = max(1, min(10, int(alert_level)))
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO theses (asset, thesis, alert_level, evidence, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (asset.upper(), thesis, level, evidence, STATUS_OPEN,
                 datetime.now().isoformat()),
            )
            conn.commit()
            return int(cur.lastrowid)

    def review(self, thesis_id: int, status: str, note: str = "") -> None:
        """Reavalia uma tese: confirma ou refuta (com nota do porquê)."""
        if status not in _VALID_STATUS:
            raise ValueError(f"status inválido: {status} (use {sorted(_VALID_STATUS)})")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE theses SET status = ?, reviewed_at = ?, review_note = ? WHERE id = ?",
                (status, datetime.now().isoformat(), note, thesis_id),
            )
            conn.commit()

    def open_theses(self, asset: str | None = None, limit: int = 5) -> list[Thesis]:
        """Teses ainda em aberto (para reavaliar). Filtra por ativo se informado."""
        q = "SELECT * FROM theses WHERE status = ?"
        params: list = [STATUS_OPEN]
        if asset:
            q += " AND asset = ?"
            params.append(asset.upper())
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(q, params).fetchall()
        return [self._row_to_thesis(r) for r in rows]

    def all(self, limit: int = 50) -> list[Thesis]:
        """Todas as teses (mais recentes primeiro)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM theses ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_thesis(r) for r in rows]

    @staticmethod
    def _row_to_thesis(r: sqlite3.Row) -> Thesis:
        return Thesis(
            id=r["id"], asset=r["asset"], thesis=r["thesis"],
            alert_level=r["alert_level"], evidence=r["evidence"], status=r["status"],
            created_at=r["created_at"], reviewed_at=r["reviewed_at"],
            review_note=r["review_note"],
        )
