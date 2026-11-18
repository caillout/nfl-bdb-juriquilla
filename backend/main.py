"""API de la plantilla. Ejecuta: .venv/bin/uvicorn backend.main:app --reload"""
import logging
import os
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
    OffsideResponse,
    calcular_metricas,
    cargar_datos,
)

logger = logging.getLogger("backend")

RAIZ = Path(__file__).resolve().parent.parent
DIST = RAIZ / "dashboard" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.resultado = None
    app.state.error = None
    try:
        app.state.resultado = calcular_metricas(cargar_datos())
    except DatosNoDisponibles as e:
        app.state.error = str(e) or "Datos no disponibles."
        logger.error("Datos no disponibles: %s", app.state.error)
    except Exception as e:  # el servidor debe arrancar aunque falle el cálculo
        app.state.error = f"No se pudieron calcular las métricas: {type(e).__name__}"
        logger.exception("Error al calcular métricas")
    yield


app = FastAPI(title="Hackathon NFL UNAM", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/offside", response_model=OffsideResponse)
def offside() -> dict:
    resultado = getattr(app.state, "resultado", None)
    if resultado is None:
        detalle = getattr(app.state, "error", None) or "Datos aún no disponibles."
        raise HTTPException(status_code=503, detail=detalle)
    return resultado


# Siempre al final, para no tapar /health ni /api. Solo si existe el build.
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="dashboard")
