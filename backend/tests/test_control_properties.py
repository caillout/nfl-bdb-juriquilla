"""Pruebas de propiedades de jugada-control (Properties 1 a 3 del design.md),
control nulo sin candidata, segunda pasada ilegible y texto del criterio.

Sin Hypothesis: cada propiedad se parametriza sobre semillas de
numpy.random.default_rng, con una referencia de fuerza bruta.
"""
from __future__ import annotations

import logging
import shutil

import numpy as np
import pandas as pd
import pytest

from backend import offside_service
from backend.offside_service import (
    UMBRAL_QUIETO,
    VENTANA_ANTES,
    VENTANA_DESPUES,
    JugadaControl,
    JugadaDetalle,
    JugadaResumen,
    agregar_controles,
    calcular_todo,
    cargar_datos,
    construir_jugadas,
    elegir_controles,
    es_alineado,
    leer_ventanas,
    normalizar,
    preparar_alineados,
)
from backend.tests.sinteticos import (
    BX_CP,
    G1,
    G2,
    G3,
    G4,
    G5,
    G6,
    N_FRAMES_CP,
    SNAP_CP,
    escribir_data_dir,
    filas_jugada,
    jugada_plays,
)

OFS = "Defensive Offside"
SEMILLAS = list(range(40))
# Cada semilla del pipeline completo escribe un Data_Dir y corre calcular_todo (~0.3 s).
SEMILLAS_PIPELINE = list(range(2))
ORD = {1: "1er", 2: "2do", 3: "3er", 4: "4to"}


# ---------------------------------------------------------------------------
# Referencia de fuerza bruta (Glossary de jugada-control)
# ---------------------------------------------------------------------------
def control_referencia(ofensores: dict, rushers: dict, situacion: dict) -> dict:
    """{(g, p): ((g_c, p_c), distancia)} según el Glossary.

    `ofensores`: {(g, p): nflId con offside}. `rushers`: {(g, p, nflId): (cruce, s, offside)}
    solo de Rusher_Snap. `situacion`: {(g, p): (down, yardsToGo)}.
    """
    salida = {}
    for (g, p), nid in ofensores.items():
        d0, y0 = situacion[(g, p)]
        cands = []
        for (gc, pc, nc), (cruce, s, off) in rushers.items():
            if nc != nid or (gc, pc) == (g, p) or off != 0 or s > UMBRAL_QUIETO:
                continue
            if not (-1.5 <= cruce <= 0.5):
                continue
            d, y = situacion[(gc, pc)]
            dist = 10 * abs(d - d0) + abs(y - y0)
            cands.append(((dist, gc != g, s, gc, pc), (gc, pc), dist))
        if cands:
            _, clave, dist = min(cands)
            salida[(g, p)] = (clave, dist)
    return salida


# ---------------------------------------------------------------------------
# Generador de Rusher_Snap aleatorios para elegir_controles (sin E/S)
# ---------------------------------------------------------------------------
S_VALORES = [0.0, 0.05, 0.1, 0.25, 0.26, 0.5, 1.0, 2.5]
CRUCES = [-3.0, -1.51, -1.5, -1.0, -0.5, 0.0, 0.5, 0.51, 1.0]


def generar_rusher_snaps(rng):
    filas, plays, ofensores, rushers, situacion = [], [], {}, {}, {}
    juegos = [2030000001 + i for i in range(int(rng.integers(1, 4)))]
    for g in juegos:
        for p in range(1, int(rng.integers(2, 12)) + 1):
            down = int(rng.choice([0, 1, 2, 3, 4], p=[0.05, 0.3, 0.3, 0.25, 0.1]))
            ytg = int(rng.integers(1, 6))
            situacion[(g, p)] = (down, ytg)
            plays.append({"gameId": g, "playId": p, "down": down, "yardsToGo": ytg})
            presentes = [int(v) for v in rng.choice([1, 2, 3, 4], int(rng.integers(1, 4)), replace=False)]
            ofensor = int(rng.choice(presentes)) if rng.random() < 0.35 else None
            if ofensor is not None:
                ofensores[(g, p)] = ofensor
            for nid in presentes:
                s, cruce = float(rng.choice(S_VALORES)), float(rng.choice(CRUCES))
                off = int(nid == ofensor)
                rushers[(g, p, nid)] = (cruce, s, off)
                filas.append({"gameId": g, "playId": p, "nflId": nid, "s": s, "cruce": cruce,
                              "down": down, "offside": off})
    rs = pd.DataFrame(filas)
    rs["nflId"] = rs["nflId"].astype("Int64")
    alineados = rs.loc[es_alineado(rs["cruce"])].reset_index(drop=True)
    return rs, alineados, pd.DataFrame(plays), (ofensores, rushers, situacion)


