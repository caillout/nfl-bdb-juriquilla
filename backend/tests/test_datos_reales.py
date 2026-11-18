"""Verificación contra los datos reales de data/ (solo lectura, ~30 s).

Se omite si no se encuentra Data_Dir. Ejecutar solo estas pruebas:
    .venv\\Scripts\\python.exe -m pytest backend/tests -m datos_reales -q
"""
from __future__ import annotations

import pytest

from backend.offside_service import (
    RANGOS_ETIQUETAS,
    DatosNoDisponibles,
    EquiposResponse,
    JugadaControl,
    JugadaDetalle,
    JugadaResumen,
    JugadorLista,
    OffsideResponse,
    PerfilJugador,
    calcular_todo,
    cargar_datos,
    resolver_data_dir,
)

pytestmark = pytest.mark.datos_reales


@pytest.fixture(scope="module")
def reales() -> dict:
    """calcular_todo(cargar_datos()) una sola vez para todo el módulo."""
    try:
        resolver_data_dir()
    except DatosNoDisponibles as e:
        pytest.skip(f"Datos reales no disponibles: {e}")
    return calcular_todo(cargar_datos())


def test_esquema(reales):
    """La respuesta y las jugadas cumplen los modelos Pydantic."""
    OffsideResponse.model_validate(reales["offside"])
    for j in reales["jugadas"]:
        JugadaResumen.model_validate(j)
    for d in reales["detalles"].values():
        JugadaDetalle.model_validate(d)


def test_totales(reales):
    """Totales de Rusher_Alineado, offsides y alineados sin down válido."""
    t = reales["offside"]["totales"]
    assert t["rusher_snaps"] == 30116
    assert t["offsides"] == 44
    assert t["sin_down_valido"] == {"rusher_snaps": 129, "offsides": 1}


def test_rangos(reales):
    """Métricas por Rango_Velocidad."""
    rangos = reales["offside"]["rangos"]
    assert [(r["rango"], r["rusher_snaps"], r["offsides"]) for r in rangos] == [
        ("0-0.25", 20594, 13),
        ("0.25-0.5", 6389, 3),
        ("0.5-1", 2691, 16),
        ("1-2", 403, 9),
        (">2", 39, 3),
    ]
    assert [round(r["pct_presion"], 1) for r in rangos] == [10.7, 11.8, 13.6, 18.9, 20.5]
    assert [round(r["offsides_por_1000"], 2) for r in rangos] == [0.63, 0.47, 5.95, 22.33, 76.92]


def test_por_down(reales):
    """Cuatro downs con sus Rusher_Alineado y offsides."""
    por_down = reales["offside"]["por_down"]
    assert [d["down"] for d in por_down] == [1, 2, 3, 4]
    assert [d["offsides"] for d in por_down] == [8, 15, 19, 1]
    assert [d["rusher_snaps"] for d in por_down] == [10970, 9911, 8279, 827]
    assert sum(d["pct_del_total"] for d in por_down) == pytest.approx(100.0)


def test_top10_scout(reales):
    """Top_10_Scout en orden."""
    jug = reales["offside"]["top10_scout"]["jugadores"]
    assert len(jug) == 10
    assert (jug[0]["nflId"], jug[0]["nombre"], jug[0]["rusher_snaps"]) == (41915, "Shaquil Barrett", 199)
    assert (jug[9]["nflId"], jug[9]["nombre"]) == (42365, "Bud Dupree")
    assert [j["nombre"] for j in jug] == [
        "Shaquil Barrett", "Matt Judon", "Joey Bosa", "Randy Gregory", "Lorenzo Carter",
        "Leonard Floyd", "Cameron Jordan", "Jerry Hughes", "Azeez Ojulari", "Bud Dupree",
    ]
    assert all(j["rusher_snaps"] >= 100 for j in jug)


def test_numero_clave(reales):
    """Número_Clave: X% de los snaps -> Y% de los offsides."""
    nc = reales["offside"]["numero_clave"]
    assert round(nc["y_pct_offsides"], 1) == 63.6
    assert round(nc["x_pct_snaps"], 1) == 10.4


def test_jugadas(reales):
    """Lista de Jugada_Offside y primera jugada."""
    lista = reales["jugadas"]
    assert len(lista) == 48
    assert sum(j["alineado"] for j in lista) == 44
    primera = lista[0]
    assert (primera["gameId"], primera["playId"]) == (2021091206, 98)
    assert primera["infractor"]["nflId"] == 44818
    assert primera["s_snap"] == 3.72
    s = [j["s_snap"] for j in lista]
    assert all(a >= b for a, b in zip(s, s[1:]))


def test_detalles(reales):
    """Cada detalle tiene cuadros, un único t == 0 y a lo más un infractor y un balón por cuadro."""
    assert set(reales["detalles"]) == {(j["gameId"], j["playId"]) for j in reales["jugadas"]}
    for clave, det in reales["detalles"].items():
        assert det["frames"], clave
        assert sum(1 for f in det["frames"] if f["t"] == 0) == 1, clave
        ids = [f["frameId"] for f in det["frames"]]
        assert all(a < b for a, b in zip(ids, ids[1:])), clave
        for f in det["frames"]:
            roles = [j["rol"] for j in f["jugadores"]]
            assert roles.count("infractor") <= 1, (clave, f["frameId"])
            assert roles.count("balon") <= 1, (clave, f["frameId"])


