"""API de la plantilla. Ejecuta: .venv/bin/uvicorn backend.main:app --reload"""
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path


def cargar_env():
    f = Path(__file__).resolve().parent.parent / ".env"
    if f.exists():
        for linea in f.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


cargar_env()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from backend.offside_service import (  # noqa: E402
    DatosNoDisponibles,
    EquiposResponse,
    JugadaDetalle,
    JugadaResumen,
    JugadorLista,
    OffsideResponse,
    PerfilJugador,
    calcular_todo,
    cargar_datos,
)

logger = logging.getLogger("backend")

RAIZ = Path(__file__).resolve().parent.parent
DIST = RAIZ / "dashboard" / "dist"

MENSAJE_CALCULANDO = "Calculando las métricas a partir del tracking. Intenta de nuevo en unos segundos."


def iniciar_estado(app: FastAPI) -> None:
    app.state.estado = "calculando"
    app.state.error = None
    app.state.resultado = None
    app.state.jugadas = None
    app.state.detalles = None
    app.state.jugadores = None
    app.state.perfiles = None
    app.state.equipos = None


def ejecutar_calculo(app: FastAPI, data_dir: Path | None = None) -> None:
    """Carga los datos y guarda el resultado en app.state (sin escribir a disco)."""
    try:
        todo = calcular_todo(cargar_datos(data_dir))
        app.state.resultado = todo["offside"]
        app.state.jugadas = todo["jugadas"]
        app.state.detalles = todo["detalles"]
        app.state.jugadores = todo["jugadores"]
        app.state.perfiles = todo["perfiles"]
        app.state.equipos = todo["equipos"]
        app.state.estado = "listo"
        logger.info("Métricas listas: %s jugadas con offside", len(todo["jugadas"]))
    except DatosNoDisponibles as e:
        app.state.error = str(e) or "Datos no disponibles."
        app.state.estado = "error"
        logger.error("Datos no disponibles: %s", app.state.error)
    except Exception as e:  # el servidor debe seguir vivo aunque falle el cálculo
        app.state.error = f"No se pudieron calcular las métricas: {type(e).__name__}"
        app.state.estado = "error"
        logger.exception("Error al calcular métricas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # El cálculo tarda ~15 s: se hace en segundo plano para que /health responda de inmediato.
    iniciar_estado(app)
    threading.Thread(target=ejecutar_calculo, args=(app,), daemon=True, name="calculo-offside").start()
    yield


app = FastAPI(title="Hackathon NFL UNAM", lifespan=lifespan)


def _exigir_listo() -> None:
    estado = getattr(app.state, "estado", "calculando")
    if estado == "listo":
        return
    if estado == "error":
        mensaje = getattr(app.state, "error", None) or "Datos no disponibles."
        raise HTTPException(status_code=503, detail={"estado": "error", "mensaje": mensaje})
    raise HTTPException(
        status_code=503,
        detail={"estado": "calculando", "mensaje": MENSAJE_CALCULANDO},
        headers={"Retry-After": "5"},
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/offside", response_model=OffsideResponse)
def offside() -> dict:
    _exigir_listo()
    return app.state.resultado


@app.get("/api/jugadas", response_model=list[JugadaResumen])
def jugadas() -> list[dict]:
    _exigir_listo()
    return app.state.jugadas


@app.get("/api/jugadas/{game_id}/{play_id}", response_model=JugadaDetalle)
def jugada(game_id: int, play_id: int) -> dict:
    _exigir_listo()
    detalle = (app.state.detalles or {}).get((game_id, play_id))
    if detalle is None:
        raise HTTPException(status_code=404, detail="No hay una jugada con offside con ese gameId y playId.")
    return detalle


@app.get("/api/jugadores", response_model=list[JugadorLista])
def jugadores() -> list[dict]:
    _exigir_listo()
    return app.state.jugadores


@app.get("/api/jugadores/{nfl_id}", response_model=PerfilJugador)
def perfil(nfl_id: int) -> dict:
    _exigir_listo()
    p = (app.state.perfiles or {}).get(nfl_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Ese jugador no tiene al menos 100 snaps alineados.")
    return p


@app.get("/api/equipos", response_model=EquiposResponse)
def equipos() -> dict:
    _exigir_listo()
    return app.state.equipos


# Siempre al final, para no tapar /health ni /api. Solo si existe el build.
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="dashboard")
