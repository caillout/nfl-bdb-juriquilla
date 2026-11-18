"""Narrador de jugadas con IA (Amazon Bedrock, modelos Amazon Nova).

La IA es opcional: si falla o no está disponible se devuelve una narración hecha
con plantilla, para que la app siempre muestre su hallazgo. Las credenciales no
se leen aquí: en AWS las pone el rol de la tarea y en local boto3 las toma del
entorno (cargado desde .env por backend/main.py).
"""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger("backend.narrador")

_cache: dict[tuple[int, int], dict] = {}
_candado = threading.Lock()

SISTEMA = (
    "Eres comentarista de una transmisión de la NFL en español de México: emocionado, claro y con ritmo de TV. "
    "Narra en 2 o 3 frases (máximo 70 palabras) el momento del snap de la jugada que te describen. "
    "Usa SOLO los datos que te doy: no inventes nombres, números, resultados ni contexto. "
    "Las velocidades están en yardas por segundo. Menciona a qué velocidad iba el infractor antes del snap contra el resto de su línea (casi quieta), y si viene el dato, remata contrastando con otra jugada parecida contra otro rival "
    "en la que el mismo jugador salió quieto y no hubo falta. "
    "Responde solo con la narración, sin títulos ni comillas."
)

_ORD = {1: "1er", 2: "2do", 3: "3er", 4: "4to"}


def _vel_en(velocidad: list[dict], t: float, campo: str):
    for p in velocidad:
        if abs(p["t"] - t) < 0.05:
            return p.get(campo)
    return None


def hechos(detalle: dict) -> dict:
    """Hechos calculados de la jugada (lo único que ve el modelo)."""
    vel = detalle.get("velocidad", [])
    t0 = min((p["t"] for p in vel), default=0.0)
    control = detalle.get("control")
    return {
        "infractor": detalle["infractor"]["nombre"],
        "defensa": detalle["equipo_defensa"],
        "ofensiva": detalle["equipo_ofensiva"],
        "cuarto": detalle["quarter"],
        "reloj": detalle["gameClock"],
        "situacion": f"{_ORD.get(detalle['down'], detalle['down'])} y {detalle['yardsToGo']}",
        "velocidad_en_snap": detalle["s_snap"],
        "segundos_antes_del_snap": abs(t0),
        "velocidad_infractor_antes": _vel_en(vel, t0, "infractor"),
        "velocidad_resto_linea_antes": _vel_en(vel, t0, "resto_linea"),
        "velocidad_resto_linea_en_snap": _vel_en(vel, 0.0, "resto_linea"),
        "misma_jugada_parecida_sin_offside": None if not control else {
            "rival": control["equipo_ofensiva"],
            "situacion": f"{_ORD.get(control['down'], control['down'])} y {control['yardsToGo']}",
            "velocidad_en_snap": control["s_snap"],
        },
    }


def _fmt(v) -> str:
    return "s/d" if v is None else f"{float(v):.1f}"


def plantilla(h: dict) -> str:
    texto = (
        f"¡{h['infractor']} se adelantó! En {h['situacion']}, {h['defensa']} contra {h['ofensiva']}, "
        f"ya iba a {_fmt(h['velocidad_infractor_antes'])} yardas por segundo "
        f"{_fmt(h['segundos_antes_del_snap'])} segundos antes del snap, mientras el resto de su línea estaba en "
        f"{_fmt(h['velocidad_resto_linea_antes'])}. Llegó al snap a {_fmt(h['velocidad_en_snap'])} yd/s: offside."
    )
    if h["misma_jugada_parecida_sin_offside"]:
        texto += (
            f" En una jugada parecida contra {h['misma_jugada_parecida_sin_offside']['rival']} salió quieto, a "
            f"{_fmt(h['misma_jugada_parecida_sin_offside']['velocidad_en_snap'])} yd/s, y no hubo falta."
        )
    return texto


def _llamar_bedrock(h: dict) -> str:
    import boto3  # dependencia del stack; se importa aquí para no frenar el arranque
    from botocore.config import Config

    region = os.environ.get("AWS_REGION", "us-east-1")
    modelo = os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")
    cliente = boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(read_timeout=25, connect_timeout=5, retries={"max_attempts": 1}),
    )
    datos = "\n".join(f"- {k}: {v}" for k, v in h.items())
    resp = cliente.converse(
        modelId=modelo,
        system=[{"text": SISTEMA}],
        messages=[{"role": "user", "content": [{"text": f"Datos de la jugada:\n{datos}"}]}],
        inferenceConfig={"maxTokens": 220, "temperature": 0.6},
    )
    texto = "".join(c.get("text", "") for c in resp["output"]["message"]["content"]).strip()
    if not texto:
        raise ValueError("respuesta vacía")
    return texto


def narrar(clave: tuple[int, int], detalle: dict) -> dict:
    """Narración de la jugada: {"texto", "fuente": "ia" | "plantilla"}. Se guarda en memoria."""
    with _candado:
        if clave in _cache:
            return _cache[clave]
    h = hechos(detalle)
    try:
        resultado = {"texto": _llamar_bedrock(h), "fuente": "ia"}
    except Exception as e:  # sin IA la app sigue funcionando
        logger.warning("Narración con IA no disponible (%s); se usa plantilla", type(e).__name__)
        return {"texto": plantilla(h), "fuente": "plantilla"}  # no se guarda: se reintenta la IA la próxima vez
    with _candado:
        _cache[clave] = resultado
    return resultado
