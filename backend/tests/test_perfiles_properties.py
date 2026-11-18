"""Pruebas de propiedades de perfil-jugador (Properties 1 a 3 del design.md),
edad, número, equipo y jugadas con offside del perfil.

construir_perfiles se prueba con DataFrames en memoria (sin E/S) sobre semillas
de numpy.random.default_rng, y con el conjunto fijo de sinteticos.py.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from backend.offside_service import (
    MIN_SNAPS_SCOUT,
    RANGOS_ETIQUETAS,
    UMBRAL_SCOUT,
    JugadorLista,
    PerfilJugador,
    _edad,
    construir_perfiles,
    rango_velocidad,
    top10_scout,
)

SEMILLAS = list(range(10))
EQUIPOS = ["AAA", "BBB", "CCC"]
S_VALORES = [0.0, 0.1, 0.25, 0.26, 0.5, 0.99, 1.0, 1.01, 2.0, 2.01, 3.5]


def etiqueta(s: float) -> str:
    for lim, e in zip([0.25, 0.5, 1, 2], RANGOS_ETIQUETAS):
        if s <= lim:
            return e
    return ">2"


def modas(valores) -> set:
    serie = pd.Series(list(valores)).dropna()
    if serie.empty:
        return {None}
    conteo = serie.value_counts()
    return set(conteo[conteo == conteo.max()].index)


def generar_datos(rng):
    """datos (plays, tracking_snap, players), alineados y jugadas aleatorios."""
    ids = list(range(1, 13))
    prob = {nid: float(rng.uniform(0.2, 0.9)) for nid in ids}
    prob[12] = 0.95
    p_num = {nid: float(rng.uniform(0.2, 0.8)) for nid in ids}
    n_plays = int(rng.integers(150, 230))
    plays, alin, snap = [], [], []
    for p in range(1, n_plays + 1):
        g = 2040000001 + p % 3
        defensa = str(rng.choice(EQUIPOS))
        plays.append({"gameId": g, "playId": p, "defensiveTeam": defensa,
                      "possessionTeam": str(rng.choice(["XXX", "YYY"])), "down": int(rng.integers(1, 5))})
        presentes = [nid for nid in ids if rng.random() < prob[nid]]
        ofensor = int(rng.choice(presentes)) if presentes and rng.random() < 0.08 else None
        filas_play = []
        for nid in presentes:
            s = float(rng.choice(S_VALORES)) if rng.random() < 0.6 else round(float(rng.uniform(0, 4)), 2)
            numero = nid if rng.random() < p_num[nid] else nid + 50
            if rng.random() < 0.9:  # Rusher_Alineado
                filas_play.append({"gameId": g, "playId": p, "nflId": nid, "s": s,
                                   "offside": int(nid == ofensor), "presion": bool(rng.random() < 0.15),
                                   "down": plays[-1]["down"]})
                snap.append({"gameId": g, "playId": p, "nflId": float(nid), "jerseyNumber": float(numero)})
            else:  # rusher no alineado: su número no cuenta
                snap.append({"gameId": g, "playId": p, "nflId": float(nid), "jerseyNumber": 0.0})
        # 13 es un gemelo exacto de 12 (mismo % y mismos snaps: desempate por nflId)
        for f in list(filas_play):
            if f["nflId"] == 12:
                filas_play.append({**f, "nflId": 13, "offside": 0})
                snap.append({"gameId": g, "playId": p, "nflId": 13.0, "jerseyNumber": 13.0})
        alin += filas_play
        snap.append({"gameId": g, "playId": p, "nflId": np.nan, "jerseyNumber": np.nan})  # balón
    alineados = pd.DataFrame(alin)
    alineados["nflId"] = alineados["nflId"].astype("Int64")
    alineados["rango"] = rango_velocidad(alineados["s"]).values

    players = []
    for nid in range(1, 14):
        if nid == 12:
            continue  # sin fila en players.csv
        players.append({
            "nflId": nid, "displayName": f"Jugador {nid}",
            "height": None if rng.random() < 0.2 else f"6-{int(rng.integers(0, 7))}",
            "weight": np.nan if rng.random() < 0.2 else float(rng.integers(220, 330)),
            "birthDate": None if rng.random() < 0.2 else f"{int(rng.integers(1985, 2000))}-{int(rng.integers(1, 13)):02d}-09",
            "collegeName": None if rng.random() < 0.2 else f"Universidad {nid}",
            "officialPosition": None if rng.random() < 0.2 else str(rng.choice(["OLB", "DE", "DT"])),
        })
    plays_df = pd.DataFrame(plays)
    of = alineados[alineados["offside"] == 1].merge(plays_df[["gameId", "playId", "possessionTeam"]])
    of = of.sort_values(["s", "gameId", "playId"], ascending=[False, True, True])
    jugadas = [{"gameId": int(r.gameId), "playId": int(r.playId), "s_snap": float(r.s),
                "equipo_ofensiva": r.possessionTeam, "infractor": {"nflId": int(r.nflId), "nombre": ""}}
               for r in of.itertuples(index=False)]
    datos = {"plays": plays_df, "tracking_snap": pd.DataFrame(snap), "players": pd.DataFrame(players)}
    return datos, alineados, jugadas


@pytest.fixture(scope="module")
def casos():
    out = {}
    for semilla in SEMILLAS:
        datos, alineados, jugadas = generar_datos(np.random.default_rng(semilla))
        out[semilla] = (datos, alineados, jugadas, construir_perfiles(datos, alineados, jugadas))
    return out


# ---------------------------------------------------------------------------
# Property 1: Elegibilidad y orden
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p1_elegibilidad_y_orden(semilla, casos):
    """Feature: perfil-jugador, Property 1: Elegibilidad y orden"""
    datos, alineados, _, (lista, perfiles) = casos[semilla]
    conteo = alineados.groupby("nflId").size()
    elegibles = {int(k) for k, v in conteo.items() if v >= MIN_SNAPS_SCOUT}
    assert {j["nflId"] for j in lista} == elegibles == set(perfiles)
    assert 12 in elegibles and 13 in elegibles  # el gemelo exacto también es elegible
    for j in lista:
        JugadorLista.model_validate(j)
        assert j["rusher_snaps"] >= MIN_SNAPS_SCOUT
        assert j["rusher_snaps"] == int(conteo[j["nflId"]])
    llaves = [(-j["pct_anticipa"], -j["rusher_snaps"], j["nflId"]) for j in lista]
    assert llaves == sorted(llaves)
    pos = [j["nflId"] for j in lista]
    assert pos.index(12) == pos.index(13) - 1  # empate exacto: menor nflId primero
    top = top10_scout(alineados, datos["players"])
    assert [(j["nflId"], j["nombre"]) for j in lista[:10]] == [(t["nflId"], t["nombre"]) for t in top]


# ---------------------------------------------------------------------------
# Property 2: Consistencia de stats
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p2_consistencia_stats(semilla, casos):
    """Feature: perfil-jugador, Property 2: Consistencia de stats"""
    _, alineados, _, (lista, perfiles) = casos[semilla]
    pcts = {j["nflId"]: j["pct_anticipa"] for j in lista}
    for j in lista:
        nid = j["nflId"]
        p = perfiles[nid]
        PerfilJugador.model_validate(p)
        st = p["stats"]
        sub = alineados[alineados["nflId"] == nid]
        ant = sub[sub["s"] >= UMBRAL_SCOUT]
        no_ant = sub[sub["s"] < UMBRAL_SCOUT]
        assert st["anticipando"]["snaps"] + st["sin_anticipar"]["snaps"] == st["rusher_snaps"]
        assert st["anticipando"]["snaps"] == len(ant)
        assert st["pct_anticipa"] == pytest.approx(st["anticipando"]["snaps"] / st["rusher_snaps"] * 100)
        assert 0 < st["percentil_anticipacion"] <= 100
        assert st["percentil_anticipacion"] == pytest.approx(
            sum(v <= pcts[nid] for v in pcts.values()) / len(pcts) * 100)
        assert st["velocidad_media_snap"] == pytest.approx(sub["s"].mean())
        assert st["pct_presion"] == pytest.approx(sub["presion"].mean() * 100)
        assert st["offsides"] == int(sub["offside"].sum())
        for grupo, df in (("anticipando", ant), ("sin_anticipar", no_ant)):
            esperado = None if len(df) == 0 else df["presion"].mean() * 100
            assert st[grupo]["pct_presion"] == (None if esperado is None else pytest.approx(esperado))
        # la lista coincide con el perfil
        assert j["nombre"] == p["ficha"]["nombre"] and j["equipo"] == p["ficha"]["equipo"]
        assert j["posicion"] == p["ficha"]["posicion"] and j["numero"] == p["ficha"]["numero"]
        assert (j["rusher_snaps"], j["pct_anticipa"], j["pct_presion"], j["offsides"]) == (
            st["rusher_snaps"], st["pct_anticipa"], st["pct_presion"], st["offsides"])
    if lista:  # el primero de la lista tiene percentil 100
        assert perfiles[lista[0]["nflId"]]["stats"]["percentil_anticipacion"] == 100.0


# ---------------------------------------------------------------------------
# Property 3: Distribución
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p3_distribucion(semilla, casos):
    """Feature: perfil-jugador, Property 3: Distribución"""
    _, alineados, _, (_, perfiles) = casos[semilla]
    etiquetas_liga = [etiqueta(s) for s in alineados["s"]]
    for nid, p in perfiles.items():
        dist = p["distribucion"]
        assert [d["rango"] for d in dist] == RANGOS_ETIQUETAS
        assert sum(d["pct_jugador"] for d in dist) == pytest.approx(100.0)
        assert sum(d["pct_liga"] for d in dist) == pytest.approx(100.0)
        propias = [etiqueta(s) for s in alineados.loc[alineados["nflId"] == nid, "s"]]
        for d in dist:
            assert d["pct_jugador"] == pytest.approx(propias.count(d["rango"]) / len(propias) * 100)
            assert d["pct_liga"] == pytest.approx(etiquetas_liga.count(d["rango"]) / len(etiquetas_liga) * 100)


# ---------------------------------------------------------------------------
# Ficha: número, equipo, jugadas con offside y campos de players.csv
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_ficha_numero_equipo_y_offsides(semilla, casos):
    """Numero_Jugador y Equipo_Jugador son los más frecuentes en sus Rusher_Alineado;
    jugadas_offside son sus Jugada_Offside; los campos sin dato son null."""
    datos, alineados, jugadas, (_, perfiles) = casos[semilla]
    snap = datos["tracking_snap"].dropna(subset=["nflId"])
    llaves = alineados[["gameId", "playId", "nflId"]].astype({"nflId": "int64"})
    snap_al = snap.astype({"nflId": "int64"}).merge(llaves, on=["gameId", "playId", "nflId"])
    equipos = alineados.merge(datos["plays"][["gameId", "playId", "defensiveTeam"]], on=["gameId", "playId"])
    info = {int(r["nflId"]): r for _, r in datos["players"].iterrows()}
    for nid, p in perfiles.items():
        f = p["ficha"]
        assert f["numero"] in modas(snap_al.loc[snap_al["nflId"] == nid, "jerseyNumber"].astype(int))
        assert f["numero"] != 0  # nunca el de un snap no alineado
        assert f["equipo"] in modas(equipos.loc[equipos["nflId"] == nid, "defensiveTeam"])
        assert p["jugadas_offside"] == [
            {"gameId": j["gameId"], "playId": j["playId"], "s_snap": j["s_snap"], "rival": j["equipo_ofensiva"]}
            for j in jugadas if j["infractor"]["nflId"] == nid]
        r = info.get(nid)
        if r is None:  # sin fila en players.csv
            assert f == {**f, "nombre": str(nid), "posicion": None, "estatura": None, "peso": None,
                         "edad": None, "universidad": None}
            continue
        assert f["nombre"] == r["displayName"]
        assert f["posicion"] == (None if pd.isna(r["officialPosition"]) else r["officialPosition"])
        assert f["estatura"] == (None if pd.isna(r["height"]) else r["height"])
        assert f["peso"] == (None if pd.isna(r["weight"]) else int(r["weight"]))
        assert f["universidad"] == (None if pd.isna(r["collegeName"]) else r["collegeName"])
        if pd.isna(r["birthDate"]):
            assert f["edad"] is None
        else:
            y, m, _ = map(int, r["birthDate"].split("-"))
            assert f["edad"] == 2021 - y - (1 if m > 9 else 0)  # nacidos un día 9


def test_vacios():
    """Sin alineados no hay perfiles; con menos de 100 snaps tampoco."""
    vacio = pd.DataFrame(columns=["gameId", "playId", "nflId", "s", "offside", "presion"])
    datos = {"plays": pd.DataFrame(columns=["gameId", "playId", "defensiveTeam"]),
             "tracking_snap": pd.DataFrame(), "players": pd.DataFrame()}
    assert construir_perfiles(datos, vacio, []) == ([], {})
    pocos = pd.DataFrame({"gameId": [1] * 99, "playId": range(99), "nflId": [7] * 99,
                          "s": [1.0] * 99, "offside": [0] * 99, "presion": [False] * 99})
    datos["plays"] = pd.DataFrame({"gameId": [1] * 99, "playId": range(99), "defensiveTeam": ["AAA"] * 99})
    assert construir_perfiles(datos, pocos, []) == ([], {})


# ---------------------------------------------------------------------------
# _edad: años cumplidos al 2021-09-09
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nacimiento, edad", [
    ("1992-11-17", 28),      # cumpleaños después del 9 de septiembre
    ("1992-03-01", 29),      # antes
    ("1992-09-08", 29),      # un día antes de la referencia
    ("1992-09-09", 29),      # el mismo día: ya los cumplió
    ("1992-09-10", 28),      # un día después
    ("1996-02-29", 25),      # año bisiesto
    ("11/17/1992", 28),      # otro formato de fecha
    (pd.Timestamp("1990-12-31"), 30),
    (None, None),
    (float("nan"), None),
    (np.nan, None),
    (pd.NaT, None),
    ("", None),
    ("no es fecha", None),
])
def test_edad(nacimiento, edad):
    assert _edad(nacimiento) == edad


def test_edad_referencia_propia():
    assert _edad("2000-06-15", pd.Timestamp("2010-06-14")) == 9
    assert _edad("2000-06-15", pd.Timestamp("2010-06-15")) == 10


# ---------------------------------------------------------------------------
# Conjunto fijo con valores calculados a mano
# ---------------------------------------------------------------------------
def test_lista_conjunto_cp(resultado_cp, esperado_cp):
    """Orden con empates (302/303 por nflId, 301 por snaps), frontera de 100 snaps y 304 fuera."""
    lista = resultado_cp["jugadores"]
    assert [(j["nflId"], j["nombre"], j["rusher_snaps"], j["pct_anticipa"]) for j in lista] == esperado_cp["jugadores"]
    for j in lista:
        JugadorLista.model_validate(j)
        f = esperado_cp["fichas"][j["nflId"]]
        assert (j["equipo"], j["posicion"], j["numero"]) == (f["equipo"], f["posicion"], f["numero"])
    for nid in esperado_cp["no_elegibles"]:
        assert nid not in resultado_cp["perfiles"]
    # Top_10_Scout y la lista coinciden
    top = resultado_cp["offside"]["top10_scout"]["jugadores"]
    assert [t["nflId"] for t in top] == [j["nflId"] for j in lista[:10]]


def test_perfiles_conjunto_cp(resultado_cp, esperado_cp):
    """Ficha (con birthDate vacío, peso y universidad vacíos), stats, distribución y offsides."""
    perfiles = resultado_cp["perfiles"]
    for nid, ficha in esperado_cp["fichas"].items():
        PerfilJugador.model_validate(perfiles[nid])
        assert perfiles[nid]["ficha"] == ficha, nid
    p = perfiles[301]
    st = p["stats"]
    for k, v in esperado_cp["stats_301"].items():
        assert st[k] == (pytest.approx(v) if isinstance(v, float) else v), k
    assert [(d["rango"], pytest.approx(d["pct_jugador"])) for d in p["distribucion"]] == [
        (r, pytest.approx(v)) for r, v in esperado_cp["distribucion_301"]]
    assert p["jugadas_offside"] == esperado_cp["jugadas_offside_301"]
    assert perfiles[300]["stats"]["percentil_anticipacion"] == 100.0
    assert perfiles[302]["stats"]["percentil_anticipacion"] == 75.0
    for nid in (300, 302, 303):
        assert perfiles[nid]["jugadas_offside"] == []
    # pct_liga es el mismo para todos y suma 100
    ligas = {tuple(d["pct_liga"] for d in pp["distribucion"]) for pp in perfiles.values()}
    assert len(ligas) == 1 and math.isclose(sum(next(iter(ligas))), 100.0)
