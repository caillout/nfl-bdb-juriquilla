"""Pruebas de propiedades de equipos (Properties 1 y 2 del design.md).

metricas_equipos se prueba con DataFrames en memoria sobre semillas de
numpy.random.default_rng (con equipos gemelos para forzar empates) y con el
conjunto fijo de sinteticos.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.offside_service import (
    UMBRAL_SCOUT,
    EquiposResponse,
    metricas_equipos,
)

SEMILLAS = list(range(25))
DEFENSAS = ["AAA", "BBB", "CCC", "DDD", "EEE"]
OFENSIVAS = ["PPP", "QQQ", "RRR", "SSS", "TTT"]
S_VALORES = [0.0, 0.25, 0.5, 0.99, 1.0, 1.01, 2.0, 3.0]


def generar(rng):
    """(alineados, plays) aleatorios; YYY es gemela de la defensa BBB y VVV de la ofensiva QQQ."""
    plays, filas = [], []
    n_plays = int(rng.integers(20, 120))
    for p in range(1, n_plays + 1):
        g = 2050000001 + p % 4
        plays.append({"gameId": g, "playId": p, "defensiveTeam": str(rng.choice(DEFENSAS)),
                      "possessionTeam": str(rng.choice(OFENSIVAS))})
        n = int(rng.integers(1, 5))
        ofensor = int(rng.integers(0, n)) if rng.random() < 0.1 else -1
        for k in range(n):
            filas.append({"gameId": g, "playId": p, "nflId": 100 + k, "s": float(rng.choice(S_VALORES)),
                          "offside": int(k == ofensor), "presion": bool(rng.random() < 0.2)})
    plays_df, al = pd.DataFrame(plays), pd.DataFrame(filas)
    # gemelos: mismas filas en jugadas nuevas -> mismo % (empate que se rompe por siglas)
    extra_p, extra_a = [plays_df], [al]
    siguiente = n_plays + 1
    for col, origen, gemelo, otro_col, otro in (("defensiveTeam", "BBB", "YYY", "possessionTeam", "WWW"),
                                                ("possessionTeam", "QQQ", "VVV", "defensiveTeam", "XXX")):
        sel = plays_df[plays_df[col] == origen]
        nuevos = np.arange(siguiente, siguiente + len(sel))
        siguiente += len(sel)
        mapa = sel[["gameId", "playId"]].assign(nuevo=nuevos)
        copia = al.merge(mapa, on=["gameId", "playId"]).drop(columns="playId").rename(columns={"nuevo": "playId"})
        extra_a.append(copia[al.columns])
        extra_p.append(pd.DataFrame({"gameId": sel["gameId"].to_numpy(), "playId": nuevos,
                                     col: gemelo, otro_col: otro}))
    plays_df = pd.concat(extra_p, ignore_index=True)
    al = pd.concat(extra_a, ignore_index=True)
    return al.sample(frac=1, random_state=int(rng.integers(1 << 31))).reset_index(drop=True), plays_df


@pytest.fixture(scope="module")
def casos():
    out = {}
    for semilla in SEMILLAS:
        al, plays = generar(np.random.default_rng(semilla))
        out[semilla] = (al, plays, metricas_equipos(al, plays))
    return out


def referencia(al, plays, col):
    df = al.merge(plays, on=["gameId", "playId"])
    out = {}
    for eq, g in df.groupby(col):
        n = len(g)
        out[eq] = {"n": n, "ant": float((g["s"] >= UMBRAL_SCOUT).mean() * 100),
                   "pres": float(g["presion"].mean() * 100), "off": int(g["offside"].sum()),
                   "por_1000": float(g["offside"].sum() / n * 1000)}
    return out


@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p1_conservacion(semilla, casos):
    """Feature: equipos, Property 1: Conservación"""
    al, plays, res = casos[semilla]
    EquiposResponse.model_validate(res)
    total, total_of = len(al), int(al["offside"].sum())
    assert sum(d["rusher_snaps"] for d in res["defensas"]) == total
    assert sum(o["rusher_snaps_rival"] for o in res["ofensivas"]) == total
    assert sum(d["offsides"] for d in res["defensas"]) == total_of
    assert sum(o["offsides_provocados"] for o in res["ofensivas"]) == total_of

    ref_d = referencia(al, plays, "defensiveTeam")
    assert {d["equipo"] for d in res["defensas"]} == set(ref_d)
    for d in res["defensas"]:
        r = ref_d[d["equipo"]]
        assert d["rusher_snaps"] == r["n"] and d["offsides"] == r["off"]
        assert d["pct_anticipa"] == pytest.approx(r["ant"])
        assert d["pct_presion"] == pytest.approx(r["pres"])
        assert d["offsides_por_1000"] == pytest.approx(r["por_1000"])
        assert 0 <= d["pct_anticipa"] <= 100 and 0 <= d["pct_presion"] <= 100
    ref_o = referencia(al, plays, "possessionTeam")
    assert {o["equipo"] for o in res["ofensivas"]} == set(ref_o)
    for o in res["ofensivas"]:
        r = ref_o[o["equipo"]]
        assert o["rusher_snaps_rival"] == r["n"] and o["offsides_provocados"] == r["off"]
        assert o["pct_anticipa_rival"] == pytest.approx(r["ant"])
        assert o["offsides_por_1000"] == pytest.approx(r["por_1000"])


@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p2_orden(semilla, casos):
    """Feature: equipos, Property 2: Orden"""
    _, _, res = casos[semilla]
    d = res["defensas"]
    llaves = [(-x["pct_anticipa"], x["equipo"]) for x in d]
    assert llaves == sorted(llaves)
    o = res["ofensivas"]
    llaves = [(-x["offsides_por_1000"], -x["pct_anticipa_rival"], x["equipo"]) for x in o]
    assert llaves == sorted(llaves)
    # gemelas: mismo % -> el desempate es por siglas ascendente
    eq_d = [x["equipo"] for x in d]
    if "YYY" in eq_d:
        bbb, yyy = d[eq_d.index("BBB")], d[eq_d.index("YYY")]
        assert bbb["pct_anticipa"] == yyy["pct_anticipa"]
        assert eq_d.index("BBB") < eq_d.index("YYY")
    eq_o = [x["equipo"] for x in o]
    if "VVV" in eq_o:
        qqq, vvv = o[eq_o.index("QQQ")], o[eq_o.index("VVV")]
        assert (qqq["offsides_por_1000"], qqq["pct_anticipa_rival"]) == (vvv["offsides_por_1000"], vvv["pct_anticipa_rival"])
        assert eq_o.index("QQQ") < eq_o.index("VVV")


def test_orden_desempates_explicitos():
    """Desempates de ofensivas: offsides_por_1000 desc, luego pct_anticipa_rival desc, luego siglas."""
    plays = pd.DataFrame({
        "gameId": [1] * 6, "playId": range(1, 7),
        "defensiveTeam": ["D1", "D1", "D2", "D2", "D3", "D3"],
        "possessionTeam": ["O3", "O3", "O1", "O1", "O2", "O2"],
    })
    al = pd.DataFrame({
        "gameId": [1] * 6, "playId": range(1, 7), "nflId": [1] * 6,
        "s": [1.5, 0.0, 1.5, 0.0, 0.0, 0.0],   # D1/O3 y D2/O1 con 50 %, D3/O2 con 0 %
        "offside": [0, 0, 0, 0, 0, 0], "presion": [False] * 6,
    })
    res = metricas_equipos(al, plays)
    assert [d["equipo"] for d in res["defensas"]] == ["D1", "D2", "D3"]
    assert [o["equipo"] for o in res["ofensivas"]] == ["O1", "O3", "O2"]
    al.loc[5, "offside"] = 1  # O2 provoca un offside: pasa al primer lugar
    res = metricas_equipos(al, plays)
    assert [o["equipo"] for o in res["ofensivas"]] == ["O2", "O1", "O3"]
    assert [d["equipo"] for d in res["defensas"]] == ["D1", "D2", "D3"]


def test_vacio():
    res = metricas_equipos(pd.DataFrame(columns=["gameId", "playId", "nflId", "s", "offside"]),
                           pd.DataFrame(columns=["gameId", "playId", "defensiveTeam", "possessionTeam"]))
    assert res["defensas"] == [] and res["ofensivas"] == []
    assert isinstance(res["nota"], str) and res["nota"]


@pytest.mark.xfail(
    reason="BUG: metricas_equipos (offside_service.py:1116-1128) hace un left join con plays y agrupa "
           "por defensiveTeam/possessionTeam; groupby descarta las llaves NaN, así que un "
           "Rusher_Alineado cuya jugada no está en plays.csv (o sin equipo) desaparece de los rankings "
           "aunque sí cuenta en totales de /api/offside (rompe la Property 1: Conservación).",
    strict=True,
)
def test_p1_conservacion_jugada_sin_equipo():
    """Property 1 con un Rusher_Alineado cuya jugada no aparece en plays."""
    plays = pd.DataFrame({"gameId": [1], "playId": [1], "defensiveTeam": ["D1"], "possessionTeam": ["O1"]})
    al = pd.DataFrame({"gameId": [1, 1], "playId": [1, 2], "nflId": [7, 7], "s": [0.0, 1.0],
                       "offside": [0, 1], "presion": [False, False]})
    res = metricas_equipos(al, plays)
    assert sum(d["rusher_snaps"] for d in res["defensas"]) == len(al)
    assert sum(d["offsides"] for d in res["defensas"]) == int(al["offside"].sum())


# ---------------------------------------------------------------------------
# Conjunto fijo con valores calculados a mano
# ---------------------------------------------------------------------------
def test_equipos_conjunto_cp(resultado_cp):
    """KC: 202 snaps (150 anticipando, 2 offsides); TB: 437 (109); NYG: 48 (3, 7 offsides)."""
    eq = resultado_cp["equipos"]
    EquiposResponse.model_validate(eq)
    totales = resultado_cp["offside"]["totales"]
    obtenido = [(d["equipo"], d["rusher_snaps"], d["offsides"]) for d in eq["defensas"]]
    assert obtenido == [("KC", 202, 2), ("TB", 437, 0), ("NYG", 48, 7)]
    assert [d["pct_anticipa"] for d in eq["defensas"]] == pytest.approx([150 / 202 * 100, 109 / 437 * 100, 6.25])
    nyg = eq["defensas"][2]
    assert nyg["pct_presion"] == pytest.approx(26 / 48 * 100)  # el relleno 499 presiona en las 26
    assert nyg["offsides_por_1000"] == pytest.approx(7 / 48 * 1000)
    assert [(o["equipo"], o["offsides_provocados"]) for o in eq["ofensivas"]] == [("DAL", 7), ("BUF", 2), ("NE", 0)]
    assert sum(d["rusher_snaps"] for d in eq["defensas"]) == totales["rusher_snaps"] == 687
    assert sum(o["rusher_snaps_rival"] for o in eq["ofensivas"]) == totales["rusher_snaps"]
    assert sum(d["offsides"] for d in eq["defensas"]) == totales["offsides"] == 9
    assert sum(o["offsides_provocados"] for o in eq["ofensivas"]) == totales["offsides"]
    assert "offsides" in eq["nota"].lower()


def test_equipos_conjunto_fijo(resultado_sintetico, esperado_sintetico):
    """Primer conjunto fijo: una sola defensa (DEF) y una sola ofensiva (OFF) con todos los totales."""
    eq = resultado_sintetico["equipos"]
    t = esperado_sintetico["totales"]
    assert [(d["equipo"], d["rusher_snaps"], d["offsides"]) for d in eq["defensas"]] == [
        ("DEF", t["rusher_snaps"], t["offsides"])]
    assert [(o["equipo"], o["rusher_snaps_rival"], o["offsides_provocados"]) for o in eq["ofensivas"]] == [
        ("OFF", t["rusher_snaps"], t["offsides"])]
