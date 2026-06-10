"""Decisão do dia (cockpit): tradução mecânica do peso fracionário em UMA ação.

LINHA VERMELHA testada por construção: daily_decision recebe SÓ w_live/trades/close
do motor — postura, valuation e cone nem entram na assinatura. Aqui validamos as 6
ações, a estatística pós-saída (janela até a REENTRADA, não até hoje) e os edges.
"""

import numpy as np
import pandas as pd

from trendfit.cockpit import _post_exit_stats, daily_decision


def _w(vals):
    idx = pd.date_range("2024-01-01", periods=len(vals), freq="D", tz="UTC")
    return pd.Series(vals, index=idx, dtype=float)


def _close(vals, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(vals), freq="D", tz="UTC")
    return pd.Series(vals, index=idx, dtype=float)


# ---------------- as 6 ações ----------------

def test_compro_quando_entra_de_caixa():
    d = daily_decision(_w([0, 0, 0, 0.5]), [], _close([100] * 4))
    assert d["action"] == "COMPRO"
    assert d["frac_today"] == 0.5
    assert d["frac_prev"] == 0.0


def test_compro_mais_quando_fracao_sobe():
    d = daily_decision(_w([0, 1 / 3, 1 / 3, 2 / 3]), [], _close([100] * 4))
    assert d["action"] == "COMPRO_MAIS"
    assert abs(d["frac_prev"] - 1 / 3) < 1e-9


def test_reduzo_quando_fracao_cai():
    d = daily_decision(_w([0, 1.0, 1.0, 2 / 3]), [], _close([100] * 4))
    assert d["action"] == "REDUZO"
    assert d["frac_prev"] == 1.0


def test_mantenho_quando_fracao_estavel():
    d = daily_decision(_w([0, 1.0, 1.0, 1.0]), [], _close([100] * 4))
    assert d["action"] == "MANTENHO"
    assert d["last_change"] == "2024-01-02"  # dia em que virou 1.0
    assert d["frac_prev"] == 0.0             # de onde veio


def test_saio_no_dia_da_saida():
    d = daily_decision(_w([0, 1.0, 1.0, 0.0]), [], _close([100] * 4))
    assert d["action"] == "SAIO"


def test_fico_fora_depois_da_saida():
    d = daily_decision(_w([1.0, 0.0, 0.0, 0.0]), [], _close([100] * 4))
    assert d["action"] == "FICO_FORA"
    assert d["last_change"] == "2024-01-02"


# ---------------- edges ----------------

def test_serie_vazia_retorna_none():
    assert daily_decision(_w([]), [], _close([])) is None


def test_um_ponto_comprado_vira_compro():
    d = daily_decision(_w([0.5]), [], _close([100]))
    assert d["action"] == "COMPRO"
    assert d["frac_prev"] is None  # nunca mudou dentro da janela


def test_nan_tratado_como_caixa():
    d = daily_decision(_w([np.nan, np.nan, 0.5]), [], _close([100] * 3))
    assert d["action"] == "COMPRO"


def test_deterministico():
    w, tr, cl = _w([0, 0.5, 1.0, 1.0]), [], _close([100, 110, 120, 130])
    assert daily_decision(w, tr, cl) == daily_decision(w, tr, cl)


# ---------------- estatística pós-saída ----------------

def _trades_iso(items):
    """trades como o asset_cockpit serializa: datas ISO string (a armadilha de tz)."""
    return [{"entry_date": e, "exit_date": x, "entry_px": ep, "exit_px": xp,
             "ret": xp / ep - 1} for e, x, ep, xp in items]


def test_post_exit_janela_ate_reentrada_nao_ate_hoje():
    # preço: saída a 100 no dia 3; mínimo 90 antes da reentrada (dia 6); DEPOIS da
    # reentrada despenca a 50 — esse tombo é do trade seguinte, NÃO da saída.
    close = _close([100, 110, 105, 100, 95, 90, 95, 80, 50, 50])
    trades = _trades_iso([
        ("2024-01-01", "2024-01-04", 100.0, 100.0),  # saiu dia 4 (preço 100)
        ("2024-01-07", None, 95.0, 50.0),            # reentrou dia 7 (aberto)
    ])
    trades[1]["open"] = True
    pe = _post_exit_stats(trades, close)
    assert pe["n"] == 1
    # mínimo entre saída (04) e reentrada (07) = 90 -> -10%; se a janela fosse até
    # hoje pegaria 50 (-50%) — o bug que este teste trava.
    assert abs(pe["avg_drop_after"] - (90 / 100 - 1)) < 1e-9


def test_post_exit_n_loss_conta_trades_no_prejuizo():
    close = _close([100] * 8)
    trades = _trades_iso([
        ("2024-01-01", "2024-01-03", 100.0, 90.0),   # prejuízo
        ("2024-01-04", "2024-01-06", 90.0, 120.0),   # lucro
    ])
    pe = _post_exit_stats(trades, close)
    assert pe["n"] == 2
    assert pe["n_loss"] == 1


def test_post_exit_strings_iso_com_index_tz_aware():
    # datas ISO string + índice tz-aware: não pode explodir com UTC offset
    close = _close([100, 95, 90, 95, 100])
    trades = _trades_iso([("2024-01-01", "2024-01-02", 100.0, 95.0)])
    pe = _post_exit_stats(trades, close)
    assert pe is not None and pe["n"] == 1


def test_post_exit_sem_trades_fechados():
    assert _post_exit_stats([], _close([100, 101])) is None
    aberto = [{"entry_date": "2024-01-01", "exit_date": None, "entry_px": 100.0,
               "exit_px": 101.0, "ret": 0.01, "open": True}]
    assert _post_exit_stats(aberto, _close([100, 101])) is None
