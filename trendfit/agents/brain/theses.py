"""Memória de teses do Buffett Jr — julgamento ADAPTÁVEL + placar de acerto.

"Nossa regra precisa ser adaptável, retestar." E mais (pedido do Bruno): monitorar
as opiniões do agente ao longo do tempo pra ver se ele ACERTA ou ERRA — aprendizado.

Cada tese guarda a postura recomendada (stance) + o preço no momento (snapshot) + um
horizonte. Quando o horizonte vence, `resolve(preço_atual)` julga objetivamente:
- stance DEFENSIVO (sair/cautela): acerto se o preço caiu, erro se subiu forte.
- stance ACUMULAR (comprar): o inverso.
- stance NEUTRO: acerto se ficou de lado.
O `scoreboard()` agrega a taxa de acerto. É o WFA honesto: registra hoje, confere depois.

Persistência: SQLite (db/buffett_brain.db, gitignored). Desacoplado do engine e do
data layer (quem coleta o preço é o chamador — ver scripts/thesis_tracker.py).
LINHA VERMELHA: tese é julgamento do assessor — nunca sinal mecânico nem ordem.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

# status de uma tese ao longo do tempo
STATUS_OPEN = "aberta"
STATUS_HIT = "acerto"
STATUS_MISS = "erro"
STATUS_NEUTRAL = "neutra"
_VALID_STATUS = {STATUS_OPEN, STATUS_HIT, STATUS_MISS, STATUS_NEUTRAL}

# posturas que o agente pode recomendar
STANCE_DEFENSIVE = "defensivo"   # sair / aliviar / cautela
STANCE_NEUTRAL = "neutro"        # manter / esperar
STANCE_ACCUMULATE = "acumular"   # comprar / aumentar
_VALID_STANCE = {STANCE_DEFENSIVE, STANCE_NEUTRAL, STANCE_ACCUMULATE}

_NEW_COLUMNS = {  # coluna -> SQL de criação (para migração de db antigo)
    "stance": "TEXT NOT NULL DEFAULT 'neutro'",
    "price_at": "REAL",
    "horizon_days": "INTEGER NOT NULL DEFAULT 14",
    "outcome_price": "REAL",
    "return_pct": "REAL",
}


@dataclass
class Thesis:
    """Uma tese registrada do assessor (com snapshot e resultado)."""

    id: int
    asset: str
    thesis: str
    alert_level: int          # 1 (tranquilo) a 10 (perigo extremo)
    evidence: str
    stance: str               # defensivo / neutro / acumular
    price_at: float | None    # preço do ativo no registro (snapshot)
    horizon_days: int         # dias até reavaliar
    status: str               # aberta / acerto / erro / neutra
    created_at: str
    reviewed_at: str | None = None
    review_note: str = ""
    outcome_price: float | None = None
    return_pct: float | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "asset": self.asset, "thesis": self.thesis,
            "alert_level": self.alert_level, "evidence": self.evidence,
            "stance": self.stance, "price_at": self.price_at,
            "horizon_days": self.horizon_days, "status": self.status,
            "created_at": self.created_at, "reviewed_at": self.reviewed_at,
            "review_note": self.review_note, "outcome_price": self.outcome_price,
            "return_pct": self.return_pct,
        }


class ThesisStore:
    """Armazena, reavalia e pontua as teses do Buffett Jr (SQLite)."""

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
                    stance TEXT NOT NULL DEFAULT 'neutro',
                    price_at REAL,
                    horizon_days INTEGER NOT NULL DEFAULT 14,
                    status TEXT NOT NULL DEFAULT 'aberta',
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    review_note TEXT NOT NULL DEFAULT '',
                    outcome_price REAL,
                    return_pct REAL
                )
                """
            )
            # migração: adiciona colunas novas se o db é de uma versão anterior
            existing = {row[1] for row in conn.execute("PRAGMA table_info(theses)")}
            for col, decl in _NEW_COLUMNS.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE theses ADD COLUMN {col} {decl}")
            conn.commit()

    def record(self, asset: str, thesis: str, alert_level: int, evidence: str = "",
               stance: str = STANCE_NEUTRAL, price_at: float | None = None,
               horizon_days: int = 14) -> int:
        """Registra uma nova tese (status aberta). Retorna o id."""
        level = max(1, min(10, int(alert_level)))
        if stance not in _VALID_STANCE:
            raise ValueError(f"stance inválido: {stance} (use {sorted(_VALID_STANCE)})")
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO theses
                    (asset, thesis, alert_level, evidence, stance, price_at,
                     horizon_days, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (asset.upper(), thesis, level, evidence, stance,
                 float(price_at) if price_at is not None else None,
                 int(horizon_days), STATUS_OPEN, datetime.now().isoformat()),
            )
            conn.commit()
            return int(cur.lastrowid)

    def review(self, thesis_id: int, status: str, note: str = "") -> None:
        """Reavaliação MANUAL: força um status (acerto/erro/neutra) com nota."""
        if status not in _VALID_STATUS:
            raise ValueError(f"status inválido: {status} (use {sorted(_VALID_STATUS)})")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE theses SET status = ?, reviewed_at = ?, review_note = ? WHERE id = ?",
                (status, datetime.now().isoformat(), note, thesis_id),
            )
            conn.commit()

    def resolve(self, thesis_id: int, current_price: float,
                threshold: float = 0.05, note: str = "") -> str:
        """Avaliação AUTOMÁTICA contra o preço atual. Julga acerto/erro/neutra
        conforme a postura recomendada e o movimento do preço. Retorna o status."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM theses WHERE id = ?", (thesis_id,)).fetchone()
            if row is None:
                raise ValueError(f"tese {thesis_id} não existe")
            t = self._row_to_thesis(row)
            if t.price_at is None or t.price_at == 0:
                ret = None
                status = STATUS_NEUTRAL  # sem snapshot de preço, não dá pra julgar
            else:
                ret = (current_price - t.price_at) / t.price_at
                status = self._judge(t.stance, ret, threshold)
            conn.execute(
                """UPDATE theses SET status = ?, reviewed_at = ?, review_note = ?,
                   outcome_price = ?, return_pct = ? WHERE id = ?""",
                (status, datetime.now().isoformat(), note,
                 float(current_price), ret, thesis_id),
            )
            conn.commit()
        return status

    @staticmethod
    def _judge(stance: str, ret: float, thr: float) -> str:
        """Regra de acerto: postura defensiva ganha em queda, acumular ganha em alta."""
        if stance == STANCE_DEFENSIVE:
            if ret <= -thr:
                return STATUS_HIT
            if ret >= thr:
                return STATUS_MISS
            return STATUS_NEUTRAL
        if stance == STANCE_ACCUMULATE:
            if ret >= thr:
                return STATUS_HIT
            if ret <= -thr:
                return STATUS_MISS
            return STATUS_NEUTRAL
        # neutro: acerta se ficou de lado, senão inconclusivo (não pune)
        return STATUS_HIT if abs(ret) < thr else STATUS_NEUTRAL

    def due(self, limit: int = 50) -> list[Thesis]:
        """Teses abertas cujo horizonte já venceu (prontas pra resolver)."""
        now = datetime.now()
        out: list[Thesis] = []
        for t in self.open_theses(limit=200):
            try:
                created = datetime.fromisoformat(t.created_at)
            except ValueError:
                continue
            if created + timedelta(days=t.horizon_days) <= now:
                out.append(t)
            if len(out) >= limit:
                break
        return out

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

    def all(self, limit: int = 100) -> list[Thesis]:
        """Todas as teses (mais recentes primeiro)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM theses ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_thesis(r) for r in rows]

    def scoreboard(self) -> dict:
        """Placar de acerto do agente: total, abertas, resolvidas e taxa de acerto."""
        rows = self.all(limit=10000)
        counts = {STATUS_OPEN: 0, STATUS_HIT: 0, STATUS_MISS: 0, STATUS_NEUTRAL: 0}
        by_asset: dict[str, dict] = {}
        for t in rows:
            counts[t.status] = counts.get(t.status, 0) + 1
            a = by_asset.setdefault(t.asset, {STATUS_HIT: 0, STATUS_MISS: 0})
            if t.status in (STATUS_HIT, STATUS_MISS):
                a[t.status] += 1
        decided = counts[STATUS_HIT] + counts[STATUS_MISS]
        accuracy = (counts[STATUS_HIT] / decided) if decided else None
        for a, d in by_asset.items():
            dec = d[STATUS_HIT] + d[STATUS_MISS]
            d["accuracy"] = (d[STATUS_HIT] / dec) if dec else None
        return {
            "total": len(rows),
            "open": counts[STATUS_OPEN],
            "hit": counts[STATUS_HIT],
            "miss": counts[STATUS_MISS],
            "neutral": counts[STATUS_NEUTRAL],
            "accuracy": accuracy,
            "by_asset": by_asset,
        }

    @staticmethod
    def _row_to_thesis(r: sqlite3.Row) -> Thesis:
        return Thesis(
            id=r["id"], asset=r["asset"], thesis=r["thesis"],
            alert_level=r["alert_level"], evidence=r["evidence"],
            stance=r["stance"], price_at=r["price_at"], horizon_days=r["horizon_days"],
            status=r["status"], created_at=r["created_at"], reviewed_at=r["reviewed_at"],
            review_note=r["review_note"], outcome_price=r["outcome_price"],
            return_pct=r["return_pct"],
        )