# ---------------------------------------------------------------------------
# Property 1 y 2 sobre elegir_controles
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("semilla", SEMILLAS)
def test_p1_p2_elegir_controles(semilla):
    """Feature: jugada-control, Property 1: Validez y Property 2: Optimalidad y desempate"""
    rng = np.random.default_rng(semilla)
    rs, alineados, plays, (ofensores, rushers, situacion) = generar_rusher_snaps(rng)
    elegidos = elegir_controles(rs, alineados, plays)
    esperado = control_referencia(ofensores, rushers, situacion)

    assert set(elegidos) == set(esperado)
    for clave_of, e in elegidos.items():
        clave_c = e["clave"]
        nid = ofensores[clave_of]
        # Property 1: otra jugada, mismo nflId, Rusher_Alineado, sin offside y quieto
        assert clave_c != clave_of
        cruce, s, off = rushers[(clave_c[0], clave_c[1], nid)]
        assert -1.5 <= cruce <= 0.5 and off == 0 and s <= UMBRAL_QUIETO
        # Property 2: igual a la referencia (distancia mínima y desempates)
        assert (clave_c, e["distancia_situacion"]) == esperado[clave_of]
        assert isinstance(e["distancia_situacion"], int)
        # ninguna candidata con menor distancia
        d0, y0 = situacion[clave_of]
        for (g, p, n), (cr, sc, o) in rushers.items():
            if n == nid and (g, p) != clave_of and o == 0 and sc <= UMBRAL_QUIETO and -1.5 <= cr <= 0.5:
                d, y = situacion[(g, p)]
                assert 10 * abs(d - d0) + abs(y - y0) >= e["distancia_situacion"]
        # criterio: "mismo partido" solo si el control es del mismo partido
        assert ("mismo partido" in e["criterio"]) == (clave_c[0] == clave_of[0])


@pytest.mark.parametrize("semilla", SEMILLAS[:5])
def test_determinismo_elegir_controles(semilla):
    """Requirement 1.4: con los mismos datos (en otro orden de filas) la control es la misma."""
    rng = np.random.default_rng(semilla)
    rs, alineados, plays, _ = generar_rusher_snaps(rng)
    a = elegir_controles(rs, alineados, plays)
    b = elegir_controles(rs, alineados, plays)
    perm = np.random.default_rng(semilla + 1000)
    c = elegir_controles(
        rs.sample(frac=1, random_state=perm.integers(1 << 31)).reset_index(drop=True),
        alineados.sample(frac=1, random_state=perm.integers(1 << 31)).reset_index(drop=True),
        plays.sample(frac=1, random_state=perm.integers(1 << 31)).reset_index(drop=True),
    )
    assert a == b == c


def test_elegir_controles_vacios():
    """Sin Rusher_Snap, sin alineados o sin offsides no hay controles."""
    rs = pd.DataFrame({"gameId": [1], "playId": [1], "nflId": [7], "s": [0.0], "cruce": [0.0],
                       "down": [1], "offside": [0]})
    plays = pd.DataFrame({"gameId": [1], "playId": [1], "down": [1], "yardsToGo": [10]})
    assert elegir_controles(rs, rs, plays) == {}
    assert elegir_controles(rs.iloc[0:0], rs.iloc[0:0], plays) == {}


# ---------------------------------------------------------------------------
# Conjuntos fijos con valores calculados a mano
# ---------------------------------------------------------------------------
def _control_obtenido(det):
    c = det["control"]
    if c is None:
        return None
    return ((c["gameId"], c["playId"]), c["distancia_situacion"], c["criterio"])


def test_controles_conjunto_cp(resultado_cp, esperado_cp):
    """Ranking por Distancia_Situacion y los cuatro desempates (mismo partido, menor s,
    menor gameId, menor playId), frontera s = 0.25 y un infractor sin candidata."""
    detalles = resultado_cp["detalles"]
    assert set(detalles) == set(esperado_cp["controles"])
    for clave, (infractor, clave_c, dist, criterio) in esperado_cp["controles"].items():
        det = detalles[clave]
        assert det["infractor"]["nflId"] == infractor
        esperado = None if clave_c is None else (clave_c, dist, criterio)
        assert _control_obtenido(det) == esperado, clave


