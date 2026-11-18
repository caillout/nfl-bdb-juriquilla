"""Pruebas de propiedades de jugada-evidencia (Properties 1 a 4 del design.md)
y de la búsqueda de Data_Dir (resolver_data_dir)."""
from __future__ import annotations

import numpy as np
import pytest

from backend.offside_service import (
    DatosNoDisponibles,
    VENTANA_ANTES,
    VENTANA_DESPUES,
    calcular_todo,
    cargar_datos,
    normalizar,
    resolver_data_dir,
)
from backend.tests.sinteticos import escribir_data_dir, filas_jugada, jugada_plays

SEMILLAS = list(range(100))
# Las propiedades 2 a 4 escriben y leen un Data_Dir completo por semilla y corren
# calcular_todo (~0.25 s cada una); se usan 30 semillas para mantener la suite rápida.
SEMILLAS_DATASET = list(range(30))
OFS = "Defensive Offside"


# ---------------------------------------------------------------------------
# Property 1: Normalización
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p1_normalizacion(semilla):
    """Feature: jugada-evidencia, Property 1: Normalización"""
    rng = np.random.default_rng(semilla)
    n = 50
    x = np.round(rng.uniform(0, 120, n), 2)
    y = np.round(rng.uniform(0, 53.3, n), 2)
    x[:2], y[:2] = [0.0, 120.0], [0.0, 53.3]  # bordes de la cancha

    # vectorizado
    x1, y1 = normalizar(x, y, np.array(["left"] * n))
    x2, y2 = normalizar(x1, y1, np.array(["left"] * n))
    np.testing.assert_allclose(x2, x, atol=1e-9)
    np.testing.assert_allclose(y2, y, atol=1e-9)
    xr, yr = normalizar(x, y, np.array(["right"] * n))
    np.testing.assert_array_equal(xr, x)
    np.testing.assert_array_equal(yr, y)
    # con 'left' el punto se gira 180° sobre el centro de la cancha
    np.testing.assert_allclose(x1, 120 - x, atol=1e-9)
    np.testing.assert_allclose(y1, 53.3 - y, atol=1e-9)

    # escalar
    for xi, yi in zip(x[:10], y[:10]):
        a, b = normalizar(*normalizar(float(xi), float(yi), "left"), "left")
        assert a == pytest.approx(xi, abs=1e-9) and b == pytest.approx(yi, abs=1e-9)
        assert normalizar(float(xi), float(yi), "right") == (xi, yi)

    # direcciones mezcladas
    d = rng.choice(["left", "right"], n)
    xm, ym = normalizar(x, y, d)
    izq = d == "left"
    np.testing.assert_allclose(xm[izq], 120 - x[izq], atol=1e-9)
    np.testing.assert_array_equal(xm[~izq], x[~izq])
    np.testing.assert_allclose(ym[izq], 53.3 - y[izq], atol=1e-9)


# ---------------------------------------------------------------------------
# Generador de datos de tracking aleatorios con jugadas con offside
# ---------------------------------------------------------------------------
def generar_data_dir(rng, base):
    """Escribe un Data_Dir aleatorio y devuelve los metadatos esperados."""
    tracking, plays, pff, nombres = {}, [], [], {}
    meta = {}  # (g, p) -> dict(snap, n_frames, bx_norm, ofensores {nflId: s})
    for gi in range(int(rng.integers(1, 3))):
        g = 2023000000 + gi
        tracking[g] = []
        for p in range(1, int(rng.integers(1, 4)) + 1):
            n_frames = int(rng.integers(5, 31))
            snap = int(rng.integers(1, n_frames + 1))
            direccion = str(rng.choice(["left", "right"]))
            signo_def = 1 if direccion == "right" else -1  # la defensa está "adelante"
            bx = round(float(rng.uniform(20, 100)), 2)
            rushers = [int(v) for v in rng.choice(np.arange(1000, 1020), int(rng.integers(2, 5)), replace=False)]
            ofensiva = [int(v) for v in rng.choice(np.arange(2000, 2010), int(rng.integers(1, 3)), replace=False)]
            jugadores, s_por_id = [], {}
            for nid in rushers:
                cruce = round(float(rng.uniform(-3, 1)), 2)
                x = round(bx - cruce * signo_def, 2)
                s = float(rng.choice([0.0, 0.25, 0.5, 1.0, 2.0, round(float(rng.uniform(0, 4)), 2)]))
                s_por_id[nid] = s
                jugadores.append({"nflId": nid, "team": "DEF", "numero": nid % 100,
                                  "x": x, "y": float(rng.uniform(5, 48)), "s": s})
                pff.append({"gameId": g, "playId": p, "nflId": nid, "pff_role": "Pass Rush",
                            "pff_hit": int(rng.integers(0, 2)), "pff_hurry": None, "pff_sack": None})
                nombres[nid] = f"Rusher {nid}"
            for nid in ofensiva:
                jugadores.append({"nflId": nid, "team": "OFF", "numero": nid % 100,
                                  "x": round(bx - signo_def * 1.0, 2), "y": float(rng.uniform(5, 48)),
                                  "s": 0.0})
                pff.append({"gameId": g, "playId": p, "nflId": nid, "pff_role": "Pass Block",
                            "pff_hit": None, "pff_hurry": None, "pff_sack": None})
                nombres[nid] = f"Ofensivo {nid}"
            # jugadores que faltan en algunos cuadros (nunca en el snap)
            omitir = {(j["nflId"], f) for j in jugadores for f in range(1, n_frames + 1)
                      if f != snap and rng.random() < 0.05}
            tracking[g] += filas_jugada(g, p, direccion, n_frames, snap,
                                        str(rng.choice(["ball_snap", "autoevent_ballsnap"])),
                                        jugadores, bx, omitir=omitir)
            r = rng.random()
            if r < 0.45:
                fouls = [(OFS, rushers[0])]
            elif r < 0.65:
                fouls = [("Offensive Holding", ofensiva[-1]), (OFS, rushers[1])]
            elif r < 0.8:
                fouls = [(OFS, rushers[0]), (OFS, rushers[1])]
            elif r < 0.9:
                fouls = [(None, None), (None, None), (OFS, rushers[0])]  # foulName3: se ignora
            else:
                fouls = []
            plays.append(jugada_plays(g, p, int(rng.integers(0, 5)), fouls))
            ofensores = {nid: s_por_id[nid] for nombre, nid in fouls[:2] if nombre == OFS}
            meta[(g, p)] = {
                "snap": snap, "n_frames": n_frames, "ofensores": ofensores,
                "bx_norm": round(120 - bx, 2) if direccion == "left" else bx,
            }
    players = [{"nflId": k, "displayName": v} for k, v in nombres.items()]
    escribir_data_dir(base, tracking, plays, pff, players)
    return meta


