"""Pruebas de propiedades de offside-endpoint (Properties 1 a 9 del design.md).

No se usa Hypothesis (fuera del stack): cada propiedad se parametriza sobre
semillas de numpy.random.default_rng y se agregan casos frontera explícitos.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from backend.offside_service import (
    RANGOS_ETIQUETAS,
    _leer_tracking,
    calcular_cruce,
    es_alineado,
    frame_snap,
    ligar_offsides,
    metricas_por_down,
    metricas_por_rango,
    numero_clave,
    preparar_alineados,
    presion_individual,
    rango_velocidad,
    rushers_en_snap,
    top10_scout,
    cargar_datos,
)
from backend.tests.sinteticos import COLS_TRACKING, G1, G2, filas_jugada

SEMILLAS = list(range(100))
OFS = "Defensive Offside"
FRONTERAS_S = [0.0, 0.25, 0.5, 1.0, 2.0, 0.24, 0.26, 0.49, 0.51, 0.99, 1.01, 1.99, 2.01, 9.99, 10.0]


def etiqueta_esperada(s: float) -> str:
    """Rango_Velocidad esperado (intervalos cerrados a la derecha)."""
    if s <= 0.25:
        return "0-0.25"
    if s <= 0.5:
        return "0.25-0.5"
    if s <= 1:
        return "0.5-1"
    if s <= 2:
        return "1-2"
    return ">2"


def generar_s(rng, n: int, max_s: float = 10.0) -> np.ndarray:
    """Velocidades con 2 decimales, mezcladas con valores frontera."""
    base = np.round(rng.uniform(0, max_s, n), 2)
    fronteras = np.array([v for v in FRONTERAS_S if v <= max_s])
    usar = rng.random(n) < 0.4
    base[usar] = rng.choice(fronteras, usar.sum())
    return base


# ---------------------------------------------------------------------------
# Property 1: Selección de Rusher_Snap
# ---------------------------------------------------------------------------
ROLES = ["Pass Rush", "Pass rush", "Pass", "Pass Block", "Coverage", "PASS RUSH"]


def _escenario_rushers(rng, game_id=2022000001):
    filas, pff, esperado, info = [], [], {}, {}
    for play_id in range(1, int(rng.integers(1, 7)) + 1):
        n_frames = int(rng.integers(2, 12))
        snap = int(rng.integers(1, n_frames + 1))
        evento = rng.choice(["ball_snap", "autoevent_ballsnap", None], p=[0.45, 0.35, 0.2])
        con_balon = bool(rng.random() < 0.9)
        balon_en_snap = bool(rng.random() < 0.85)
        direccion = str(rng.choice(["left", "right"]))
        bx = round(float(rng.uniform(10, 110)), 2)
        ids = rng.choice(np.arange(1, 40), size=int(rng.integers(1, 8)), replace=False)
        jugadores, omitir = [], set()
        for nid in ids:
            nid = int(nid)
            j = {"nflId": nid, "team": str(rng.choice(["DEF", "OFF"])), "numero": nid,
                 "x": round(bx + float(rng.uniform(-4, 4)), 2), "y": 25.0,
                 "s": float(generar_s(rng, 1)[0])}
            jugadores.append(j)
            sin_pos = bool(rng.random() < 0.15)
            if sin_pos:
                omitir.add((nid, snap))
            rol = str(rng.choice(ROLES))
            pff.append({"gameId": game_id, "playId": play_id, "nflId": nid, "pff_role": rol})
            if (rol == "Pass Rush" and evento is not None and con_balon
                    and balon_en_snap and not sin_pos):
                esperado[(game_id, play_id, nid)] = (j["x"], j["s"], bx, direccion)
        # rusher en scouting que no aparece en el tracking
        pff.append({"gameId": game_id, "playId": play_id, "nflId": 999, "pff_role": "Pass Rush"})
        filas += filas_jugada(game_id, play_id, direccion, n_frames, snap,
                              None if evento is None else str(evento), jugadores, bx,
                              con_balon=con_balon, balon_en_snap=balon_en_snap, omitir=omitir)
        # el evento de snap solo existe si quedó alguna fila en ese cuadro
        hay_fila_snap = (con_balon and balon_en_snap) or any(
            (j["nflId"], snap) not in omitir for j in jugadores)
        info[play_id] = (evento if hay_fila_snap else None, snap)
    return filas, pd.DataFrame(pff), esperado, info


@pytest.fixture(scope="module")
def dir_p1(tmp_path_factory):
    return tmp_path_factory.mktemp("p1_tracking")


@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p1_seleccion_rusher_snap(semilla, dir_p1):
    """Feature: offside-endpoint, Property 1: Selección de Rusher_Snap"""
    rng = np.random.default_rng(semilla)
    filas, pff, esperado, info = _escenario_rushers(rng)
    ruta = dir_p1 / f"tracking_{semilla}.csv"
    df = pd.DataFrame(filas, columns=COLS_TRACKING)
    df["nflId"] = df["nflId"].astype("Int64")
    df["jerseyNumber"] = df["jerseyNumber"].astype("Int64")
    df.to_csv(ruta, index=False)

    snap_rows, _ = _leer_tracking(ruta, set())

    # Frame_Snap: solo jugadas con evento de snap y con el frameId correcto
    fs = frame_snap(df.astype({"event": object}).replace({"event": {"None": None}}))
    fs_dict = {(int(g), int(p)): int(f) for g, p, f in zip(fs["gameId"], fs["playId"], fs["frameId"])}
    assert fs_dict == {(2022000001, p): s for p, (ev, s) in info.items() if ev is not None}

    rs = rushers_en_snap(snap_rows, pff)
    obtenido = {(int(g), int(p), int(n)) for g, p, n in zip(rs["gameId"], rs["playId"], rs["nflId"])}
    assert obtenido == set(esperado)
    assert len(rs) == len(esperado)  # sin duplicados
    for r in rs.itertuples(index=False):
        x, s, bx, direccion = esperado[(int(r.gameId), int(r.playId), int(r.nflId))]
        assert r.x == pytest.approx(x, abs=1e-9)
        assert r.s == s  # Velocidad_Snap sin recalcular
        assert r.bx == pytest.approx(bx, abs=1e-9)
        assert r.playDirection == direccion


def test_p1_ejemplo_sintetico(data_sintetica):
    """Feature: offside-endpoint, Property 1: Selección de Rusher_Snap (conjunto fijo:
    sin snap, sin balón, 'Pass rush' en minúscula y rusher sin posición se excluyen)."""
    rs, _ = preparar_alineados(cargar_datos(data_sintetica))
    obtenido = {(int(g), int(p), int(n)) for g, p, n in zip(rs["gameId"], rs["playId"], rs["nflId"])}
    esperado = {(g, p, n) for g, p in [(G1, 10), (G1, 20), (G1, 30), (G2, 10), (G2, 20), (G2, 30)]
                for n in (101, 102)}
    assert obtenido == esperado


def test_p1_vacios():
    """Feature: offside-endpoint, Property 1: Selección de Rusher_Snap (entradas vacías)"""
    vacio_t = pd.DataFrame(columns=["gameId", "playId", "frameId", "nflId", "team", "x", "s", "event"])
    assert frame_snap(vacio_t).empty
    pff = pd.DataFrame({"gameId": [1], "playId": [1], "nflId": [1], "pff_role": ["Pass Rush"]})
    assert rushers_en_snap(vacio_t, pff).empty


# ---------------------------------------------------------------------------
# Property 2: Cruce y alineación
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p2_cruce_y_alineacion(semilla):
    """Feature: offside-endpoint, Property 2: Cruce y alineación"""
    rng = np.random.default_rng(semilla)
    n = 200
    bx_c = rng.integers(0, 12001, n)  # centésimas de yarda
    dif_c = rng.integers(-400, 401, n)
    # fuerza diferencias exactamente en los extremos y justo afuera
    dif_c[:8] = [-150, 50, -151, 51, -149, 49, 0, -150]
    direccion = rng.choice(["left", "right"], n)
    signo = np.where(direccion == "right", -1, 1)
    x_c = bx_c + dif_c * signo  # así (x - bx) * signo == dif_c
    x, bx = x_c / 100.0, bx_c / 100.0
    cruce_c = dif_c
    esperado_alineado = (cruce_c >= -150) & (cruce_c <= 50)

    # escalar
    for i in range(n):
        c = calcular_cruce(float(x[i]), float(bx[i]), str(direccion[i]))
        assert c == pytest.approx(cruce_c[i] / 100.0, abs=1e-9)
        assert c == round(c, 2)
        assert bool(es_alineado(c)) == bool(esperado_alineado[i]), (x[i], bx[i], direccion[i], c)

    # vectorizado con Series y con arreglos
    c_series = calcular_cruce(pd.Series(x), pd.Series(bx), pd.Series(direccion))
    c_arr = calcular_cruce(x, bx, direccion)
    np.testing.assert_allclose(np.asarray(c_series), cruce_c / 100.0, atol=1e-9)
    np.testing.assert_allclose(np.asarray(c_arr), cruce_c / 100.0, atol=1e-9)
    assert (np.asarray(es_alineado(c_series)) == esperado_alineado).all()
    assert (np.asarray(es_alineado(c_arr)) == esperado_alineado).all()


@pytest.mark.parametrize(
    "x, bx, direccion, cruce, alineado",
    [
        (51.01, 52.51, "left", -1.5, True),    # 51.01 - 52.51 = -1.4999999999999964 sin redondeo
        (52.51, 51.01, "right", -1.5, True),
        (53.01, 52.51, "left", 0.5, True),
        (52.51, 53.01, "right", 0.5, True),
        (35.07, 34.57, "right", -0.5, True),
        (34.57, 35.07, "right", 0.5, True),
        (51.00, 52.51, "left", -1.51, False),
        (53.02, 52.51, "left", 0.51, False),
        (52.51, 52.51, "right", 0.0, True),
    ],
)
def test_p2_fronteras_con_dos_decimales(x, bx, direccion, cruce, alineado):
    """Feature: offside-endpoint, Property 2: Cruce y alineación (extremos -1.5 y 0.5)"""
    c = calcular_cruce(x, bx, direccion)
    assert c == cruce
    assert bool(es_alineado(c)) is alineado
    cs = calcular_cruce(pd.Series([x]), pd.Series([bx]), pd.Series([direccion]))
    assert float(cs.iloc[0]) == cruce
    assert bool(es_alineado(cs).iloc[0]) is alineado


# ---------------------------------------------------------------------------
# Property 3: Asignación de Rango_Velocidad y umbrales
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p3_rango_velocidad(semilla):
    """Feature: offside-endpoint, Property 3: Asignación de Rango_Velocidad y umbrales"""
    rng = np.random.default_rng(semilla)
    s = pd.Series(generar_s(rng, 300))
    copia = s.copy()
    rangos = rango_velocidad(s)
    assert list(rangos.cat.categories) == RANGOS_ETIQUETAS
    assert [str(r) for r in rangos] == [etiqueta_esperada(v) for v in s]
    pd.testing.assert_series_equal(s, copia)  # s se usa sin modificar


@pytest.mark.parametrize(
    "s, etiqueta",
    [(0.0, "0-0.25"), (0.25, "0-0.25"), (0.26, "0.25-0.5"), (0.5, "0.25-0.5"),
     (0.51, "0.5-1"), (1.0, "0.5-1"), (1.01, "1-2"), (2.0, "1-2"), (2.01, ">2"), (10.0, ">2")],
)
def test_p3_fronteras_de_rango(s, etiqueta):
    """Feature: offside-endpoint, Property 3: Asignación de Rango_Velocidad y umbrales (fronteras)"""
    assert str(rango_velocidad(pd.Series([s])).iloc[0]) == etiqueta


def _alineados_constantes(s: float, n: int = 100, nflId: int = 7) -> pd.DataFrame:
    return pd.DataFrame({
        "gameId": [1] * n, "playId": list(range(n)), "nflId": [nflId] * n,
        "s": [s] * n, "down": [1] * n, "presion": [False] * n, "offside": [1] + [0] * (n - 1),
    })


def test_p3_s_uno_cuenta_como_movimiento_y_rango_05_1():
    """Feature: offside-endpoint, Property 3: s == 1.0 está en '0.5-1' y cuenta en el Top_10_Scout"""
    df = _alineados_constantes(1.0)
    rangos = {r["rango"]: r for r in metricas_por_rango(df)}
    assert rangos["0.5-1"]["rusher_snaps"] == 100
    assert rangos["1-2"]["rusher_snaps"] == 0
    top = top10_scout(df, pd.DataFrame({"nflId": [7], "displayName": ["Siete"]}))
    assert top[0]["pct_movimiento"] == 100.0
    assert numero_clave(df)["x_pct_snaps"] == 100.0


def test_p3_s_medio_no_cuenta_para_umbral_clave():
    """Feature: offside-endpoint, Property 3: s == 0.5 no cuenta para el Umbral_Clave (s > 0.5)"""
    df = _alineados_constantes(0.5)
    nc = numero_clave(df)
    assert nc["x_pct_snaps"] == 0.0
    assert nc["y_pct_offsides"] == 0.0
    top = top10_scout(df, pd.DataFrame({"nflId": [7], "displayName": ["Siete"]}))
    assert top[0]["pct_movimiento"] == 0.0


# ---------------------------------------------------------------------------
# Property 4: Presión_Individual
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p4_presion_individual(semilla):
    """Feature: offside-endpoint, Property 4: Presión_Individual"""
    rng = np.random.default_rng(semilla)
    n = 100
    valores = rng.choice([np.nan, 0.0, 0.0, 0.0, 1.0, 2.0], size=(n, 3))
    df = pd.DataFrame(valores, columns=["pff_hit", "pff_hurry", "pff_sack"])
    esperado = [sum(0.0 if math.isnan(v) else v for v in fila) > 0 for fila in valores]
    assert list(presion_individual(df)) == esperado
    # también con enteros anulables (como se lee "NA" del CSV)
    assert list(presion_individual(df.astype("Int64"))) == esperado


def test_p4_columnas_ausentes_o_vacias():
    """Feature: offside-endpoint, Property 4: Presión_Individual (vacíos y columnas ausentes = 0)"""
    df = pd.DataFrame({"pff_hit": [np.nan, np.nan, 1], "pff_hurry": [np.nan, 0, np.nan]})
    assert list(presion_individual(df)) == [False, False, True]
    assert list(presion_individual(pd.DataFrame(index=range(2)))) == [False, False]


# ---------------------------------------------------------------------------
# Property 5: Vinculación de offsides
# ---------------------------------------------------------------------------
FALTAS = [OFS, OFS, "Offensive Holding", "Neutral Zone Infraction", "Defensive Holding", None]


@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p5_vinculacion_offsides(semilla):
    """Feature: offside-endpoint, Property 5: Vinculación de offsides"""
    rng = np.random.default_rng(semilla)
    ids = np.arange(1, 15)
    plays, ligados = [], set()
    jugadas = [(1, p) for p in range(1, int(rng.integers(1, 10)) + 1)]
    for g, p in jugadas:
        fila = {"gameId": g, "playId": p}
        for k in (1, 2, 3):
            nombre = rng.choice(FALTAS)
            ident = float(rng.choice(ids)) if rng.random() < 0.9 else np.nan
            fila[f"foulName{k}"] = nombre
            fila[f"foulNFLId{k}"] = ident
            if k in (1, 2) and nombre == OFS and not math.isnan(ident):
                ligados.add((g, p, int(ident)))
        plays.append(fila)
    plays = pd.DataFrame(plays)

    # Rusher_Snap únicos; incluye jugadas que no están en plays
    candidatos = [(g, p, int(n)) for g, p in jugadas + [(2, 1)] for n in ids]
    idx = rng.choice(len(candidatos), size=int(rng.integers(0, len(candidatos) // 2)), replace=False)
    rs = pd.DataFrame([candidatos[i] for i in idx], columns=["gameId", "playId", "nflId"])
    rs["s"] = rng.uniform(0, 3, len(rs))

    res = ligar_offsides(rs, plays)
    assert len(res) == len(rs)
    assert set(res["offside"].unique()) <= {0, 1}
    for r in res.itertuples(index=False):
        assert r.offside == (1 if (r.gameId, r.playId, int(r.nflId)) in ligados else 0)


def test_p5_foulname3_y_sin_faltas():
    """Feature: offside-endpoint, Property 5: Vinculación de offsides (foulName3 se ignora; cero offsides)"""
    rs = pd.DataFrame({"gameId": [1, 1], "playId": [1, 1], "nflId": [10, 11]})
    plays = pd.DataFrame({"gameId": [1], "playId": [1],
                          "foulName1": ["Offensive Holding"], "foulNFLId1": [11.0],
                          "foulName2": [None], "foulNFLId2": [np.nan],
                          "foulName3": [OFS], "foulNFLId3": [10.0]})
    res = ligar_offsides(rs, plays)
    assert list(res["offside"]) == [0, 0]
    # sin columnas de faltas
    res2 = ligar_offsides(rs, plays[["gameId", "playId"]])
    assert list(res2["offside"]) == [0, 0]


# ---------------------------------------------------------------------------
# Generador de Rusher_Alineado para las propiedades 6 a 9
# ---------------------------------------------------------------------------
def generar_alineados(rng, semilla: int, n: int | None = None) -> pd.DataFrame:
    if n is None:
        n = 0 if semilla % 10 == 0 else int(rng.integers(1, 80))
    max_s = 0.5 if semilla % 3 == 0 else 10.0  # rangos vacíos
    df = pd.DataFrame({
        "gameId": rng.integers(1, 4, n),
        "playId": rng.integers(1, 50, n),
        "nflId": rng.integers(1, 20, n),
        "s": generar_s(rng, n, max_s),
        "down": rng.choice([0.0, 1.0, 2.0, 3.0, 4.0, np.nan], n, p=[0.05, 0.3, 0.3, 0.2, 0.1, 0.05]),
        "offside": (rng.random(n) < 0.2).astype("int64"),
    })
    if semilla % 4 == 0:
        df["offside"] = 0  # cero offsides
    if semilla % 2 == 0:
        df["presion"] = rng.random(n) < 0.3
    else:  # presión desde las columnas de PFF, con NaN
        for c in ("pff_hit", "pff_hurry", "pff_sack"):
            df[c] = rng.choice([np.nan, 0.0, 1.0], n, p=[0.5, 0.35, 0.15])
    return df


def _presion_esperada(df: pd.DataFrame) -> list[bool]:
    if "presion" in df.columns:
        return [bool(v) for v in df["presion"]]
    return [
        sum(0.0 if pd.isna(v) else v for v in (h, u, k)) > 0
        for h, u, k in zip(df["pff_hit"], df["pff_hurry"], df["pff_sack"])
    ]


# ---------------------------------------------------------------------------
# Property 6: Métricas por rango
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p6_metricas_por_rango(semilla):
    """Feature: offside-endpoint, Property 6: Métricas por rango"""
    rng = np.random.default_rng(semilla)
    df = generar_alineados(rng, semilla)
    res = metricas_por_rango(df)

    assert [r["rango"] for r in res] == RANGOS_ETIQUETAS
    presion = _presion_esperada(df)
    etiquetas = [etiqueta_esperada(v) for v in df["s"]]
    for r in res:
        idx = [i for i, e in enumerate(etiquetas) if e == r["rango"]]
        n = len(idx)
        ofs = int(sum(df["offside"].iloc[i] for i in idx))
        pres = sum(presion[i] for i in idx)
        assert r["rusher_snaps"] == n
        assert r["offsides"] == ofs
        if n == 0:
            assert r["offsides_por_1000"] is None
            assert r["pct_presion"] is None
        else:
            assert r["offsides_por_1000"] == pytest.approx(ofs / n * 1000)
            assert r["pct_presion"] == pytest.approx(pres / n * 100)
    assert sum(r["rusher_snaps"] for r in res) == len(df)
    assert sum(r["offsides"] for r in res) == int(df["offside"].sum())


# ---------------------------------------------------------------------------
# Property 7: Top_10_Scout
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p7_top10_scout(semilla):
    """Feature: offside-endpoint, Property 7: Top_10_Scout"""
    rng = np.random.default_rng(semilla)
    n_jug = int(rng.integers(0, 21))
    partes = []
    for i in range(n_jug):
        n = int(rng.choice([99, 100, int(rng.integers(60, 140))]))
        p_mov = rng.random()
        s = np.where(rng.random(n) < p_mov, rng.choice([1.0, 1.5, 3.0], n), rng.choice([0.0, 0.5, 0.99], n))
        partes.append(pd.DataFrame({
            "gameId": 1, "playId": np.arange(n), "nflId": 5000 + i, "s": s, "down": 1,
            "presion": rng.random(n) < 0.2, "offside": (rng.random(n) < 0.05).astype("int64"),
        }))
    df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(
        columns=["gameId", "playId", "nflId", "s", "down", "presion", "offside"])
    nombres = {5000 + i: f"Jugador {i}" for i in range(n_jug) if i % 5 != 4}
    players = pd.DataFrame({"nflId": list(nombres), "displayName": list(nombres.values())})

    top = top10_scout(df, players)

    stats = {}
    for nid, g in df.groupby("nflId") if len(df) else []:
        stats[int(nid)] = {
            "rusher_snaps": len(g),
            "pct_movimiento": (g["s"] >= 1.0).mean() * 100,
            "pct_presion": g["presion"].mean() * 100,
            "offsides": int(g["offside"].sum()),
        }
    elegibles = {k: v for k, v in stats.items() if v["rusher_snaps"] >= 100}

    assert len(top) == min(10, len(elegibles))
    pcts = [j["pct_movimiento"] for j in top]
    assert pcts == sorted(pcts, reverse=True)
    for j in top:
        e = elegibles[j["nflId"]]
        assert j["rusher_snaps"] == e["rusher_snaps"] >= 100
        assert j["pct_movimiento"] == pytest.approx(e["pct_movimiento"])
        assert j["pct_presion"] == pytest.approx(e["pct_presion"])
        assert j["offsides"] == e["offsides"]
        assert j["nombre"] == nombres.get(j["nflId"], str(j["nflId"]))
    if top:
        devueltos = {j["nflId"] for j in top}
        minimo = min(pcts)
        for nid, e in elegibles.items():
            if nid not in devueltos:
                assert e["pct_movimiento"] <= minimo + 1e-9


# ---------------------------------------------------------------------------
# Property 8: Offsides por down
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p8_offsides_por_down(semilla):
    """Feature: offside-endpoint, Property 8: Offsides por down"""
    rng = np.random.default_rng(semilla)
    df = generar_alineados(rng, semilla)
    if semilla % 7 == 0 and len(df):
        df = df[df["down"] != 2]  # down sin Rusher_Alineado
    por_down, sin_down = metricas_por_down(df)

    assert [d["down"] for d in por_down] == [1, 2, 3, 4]
    downs = list(df["down"])
    offs = list(df["offside"])
    total_validos = sum(o for d, o in zip(downs, offs) if d in (1, 2, 3, 4))
    for d in por_down:
        idx = [i for i, v in enumerate(downs) if v == d["down"]]
        n = len(idx)
        ofs = sum(offs[i] for i in idx)
        assert d["rusher_snaps"] == n
        assert d["offsides"] == ofs
        if n == 0:
            assert d["offsides_por_1000"] is None
        else:
            assert d["offsides_por_1000"] == pytest.approx(ofs / n * 1000)
        if total_validos == 0:
            assert d["pct_del_total"] is None
        else:
            assert d["pct_del_total"] == pytest.approx(ofs / total_validos * 100)
    if total_validos > 0:
        assert sum(d["pct_del_total"] for d in por_down) == pytest.approx(100.0)

    invalidos = [i for i, v in enumerate(downs) if v not in (1, 2, 3, 4)]
    assert sin_down == {"rusher_snaps": len(invalidos), "offsides": sum(offs[i] for i in invalidos)}
    assert sum(d["rusher_snaps"] for d in por_down) + sin_down["rusher_snaps"] == len(df)
    assert sum(d["offsides"] for d in por_down) + sin_down["offsides"] == int(df["offside"].sum())


def test_p8_vacio():
    """Feature: offside-endpoint, Property 8: Offsides por down (sin Rusher_Alineado)"""
    vacio = pd.DataFrame(columns=["s", "down", "offside"])
    por_down, sin_down = metricas_por_down(vacio)
    assert [d["down"] for d in por_down] == [1, 2, 3, 4]
    assert all(d["rusher_snaps"] == 0 and d["offsides_por_1000"] is None
               and d["pct_del_total"] is None for d in por_down)
    assert sin_down == {"rusher_snaps": 0, "offsides": 0}


# ---------------------------------------------------------------------------
# Property 9: Número_Clave
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p9_numero_clave(semilla):
    """Feature: offside-endpoint, Property 9: Número_Clave"""
    rng = np.random.default_rng(semilla)
    df = generar_alineados(rng, semilla)
    nc = numero_clave(df)
    assert nc["umbral"] == "s > 0.5 yd/s"
    n = len(df)
    if n == 0:
        assert nc["x_pct_snaps"] is None
        assert nc["y_pct_offsides"] is None
        return
    rapido = [v > 0.5 for v in df["s"]]
    offs = list(df["offside"])
    assert nc["x_pct_snaps"] == pytest.approx(sum(rapido) / n * 100)
    total = sum(offs)
    if total == 0:
        assert nc["y_pct_offsides"] is None
    else:
        assert nc["y_pct_offsides"] == pytest.approx(
            sum(o for o, r in zip(offs, rapido) if r) / total * 100)

    # Los valores dependen de los datos: subir todas las s cambia X a 100.
    nc2 = numero_clave(df.assign(s=df["s"] + 10))
    assert nc2["x_pct_snaps"] == 100.0
    if total:
        assert nc2["y_pct_offsides"] == 100.0