def test_controles_conjunto_fijo(resultado_sintetico, esperado_sintetico):
    """Controles del primer conjunto fijo (102 quieto en G1-P10)."""
    for clave, esperado in esperado_sintetico["controles"].items():
        assert _control_obtenido(resultado_sintetico["detalles"][clave]) == esperado, clave


def test_sin_candidata_control_null(resultado_cp):
    """Requirement 1.3: el infractor 405 no tiene candidata: control null y tiene_control false."""
    clave = (G3, 40)
    det = resultado_cp["detalles"][clave]
    assert det["infractor"]["nflId"] == 405
    assert det["control"] is None
    assert det["tiene_control"] is False
    resumen = next(j for j in resultado_cp["jugadas"] if (j["gameId"], j["playId"]) == clave)
    assert resumen["tiene_control"] is False
    JugadaDetalle.model_validate(det)
    assert JugadaDetalle.model_validate(det).control is None


@pytest.mark.parametrize("fixture", ["resultado_sintetico", "resultado_cp"])
def test_tiene_control_consistente(fixture, request):
    """tiene_control coincide en lista y detalle y equivale a control != null."""
    todo = request.getfixturevalue(fixture)
    for j in todo["jugadas"]:
        JugadaResumen.model_validate(j)
        det = todo["detalles"][(j["gameId"], j["playId"])]
        assert j["tiene_control"] is det["tiene_control"] is (det["control"] is not None)


# ---------------------------------------------------------------------------
# Property 3: formato del detalle de control
# ---------------------------------------------------------------------------
def verificar_formato_control(clave_of, det, snap_c, n_frames_c, linea_c=None):
    """Properties 2 y 3 de jugada-evidencia sobre `control`, más rol del infractor."""
    c = det["control"]
    JugadaControl.model_validate(c)
    JugadaDetalle.model_validate(det)
    id_inf = det["infractor"]["nflId"]
    assert c["infractor"] == det["infractor"]
    assert (c["gameId"], c["playId"]) != clave_of
    assert c["alineado"] is True and c["s_snap"] <= UMBRAL_QUIETO
    ids = [f["frameId"] for f in c["frames"]]
    assert ids == list(range(max(1, snap_c - VENTANA_ANTES), min(n_frames_c, snap_c + VENTANA_DESPUES) + 1))
    assert sum(1 for f in c["frames"] if f["t"] == 0) == 1
    for f in c["frames"]:
        assert f["t"] == pytest.approx((f["frameId"] - snap_c) / 10)
        roles = [j["rol"] for j in f["jugadores"]]
        assert set(roles) <= {"infractor", "defensa", "ofensiva", "balon"}
        assert roles.count("infractor") <= 1 and roles.count("balon") <= 1
        for j in f["jugadores"]:
            if j["rol"] == "infractor":
                assert j["nflId"] == id_inf
            elif j["rol"] != "balon":
                assert j["nflId"] != id_inf
    t0 = next(f for f in c["frames"] if f["t"] == 0)
    assert [j["rol"] for j in t0["jugadores"]].count("infractor") == 1
    assert [v["t"] for v in c["velocidad"]] == [f["t"] for f in c["frames"]]
    v0 = next(v for v in c["velocidad"] if v["t"] == 0)
    assert v0["infractor"] == c["s_snap"]
    if linea_c is not None:
        assert c["linea_golpeo_x"] == pytest.approx(linea_c, abs=1e-9)


def test_p3_formato_conjunto_cp(resultado_cp):
    """Feature: jugada-control, Property 3: Formato del detalle de control (conjunto fijo)"""
    for clave, det in resultado_cp["detalles"].items():
        if det["control"] is None:
            continue
        g_c = det["control"]["gameId"]
        if g_c == G6:  # jugadas de un solo cuadro
            verificar_formato_control(clave, det, 1, 1, BX_CP)
        else:
            linea = 120 - BX_CP if g_c == G4 else BX_CP  # G4 va a la izquierda
            verificar_formato_control(clave, det, SNAP_CP, N_FRAMES_CP, linea)
        # Resto_Linea: el relleno 499 (s 0.3) en los escenarios; nadie en G6
        if g_c != G6:
            assert all(v["resto_linea"] == 0.3 for v in det["control"]["velocidad"])