@pytest.fixture(scope="module")
def casos_aleatorios(tmp_path_factory):
    """Una corrida de calcular_todo por semilla (se comparte entre P2, P3 y P4)."""
    raiz = tmp_path_factory.mktemp("jugadas_aleatorias")
    casos = {}
    for semilla in SEMILLAS_DATASET:
        rng = np.random.default_rng(semilla)
        base = raiz / f"s{semilla}"
        meta = generar_data_dir(rng, base)
        casos[semilla] = (meta, calcular_todo(cargar_datos(base)))
    return casos


# ---------------------------------------------------------------------------
# Property 2: Ventana
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS_DATASET)
def test_p2_ventana(semilla, casos_aleatorios):
    """Feature: jugada-evidencia, Property 2: Ventana"""
    meta, todo = casos_aleatorios[semilla]
    esperadas = {k for k, m in meta.items() if m["ofensores"]}
    assert set(todo["detalles"]) == esperadas
    assert {(j["gameId"], j["playId"]) for j in todo["jugadas"]} == esperadas
    for clave, det in todo["detalles"].items():
        m = meta[clave]
        snap = m["snap"]
        ids = [f["frameId"] for f in det["frames"]]
        assert all(a < b for a, b in zip(ids, ids[1:]))
        assert all(snap - VENTANA_ANTES <= i <= snap + VENTANA_DESPUES for i in ids)
        # todos los cuadros de la Ventana que existen en el archivo
        assert ids == list(range(max(1, snap - VENTANA_ANTES), min(m["n_frames"], snap + VENTANA_DESPUES) + 1))
        assert sum(1 for f in det["frames"] if f["t"] == 0) == 1
        for f in det["frames"]:
            assert f["t"] == pytest.approx((f["frameId"] - snap) / 10)
        assert [v["t"] for v in det["velocidad"]] == [f["t"] for f in det["frames"]]
        assert det["linea_golpeo_x"] == pytest.approx(m["bx_norm"], abs=1e-9)


# ---------------------------------------------------------------------------
# Property 3: Roles
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS_DATASET)
def test_p3_roles(semilla, casos_aleatorios):
    """Feature: jugada-evidencia, Property 3: Roles"""
    meta, todo = casos_aleatorios[semilla]
    for clave, det in todo["detalles"].items():
        id_inf = det["infractor"]["nflId"]
        # el infractor es el ofensor con mayor s en el snap
        ofensores = meta[clave]["ofensores"]
        assert id_inf in ofensores
        assert det["s_snap"] == pytest.approx(max(ofensores.values()))
        for f in det["frames"]:
            roles = [j["rol"] for j in f["jugadores"]]
            assert set(roles) <= {"infractor", "defensa", "ofensiva", "balon"}
            assert roles.count("infractor") <= 1
            assert roles.count("balon") <= 1
            for j in f["jugadores"]:
                if j["rol"] == "balon":
                    assert j["nflId"] is None and j["numero"] is None
                elif j["rol"] == "infractor":
                    assert j["nflId"] == id_inf
                elif j["rol"] == "ofensiva":
                    assert 2000 <= j["nflId"] < 2010
                else:
                    assert j["nflId"] != id_inf and 1000 <= j["nflId"] < 1020
                assert j["x"] == round(j["x"], 2) and j["y"] == round(j["y"], 2)
        snap_frame = next(f for f in det["frames"] if f["t"] == 0)
        assert [j["rol"] for j in snap_frame["jugadores"]].count("infractor") == 1


