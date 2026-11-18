"""Pruebas de ejemplo de la API con TestClient.

Se usa TestClient(app) sin `with` para que el lifespan NO arranque el cálculo
con los datos reales; el estado de app.state se fija en cada prueba.
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import Mount

from backend.main import app, ejecutar_calculo, iniciar_estado
from backend.offside_service import (
    EquipoDefensa,
    EquipoOfensiva,
    EquiposResponse,
    JugadaControl,
    JugadaDetalle,
    JugadaResumen,
    JugadorLista,
    OffsideResponse,
    PerfilJugador,
)
from backend.tests.sinteticos import construir_data_sintetica

RUTAS_DATOS = ["/api/offside", "/api/jugadas", "/api/jugadas/2021000001/10",
               "/api/jugadores", "/api/jugadores/301", "/api/equipos"]
MENSAJE_404_JUGADOR = "Ese jugador no tiene al menos 100 snaps alineados."


@pytest.fixture
def cliente():
    """Cliente con app.state en 'calculando'; restaura el estado al terminar."""
    previo = dict(app.state._state)
    iniciar_estado(app)
    yield TestClient(app)
    app.state._state.clear()
    app.state._state.update(previo)


def _estado_calculado(data_dir) -> dict:
    """Corre ejecutar_calculo una vez y devuelve una copia de app.state."""
    previo = dict(app.state._state)
    iniciar_estado(app)
    ejecutar_calculo(app, data_dir=data_dir)
    assert app.state.estado == "listo", app.state.error
    estado = dict(app.state._state)
    app.state._state.clear()
    app.state._state.update(previo)
    return estado


@pytest.fixture(scope="module")
def estado_sintetico(data_sintetica) -> dict:
    return _estado_calculado(data_sintetica)


@pytest.fixture(scope="module")
def estado_cp(data_control_perfil) -> dict:
    return _estado_calculado(data_control_perfil)


@pytest.fixture
def cliente_listo(cliente, estado_sintetico):
    """Cliente con el resultado de ejecutar_calculo sobre el primer conjunto fijo
    (calculado una vez por módulo y restaurado en cada prueba)."""
    app.state._state.update(estado_sintetico)
    return cliente


@pytest.fixture
def cliente_cp(cliente, estado_cp):
    """Cliente con el resultado de ejecutar_calculo sobre el conjunto de control y perfiles."""
    app.state._state.update(estado_cp)
    return cliente


# ---------------------------------------------------------------------------
# /health y estados 503
# ---------------------------------------------------------------------------
def test_health_ok(cliente):
    """GET /health responde {"status": "ok"} aun mientras se calcula."""
    assert app.state.estado == "calculando"
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize("ruta", RUTAS_DATOS)
def test_503_mientras_calcula(cliente, ruta):
    """Mientras el cálculo está en curso: 503, estado 'calculando' y Retry-After."""
    r = cliente.get(ruta)
    assert r.status_code == 503
    detalle = r.json()["detail"]
    assert detalle["estado"] == "calculando"
    assert isinstance(detalle["mensaje"], str) and detalle["mensaje"]
    assert "retry-after" in {k.lower() for k in r.headers}
    assert int(r.headers["Retry-After"]) > 0


def test_503_sin_estado_inicial(cliente):
    """Sin estado (antes del lifespan) también se responde 'calculando'."""
    app.state._state.clear()
    r = cliente.get("/api/offside")
    assert r.status_code == 503
    assert r.json()["detail"]["estado"] == "calculando"


@pytest.fixture
def dir_sin_plays(tmp_path):
    base = construir_data_sintetica(tmp_path / "sin_plays")
    (base / "plays.csv").unlink()
    return base


@pytest.mark.parametrize("ruta", RUTAS_DATOS)
def test_503_error_sin_plays(cliente, dir_sin_plays, ruta):
    """Si falta plays.csv: 503 con estado 'error' y mensaje descriptivo; /health sigue ok."""
    ejecutar_calculo(app, data_dir=dir_sin_plays)
    assert app.state.estado == "error"
    r = cliente.get(ruta)
    assert r.status_code == 503
    detalle = r.json()["detail"]
    assert detalle["estado"] == "error"
    assert "plays.csv" in detalle["mensaje"]
    assert "AWS_" not in detalle["mensaje"]
    assert cliente.get("/health").json() == {"status": "ok"}


def test_503_error_sin_tracking_legible(cliente, tmp_path):
    """Si ningún tracking se puede leer: 503 con estado 'error'."""
    base = construir_data_sintetica(tmp_path / "corrupto")
    for f in (base / "tracking").glob("*.csv"):
        f.write_text("esto,no\nes,tracking\n", encoding="utf-8")
    ejecutar_calculo(app, data_dir=base)
    r = cliente.get("/api/offside")
    assert r.status_code == 503
    assert r.json()["detail"]["estado"] == "error"


def test_tracking_corrupto_se_omite(cliente, tmp_path, esperado_sintetico):
    """Un tracking_<gameId>.csv ilegible se omite y aparece en juegos_omitidos."""
    base = construir_data_sintetica(tmp_path / "con_corrupto")
    (base / "tracking" / "tracking_2021000099.csv").write_text("esto,no\nes,tracking\n", encoding="utf-8")
    ejecutar_calculo(app, data_dir=base)
    r = cliente.get("/api/offside")
    assert r.status_code == 200
    totales = r.json()["totales"]
    assert totales["juegos_omitidos"] == [2021000099]
    assert totales["rusher_snaps"] == esperado_sintetico["totales"]["rusher_snaps"]


# ---------------------------------------------------------------------------
# 200 con datos sintéticos
# ---------------------------------------------------------------------------
def test_offside_200(cliente_listo, esperado_sintetico):
    """GET /api/offside: 200, cuerpo válido según OffsideResponse y valores conocidos."""
    r = cliente_listo.get("/api/offside")
    assert r.status_code == 200
    cuerpo = r.json()
    OffsideResponse.model_validate(cuerpo)

    rangos = [(x["rango"], x["rusher_snaps"], x["offsides"], x["offsides_por_1000"], x["pct_presion"])
              for x in cuerpo["rangos"]]
    assert rangos == esperado_sintetico["rangos"]
    por_down = [(d["down"], d["rusher_snaps"], d["offsides"], d["offsides_por_1000"], d["pct_del_total"])
                for d in cuerpo["por_down"]]
    assert por_down == esperado_sintetico["por_down"]
    assert cuerpo["totales"]["sin_down_valido"] == esperado_sintetico["sin_down_valido"]
    assert cuerpo["totales"]["rusher_snaps"] == esperado_sintetico["totales"]["rusher_snaps"]
    assert cuerpo["totales"]["offsides"] == esperado_sintetico["totales"]["offsides"]
    assert cuerpo["totales"]["juegos_omitidos"] == []
    assert cuerpo["numero_clave"]["umbral"] == "s > 0.5 yd/s"
    assert cuerpo["numero_clave"]["x_pct_snaps"] == pytest.approx(esperado_sintetico["x_pct_snaps"])
    assert cuerpo["numero_clave"]["y_pct_offsides"] == pytest.approx(esperado_sintetico["y_pct_offsides"])
    assert cuerpo["top10_scout"]["umbral"] == "s >= 1.0 yd/s"
    assert cuerpo["top10_scout"]["jugadores"] == []  # nadie llega a 100 Rusher_Alineado
    assert "s > 0.5" in cuerpo["nota_umbrales"] and "s >= 1.0" in cuerpo["nota_umbrales"]


def test_jugadas_200(cliente_listo, esperado_sintetico):
    """GET /api/jugadas: 200, lista válida y ordenada por s_snap descendente."""
    r = cliente_listo.get("/api/jugadas")
    assert r.status_code == 200
    lista = r.json()
    for j in lista:
        JugadaResumen.model_validate(j)
    obtenido = [(j["gameId"], j["playId"], j["infractor"]["nflId"], j["s_snap"],
                 j["cruce_snap"], j["alineado"]) for j in lista]
    assert obtenido == esperado_sintetico["jugadas"]
    primera = lista[1]
    assert primera["infractor"]["nombre"] == "Rusher Uno"
    assert primera["equipo_defensa"] == "DEF" and primera["equipo_ofensiva"] == "OFF"
    assert primera["down"] == 1 and primera["quarter"] == 1 and primera["yardsToGo"] == 10
    assert primera["gameClock"] == "15:00"
    assert primera["descripcion"] == "Jugada 2021000001-10"
    assert [j["tiene_control"] for j in lista] == [
        esperado_sintetico["controles"][(j["gameId"], j["playId"])] is not None for j in lista]
    assert all("control" not in j for j in lista)  # la lista no trae el detalle de la control


def test_jugada_detalle_200(cliente_listo, esperado_sintetico):
    """GET /api/jugadas/{gameId}/{playId}: 200 y cuerpo válido según JugadaDetalle."""
    for (g, p), (snap, n_frames, linea) in esperado_sintetico["ventanas"].items():
        r = cliente_listo.get(f"/api/jugadas/{g}/{p}")
        assert r.status_code == 200
        det = r.json()
        JugadaDetalle.model_validate(det)
        assert (det["gameId"], det["playId"]) == (g, p)
        assert det["linea_golpeo_x"] == linea
        ids = [f["frameId"] for f in det["frames"]]
        assert ids == list(range(max(1, snap - 15), min(n_frames, snap + 20) + 1))
        assert [f["t"] for f in det["frames"] if f["t"] == 0] == [0.0]
        assert len(det["velocidad"]) == len(det["frames"])
        for f in det["frames"]:
            roles = [j["rol"] for j in f["jugadores"]]
            assert roles.count("balon") == 1
            assert roles.count("infractor") <= 1
        # jugada control (spec jugada-control)
        esperado = esperado_sintetico["controles"][(g, p)]
        assert det["tiene_control"] is (esperado is not None)
        if esperado is None:
            assert det["control"] is None
        else:
            c = det["control"]
            JugadaControl.model_validate(c)
            assert ((c["gameId"], c["playId"]), c["distancia_situacion"], c["criterio"]) == esperado
            assert c["infractor"] == det["infractor"]


@pytest.mark.parametrize("indice", range(5))
def test_jugada_404(cliente_listo, esperado_sintetico, indice):
    """Una jugada sin offside (o inexistente) responde 404 con mensaje en español."""
    g, p = esperado_sintetico["sin_jugada"][indice]
    r = cliente_listo.get(f"/api/jugadas/{g}/{p}")
    assert r.status_code == 404
    assert r.json()["detail"] == "No hay una jugada con offside con ese gameId y playId."


# ---------------------------------------------------------------------------
# Jugada control, perfiles y equipos (conjunto de control y perfiles)
# ---------------------------------------------------------------------------
def test_jugada_detalle_con_y_sin_control(cliente_cp, esperado_cp):
    """GET /api/jugadas/{gameId}/{playId}: `control` con el formato de JugadaControl o null."""
    lista = cliente_cp.get("/api/jugadas").json()
    assert {(j["gameId"], j["playId"]) for j in lista} == set(esperado_cp["controles"])
    for j in lista:
        clave = (j["gameId"], j["playId"])
        infractor, clave_c, dist, criterio = esperado_cp["controles"][clave]
        r = cliente_cp.get(f"/api/jugadas/{clave[0]}/{clave[1]}")
        assert r.status_code == 200
        det = r.json()
        JugadaDetalle.model_validate(det)
        assert det["infractor"]["nflId"] == infractor
        assert j["tiene_control"] is det["tiene_control"] is (clave_c is not None)
        if clave_c is None:
            assert det["control"] is None
            continue
        c = det["control"]
        JugadaControl.model_validate(c)
        assert ((c["gameId"], c["playId"]), c["distancia_situacion"], c["criterio"]) == (clave_c, dist, criterio)
        assert c["frames"] and c["velocidad"]
        assert sum(1 for f in c["frames"] if f["t"] == 0) == 1


def test_jugadores_200(cliente_cp, esperado_cp):
    """GET /api/jugadores: 200, esquema JugadorLista y orden con desempates."""
    r = cliente_cp.get("/api/jugadores")
    assert r.status_code == 200
    lista = r.json()
    for j in lista:
        JugadorLista.model_validate(j)
        assert set(j) == set(JugadorLista.model_fields)
    assert [(j["nflId"], j["nombre"], j["rusher_snaps"], j["pct_anticipa"]) for j in lista] == esperado_cp["jugadores"]
    j301 = next(j for j in lista if j["nflId"] == 301)
    assert (j301["equipo"], j301["posicion"], j301["numero"], j301["offsides"]) == ("TB", "OLB", 55, 2)
    assert j301["pct_presion"] == pytest.approx(20.0)


def test_jugadores_vacio_sin_elegibles(cliente_listo):
    """En el primer conjunto fijo nadie llega a 100 snaps: lista vacía y 404 en el perfil."""
    r = cliente_listo.get("/api/jugadores")
    assert r.status_code == 200 and r.json() == []
    r = cliente_listo.get("/api/jugadores/101")
    assert r.status_code == 404
    assert r.json()["detail"] == MENSAJE_404_JUGADOR


def test_perfil_200(cliente_cp, esperado_cp):
    """GET /api/jugadores/{nflId}: 200 con ficha, stats, distribucion y jugadas_offside."""
    for nid, ficha in esperado_cp["fichas"].items():
        r = cliente_cp.get(f"/api/jugadores/{nid}")
        assert r.status_code == 200
        p = r.json()
        PerfilJugador.model_validate(p)
        assert set(p) == {"nflId", "ficha", "stats", "distribucion", "jugadas_offside"}
        assert p["nflId"] == nid
        assert p["ficha"] == ficha
        assert [d["rango"] for d in p["distribucion"]] == ["0-0.25", "0.25-0.5", "0.5-1", "1-2", ">2"]
    p = cliente_cp.get("/api/jugadores/301").json()
    st = p["stats"]
    assert (st["rusher_snaps"], st["offsides"], st["percentil_anticipacion"]) == (120, 2, 75.0)
    assert st["anticipando"] == {"snaps": 30, "pct_presion": pytest.approx(20.0)}
    assert st["sin_anticipar"] == {"snaps": 90, "pct_presion": pytest.approx(20.0)}
    assert p["jugadas_offside"] == esperado_cp["jugadas_offside_301"]
    assert p["ficha"]["edad"] == 28
    assert cliente_cp.get("/api/jugadores/302").json()["ficha"]["edad"] is None  # birthDate vacío


@pytest.mark.parametrize("nfl_id", [304, 401, 405, 499, 999999, 0])
def test_perfil_404(cliente_cp, nfl_id):
    """Un nflId que no es Jugador_Elegible responde 404 con mensaje en español."""
    r = cliente_cp.get(f"/api/jugadores/{nfl_id}")
    assert r.status_code == 404
    assert r.json()["detail"] == MENSAJE_404_JUGADOR


def test_perfil_id_invalido_422(cliente_cp):
    """Un nflId que no es entero no llega a la ruta (validación de FastAPI)."""
    assert cliente_cp.get("/api/jugadores/abc").status_code == 422


def test_equipos_200(cliente_cp):
    """GET /api/equipos: 200, esquema EquiposResponse y conservación contra /api/offside."""
    r = cliente_cp.get("/api/equipos")
    assert r.status_code == 200
    eq = r.json()
    EquiposResponse.model_validate(eq)
    assert set(eq) == {"defensas", "ofensivas", "nota"}
    for d in eq["defensas"]:
        EquipoDefensa.model_validate(d)
        assert set(d) == set(EquipoDefensa.model_fields)
    for o in eq["ofensivas"]:
        EquipoOfensiva.model_validate(o)
        assert set(o) == set(EquipoOfensiva.model_fields)
    assert [d["equipo"] for d in eq["defensas"]] == ["KC", "TB", "NYG"]
    assert [o["equipo"] for o in eq["ofensivas"]] == ["DAL", "BUF", "NE"]
    assert isinstance(eq["nota"], str) and eq["nota"]
    tot = cliente_cp.get("/api/offside").json()["totales"]
    assert sum(d["rusher_snaps"] for d in eq["defensas"]) == tot["rusher_snaps"]
    assert sum(o["rusher_snaps_rival"] for o in eq["ofensivas"]) == tot["rusher_snaps"]
    assert sum(d["offsides"] for d in eq["defensas"]) == tot["offsides"]
    assert sum(o["offsides_provocados"] for o in eq["ofensivas"]) == tot["offsides"]


# ---------------------------------------------------------------------------
# Contrato de rutas
# ---------------------------------------------------------------------------
def test_rutas_bajo_api():
    """Toda ruta de la API está bajo /api, salvo /health y el montaje estático."""
    rutas_api = [r for r in app.routes if isinstance(r, APIRoute)]
    assert rutas_api, "no hay rutas registradas"
    for r in rutas_api:
        assert r.path == "/health" or r.path.startswith("/api/"), r.path
    assert any(r.path == "/health" for r in rutas_api)
    for r in app.routes:
        if isinstance(r, Mount):
            assert r.path in ("", "/")  # montaje de dashboard/dist
            assert r is app.routes[-1]  # al final, para no tapar /health ni /api