def test_p3_formato_conjunto_fijo(resultado_sintetico):
    """Property 3 en el primer conjunto fijo: control G1-P10 (snap 10 de 40 cuadros)."""
    for clave in [(G1, 20), (G2, 20)]:
        verificar_formato_control(clave, resultado_sintetico["detalles"][clave], 10, 40, 50.0)


def generar_data_control(rng, base):
    """Data_Dir aleatorio con un offside a lo más por jugada; devuelve metadatos."""
    tracking, plays, pff, players = {}, [], [], {}
    ofensores, rushers, situacion, cuadros = {}, {}, {}, {}
    for g in (2031000001, 2031000002):
        tracking[g] = []
        for p in range(1, int(rng.integers(4, 9)) + 1):
            n_frames = int(rng.integers(3, 40))
            snap = int(rng.integers(1, n_frames + 1))
            direccion = str(rng.choice(["left", "right"]))
            bx = round(float(rng.uniform(20, 100)), 2)
            down, ytg = int(rng.integers(1, 5)), int(rng.integers(1, 6))
            situacion[(g, p)] = (down, ytg)
            cuadros[(g, p)] = (snap, n_frames, round(120 - bx, 2) if direccion == "left" else bx)
            presentes = [int(v) for v in rng.choice([11, 12, 13], int(rng.integers(1, 4)), replace=False)]
            ofensor = int(rng.choice(presentes)) if rng.random() < 0.4 else None
            jugadores = []
            for nid in presentes:
                cruce = float(rng.choice([-3.0, -1.5, -1.0, -0.5, 0.5, 0.6]))
                s = float(rng.choice([0.0, 0.1, 0.25, 0.26, 0.5, 1.5, 3.0]))
                x = round(bx - cruce if direccion == "right" else bx + cruce, 2)
                jugadores.append({"nflId": nid, "team": "DEF", "numero": nid, "x": x, "y": 20.0 + nid, "s": s})
                rushers[(g, p, nid)] = (cruce, s, int(nid == ofensor))
                pff.append({"gameId": g, "playId": p, "nflId": nid, "pff_role": "Pass Rush",
                            "pff_hit": int(rng.integers(0, 2)), "pff_hurry": None, "pff_sack": None})
                players[nid] = f"Rusher {nid}"
            jugadores.append({"nflId": 21, "team": "OFF", "numero": 21,
                              "x": round(bx + (-1 if direccion == "right" else 1), 2), "y": 26.0, "s": 0.0})
            players[21] = "Ofensivo"
            tracking[g] += filas_jugada(g, p, direccion, n_frames, snap,
                                        str(rng.choice(["ball_snap", "autoevent_ballsnap"])), jugadores, bx)
            fila = jugada_plays(g, p, down, [(OFS, ofensor)] if ofensor else [])
            fila["yardsToGo"] = ytg
            plays.append(fila)
            if ofensor is not None:
                ofensores[(g, p)] = ofensor
    escribir_data_dir(base, tracking, plays, pff,
                      [{"nflId": k, "displayName": v} for k, v in players.items()])
    return ofensores, rushers, situacion, cuadros


@pytest.fixture(scope="module")
def casos_pipeline(tmp_path_factory):
    raiz = tmp_path_factory.mktemp("control_aleatorio")
    casos = {}
    for semilla in SEMILLAS_PIPELINE:
        rng = np.random.default_rng(semilla)
        base = raiz / f"s{semilla}"
        meta = generar_data_control(rng, base)
        casos[semilla] = (meta, calcular_todo(cargar_datos(base)))
    return casos


@pytest.mark.parametrize("semilla", SEMILLAS_PIPELINE)
def test_p1_p2_p3_pipeline(semilla, casos_pipeline):
    """Feature: jugada-control, Properties 1-3 de punta a punta (cargar_datos + calcular_todo)"""
    (ofensores, rushers, situacion, cuadros), todo = casos_pipeline[semilla]
    esperado = control_referencia(ofensores, rushers, situacion)
    assert set(todo["detalles"]) == set(ofensores)
    for clave, det in todo["detalles"].items():
        assert det["infractor"]["nflId"] == ofensores[clave]
        if clave not in esperado:
            assert det["control"] is None and det["tiene_control"] is False
            continue
        clave_c, dist = esperado[clave]
        c = det["control"]
        assert c is not None, clave
        assert ((c["gameId"], c["playId"]), c["distancia_situacion"]) == (clave_c, dist)
        snap_c, n_c, linea_c = cuadros[clave_c]
        verificar_formato_control(clave, det, snap_c, n_c, linea_c)
        assert c["s_snap"] == rushers[(clave_c[0], clave_c[1], ofensores[clave])][1]
        assert ("mismo partido" in c["criterio"]) == (clave_c[0] == clave[0])