# ---------------------------------------------------------------------------
# Property 4: Orden de la lista
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS_DATASET)
def test_p4_orden_lista(semilla, casos_aleatorios):
    """Feature: jugada-evidencia, Property 4: Orden de la lista"""
    _, todo = casos_aleatorios[semilla]
    lista = todo["jugadas"]
    llaves = [(-j["s_snap"], j["gameId"], j["playId"]) for j in lista]
    assert llaves == sorted(llaves)
    s = [j["s_snap"] for j in lista]
    assert all(a >= b for a, b in zip(s, s[1:]))
    for j in lista:  # cada resumen coincide con su detalle
        det = todo["detalles"][(j["gameId"], j["playId"])]
        assert {k: det[k] for k in j} == j


def test_ejemplo_sintetico(resultado_sintetico, esperado_sintetico):
    """Feature: jugada-evidencia, Properties 2-4 sobre el conjunto fijo con valores conocidos."""
    lista = resultado_sintetico["jugadas"]
    obtenido = [(j["gameId"], j["playId"], j["infractor"]["nflId"], j["s_snap"],
                 j["cruce_snap"], j["alineado"]) for j in lista]
    assert obtenido == esperado_sintetico["jugadas"]
    for clave, (snap, n_frames, linea) in esperado_sintetico["ventanas"].items():
        det = resultado_sintetico["detalles"][clave]
        ids = [f["frameId"] for f in det["frames"]]
        assert ids == list(range(max(1, snap - 15), min(n_frames, snap + 20) + 1))
        assert det["linea_golpeo_x"] == linea
    for clave in esperado_sintetico["sin_jugada"]:
        assert clave not in resultado_sintetico["detalles"]
    # infractor (101) sin fila en el cuadro 30 de G1-P10: velocidad.infractor = null
    det = resultado_sintetico["detalles"][(2021000001, 10)]
    assert det["velocidad"][-1] == {"t": 2.0, "infractor": None, "resto_linea": 0.25}
    ultimo = det["frames"][-1]
    assert "infractor" not in [j["rol"] for j in ultimo["jugadores"]]
    v0 = next(v for v in det["velocidad"] if v["t"] == 0)
    assert v0 == {"t": 0.0, "infractor": 2.5, "resto_linea": 0.25}


# ---------------------------------------------------------------------------
# resolver_data_dir: la profundidad de data/ depende de cómo se descomprimió
# ---------------------------------------------------------------------------
def _crear_data_dir(carpeta):
    carpeta.mkdir(parents=True)
    (carpeta / "plays.csv").write_text("gameId,playId\n", encoding="utf-8")
    (carpeta / "tracking").mkdir()
    return carpeta


def test_resolver_data_dir_un_nivel(tmp_path):
    """resolver_data_dir encuentra data/X/data/plays.csv."""
    raiz = tmp_path / "data"
    esperado = _crear_data_dir(raiz / "nfl-big-data-bowl-regional-event-data-main" / "data")
    assert resolver_data_dir(raiz) == esperado


def test_resolver_data_dir_carpeta_repetida(tmp_path):
    """resolver_data_dir encuentra data/X/X/data/plays.csv (zip con carpeta repetida)."""
    raiz = tmp_path / "data"
    nombre = "nfl-big-data-bowl-regional-event-data-main"
    esperado = _crear_data_dir(raiz / nombre / nombre / "data")
    assert resolver_data_dir(raiz) == esperado


def test_resolver_data_dir_en_la_raiz(tmp_path):
    """resolver_data_dir acepta plays.csv directamente en data/."""
    raiz = _crear_data_dir(tmp_path / "data")
    assert resolver_data_dir(raiz) == raiz


def test_resolver_data_dir_ignora_plays_sin_tracking(tmp_path):
    """Una carpeta con plays.csv pero sin tracking/ no es Data_Dir."""
    raiz = tmp_path / "data"
    (raiz / "a").mkdir(parents=True)
    (raiz / "a" / "plays.csv").write_text("gameId,playId\n", encoding="utf-8")
    esperado = _crear_data_dir(raiz / "b" / "data")
    assert resolver_data_dir(raiz) == esperado


def test_resolver_data_dir_ausente(tmp_path):
    """Sin plays.csv (o sin data/) se lanza DatosNoDisponibles."""
    raiz = tmp_path / "data"
    (raiz / "x" / "data" / "tracking").mkdir(parents=True)
    with pytest.raises(DatosNoDisponibles):
        resolver_data_dir(raiz)
    with pytest.raises(DatosNoDisponibles):
        resolver_data_dir(tmp_path / "no_existe")