# ---------------------------------------------------------------------------
# jugada-control, perfil-jugador y equipos
# ---------------------------------------------------------------------------
def test_controles(reales):
    """Las 48 Jugada_Offside tienen control y cada control cumple las Properties 1 y 3."""
    detalles = reales["detalles"]
    con_control = [d for d in detalles.values() if d["control"] is not None]
    assert len(con_control) == len(detalles) == 48
    assert all(j["tiene_control"] for j in reales["jugadas"])
    for clave, det in detalles.items():
        c = det["control"]
        JugadaControl.model_validate(c)
        assert det["tiene_control"] is True
        assert c["infractor"] == det["infractor"], clave
        assert (c["gameId"], c["playId"]) != clave
        assert c["alineado"] is True and c["s_snap"] <= 0.25, clave
        assert c["frames"], clave
        assert sum(1 for f in c["frames"] if f["t"] == 0) == 1, clave
        t0 = next(f for f in c["frames"] if f["t"] == 0)
        assert [j["rol"] for j in t0["jugadores"]].count("infractor") == 1, clave
        for f in c["frames"]:
            roles = [j["rol"] for j in f["jugadores"]]
            assert roles.count("infractor") <= 1 and roles.count("balon") <= 1, (clave, f["frameId"])
        assert ("mismo partido" in c["criterio"]) == (c["gameId"] == clave[0]), clave


def test_control_primera_jugada(reales):
    """Control de (2021091206, 98): mismo jugador en (2021101711, 126), 3er y 9, quieto."""
    c = reales["detalles"][(2021091206, 98)]["control"]
    assert (c["gameId"], c["playId"]) == (2021101711, 126)
    assert c["distancia_situacion"] == 0
    assert c["criterio"] == "Mismo jugador, 3er y 9, quieto en el snap (0.02 yd/s)"
    assert c["infractor"]["nflId"] == 44818


def test_jugadores(reales):
    """130 Jugador_Elegible; los 10 primeros son el Top_10_Scout."""
    lista = reales["jugadores"]
    assert len(lista) == 130
    for j in lista:
        JugadorLista.model_validate(j)
        assert j["rusher_snaps"] >= 100
    llaves = [(-j["pct_anticipa"], -j["rusher_snaps"], j["nflId"]) for j in lista]
    assert llaves == sorted(llaves)
    top = reales["offside"]["top10_scout"]["jugadores"]
    assert [j["nombre"] for j in lista[:10]] == [t["nombre"] for t in top]
    assert [j["nflId"] for j in lista[:10]] == [t["nflId"] for t in top]
    assert set(reales["perfiles"]) == {j["nflId"] for j in lista}


def test_perfil_barrett(reales):
    """Perfil de Shaquil Barrett (41915)."""
    p = reales["perfiles"][41915]
    PerfilJugador.model_validate(p)
    assert p["ficha"] == {
        "nombre": "Shaquil Barrett", "posicion": "OLB", "equipo": "TB", "numero": 58,
        "estatura": "6-2", "peso": 250, "edad": 28, "universidad": "Colorado State",
    }
    assert p["stats"]["rusher_snaps"] == 199
    assert p["stats"]["anticipando"]["snaps"] == 16
    assert p["stats"]["percentil_anticipacion"] == 100.0


def test_perfiles_consistencia(reales):
    """Properties 2 y 3 de perfil-jugador sobre todos los perfiles reales."""
    for nid, p in reales["perfiles"].items():
        st = p["stats"]
        assert st["anticipando"]["snaps"] + st["sin_anticipar"]["snaps"] == st["rusher_snaps"], nid
        assert st["pct_anticipa"] == pytest.approx(st["anticipando"]["snaps"] / st["rusher_snaps"] * 100), nid
        assert 0 < st["percentil_anticipacion"] <= 100, nid
        assert [d["rango"] for d in p["distribucion"]] == RANGOS_ETIQUETAS
        assert sum(d["pct_jugador"] for d in p["distribucion"]) == pytest.approx(100.0)
        assert sum(d["pct_liga"] for d in p["distribucion"]) == pytest.approx(100.0)
        for j in p["jugadas_offside"]:
            assert reales["detalles"][(j["gameId"], j["playId"])]["infractor"]["nflId"] == nid


def test_equipos(reales):
    """32 defensas y 32 ofensivas; TB y KC primeros; conservación contra los totales."""
    eq = reales["equipos"]
    EquiposResponse.model_validate(eq)
    d, o = eq["defensas"], eq["ofensivas"]
    assert len(d) == 32 and len(o) == 32
    assert d[0]["equipo"] == "TB"
    assert o[0]["equipo"] == "KC" and o[0]["offsides_provocados"] == 9
    assert sum(x["rusher_snaps"] for x in d) == 30116
    assert sum(x["offsides"] for x in d) == 44
    assert sum(x["rusher_snaps_rival"] for x in o) == 30116
    assert sum(x["offsides_provocados"] for x in o) == 44
    llaves = [(-x["pct_anticipa"], x["equipo"]) for x in d]
    assert llaves == sorted(llaves)
    llaves = [(-x["offsides_por_1000"], -x["pct_anticipa_rival"], x["equipo"]) for x in o]
    assert llaves == sorted(llaves)