# ---------------------------------------------------------------------------
# Texto del criterio
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fixture", ["resultado_sintetico", "resultado_cp"])
def test_criterio_texto(fixture, request):
    """criterio = "Mismo jugador[, mismo partido], <down> y <distancia>, quieto en el snap (<s> yd/s)"."""
    todo = request.getfixturevalue(fixture)
    vistos = set()
    for clave, det in todo["detalles"].items():
        c = det["control"]
        if c is None:
            continue
        mismo = c["gameId"] == clave[0]
        vistos.add(mismo)
        esperado = (f"Mismo jugador{', mismo partido' if mismo else ''}, {ORD[c['down']]} y {c['yardsToGo']}, "
                    f"quieto en el snap ({c['s_snap']:.2f} yd/s)")
        assert c["criterio"] == esperado
        assert ("mismo partido" in c["criterio"]) == mismo
    assert vistos == {True, False}  # ambos casos están cubiertos


# ---------------------------------------------------------------------------
# Segunda pasada: archivo ilegible, solo los partidos con control, sin data_dir
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def datos_cp(data_control_perfil):
    return cargar_datos(data_control_perfil)


def _piezas(datos):
    rs, alineados = preparar_alineados(datos)
    lista, detalles = construir_jugadas(datos, rs, alineados)
    return rs, alineados, lista, detalles


def test_segunda_pasada_ilegible(datos_cp, data_control_perfil, tmp_path, esperado_cp, caplog):
    """Requirement 3.4: si tracking_G5.csv no se puede leer en la segunda pasada, la jugada
    cuya control está en G5 (402 en G4-P10) queda con control null; las demás no cambian."""
    copia = tmp_path / "copia"
    (copia / "tracking").mkdir(parents=True)
    for g in (G3, G4, G6):  # la segunda pasada solo usa tracking/
        shutil.copy(data_control_perfil / "tracking" / f"tracking_{g}.csv", copia / "tracking")
    (copia / "tracking" / f"tracking_{G5}.csv").write_text("esto,no\nes,tracking\n", encoding="utf-8")
    datos = {**datos_cp, "data_dir": copia}
    rs, alineados, lista, detalles = _piezas(datos)
    with caplog.at_level(logging.WARNING, logger=offside_service.logger.name):
        agregar_controles(datos, rs, alineados, lista, detalles)  # no lanza
    assert str(G5) in caplog.text

    afectada = (G4, 10)
    assert detalles[afectada]["control"] is None
    assert detalles[afectada]["tiene_control"] is False
    assert next(j for j in lista if (j["gameId"], j["playId"]) == afectada)["tiene_control"] is False
    for clave, (_, clave_c, dist, criterio) in esperado_cp["controles"].items():
        if clave == afectada:
            continue
        esperado = None if clave_c is None else (clave_c, dist, criterio)
        assert _control_obtenido(detalles[clave]) == esperado, clave
    # la jugada con offside en G5 (403) conserva su detalle de la primera pasada
    assert detalles[(G5, 20)]["frames"]

    ventanas, fallidos = leer_ventanas(copia, {(G5, 10), (G3, 2)})
    assert fallidos == [G5]
    assert set(map(tuple, ventanas[["gameId", "playId"]].drop_duplicates().to_numpy())) == {(G3, 2)}


@pytest.mark.parametrize("modo", ["borrado", "vacio", "sin_columnas"])
def test_leer_ventanas_archivo_ilegible(modo, tmp_path, caplog):
    """leer_ventanas no lanza: un archivo ausente, vacío o sin columnas se registra en fallidos."""
    (tmp_path / "tracking").mkdir()
    ruta = tmp_path / "tracking" / f"tracking_{G5}.csv"
    if modo == "vacio":
        ruta.write_bytes(b"")
    elif modo == "sin_columnas":
        ruta.write_text("gameId,playId\n1,2\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger=offside_service.logger.name):
        ventanas, fallidos = leer_ventanas(tmp_path, {(G5, 10), (G5, 11)})
    assert fallidos == [G5]
    assert ventanas.empty
    assert f"gameId={G5}" in caplog.text


def test_segunda_pasada_solo_partidos_con_control(data_sintetica, monkeypatch):
    """Requirement 3.1-3.2: la segunda pasada lee solo los tracking de los partidos con
    Jugada_Control y conserva solo las ventanas de esas jugadas."""
    datos = cargar_datos(data_sintetica)
    rs, alineados, lista, detalles = _piezas(datos)
    leidos = []
    original = offside_service._leer_tracking

    def espia(ruta, claves=None):
        leidos.append((ruta.name, set(claves or ())))
        return original(ruta, claves)

    monkeypatch.setattr(offside_service, "_leer_tracking", espia)
    agregar_controles(datos, rs, alineados, lista, detalles)
    assert leidos == [(f"tracking_{G1}.csv", {(G1, 10)})]

    ventanas, fallidos = leer_ventanas(data_sintetica, {(G1, 10)})
    assert fallidos == []
    assert set(map(tuple, ventanas[["gameId", "playId"]].drop_duplicates().to_numpy())) == {(G1, 10)}


@pytest.mark.parametrize("quitar", [True, False])
def test_sin_data_dir_control_null(datos_cp, quitar):
    """Datos sin data_dir (en memoria): control null en todas las jugadas."""
    datos = {k: v for k, v in datos_cp.items() if k != "data_dir"} if quitar else {**datos_cp, "data_dir": None}
    rs, alineados, lista, detalles = _piezas(datos)
    agregar_controles(datos, rs, alineados, lista, detalles)
    assert detalles and all(d["control"] is None and d["tiene_control"] is False for d in detalles.values())
    assert all(j["tiene_control"] is False for j in lista)


# ---------------------------------------------------------------------------
# Bug: jugada con dos offsides ligados
# ---------------------------------------------------------------------------
G7 = 2021000007


def _data_doble_offside(base):
    """G7-P1 con offside de 407 (s 0.4) y de 408 (s 2.0): el Infractor es 408.
    407 está quieto en G7-P2 (donde 408 corre a 1.0) y 408 está quieto en G7-P3."""
    tracking, plays, pff = {G7: []}, [], []
    escenarios = [
        (1, 1, 10, [(407, 0.4), (408, 2.0)], [(OFS, 407), (OFS, 408)]),
        (2, 1, 10, [(407, 0.0), (408, 1.0)], []),
        (3, 2, 10, [(408, 0.0)], []),
    ]
    for p, down, ytg, jug, fouls in escenarios:
        jugadores = [{"nflId": n, "team": "DEF", "numero": n % 100, "x": 50.5, "y": 20.0 + n % 10, "s": s}
                     for n, s in jug]
        tracking[G7] += filas_jugada(G7, p, "right", 8, 4, "ball_snap", jugadores, 50.0)
        pff += [{"gameId": G7, "playId": p, "nflId": n, "pff_role": "Pass Rush"} for n, _ in jug]
        fila = jugada_plays(G7, p, down, fouls)
        fila["yardsToGo"] = ytg
        plays.append(fila)
    return escribir_data_dir(base, tracking, plays, pff,
                             [{"nflId": 407, "displayName": "Lento"}, {"nflId": 408, "displayName": "Rapido"}])


@pytest.mark.xfail(
    reason="BUG: elegir_controles (offside_service.py:807) toma el primer Rusher con offside de la "
           "jugada (drop_duplicates sin ordenar por s), pero construir_jugadas elige como Infractor al "
           "de mayor s; con dos offsides ligados la control se busca para otro jugador y "
           "agregar_controles la arma para el Infractor en una jugada donde no estaba quieto.",
    strict=True,
)
def test_control_con_dos_offsides_en_la_jugada(tmp_path):
    """Property 1 con dos Offside_Ligado en la misma jugada: la control es del Infractor (408)."""
    todo = calcular_todo(cargar_datos(_data_doble_offside(tmp_path / "doble")))
    det = todo["detalles"][(G7, 1)]
    assert det["infractor"]["nflId"] == 408
    c = det["control"]
    assert c is not None
    assert c["s_snap"] <= UMBRAL_QUIETO
    assert (c["gameId"], c["playId"]) == (G7, 3)
