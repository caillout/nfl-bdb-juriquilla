"""Servicio de calculo para GET /api/offside.

Contiene constantes, la excepcion DatosNoDisponibles, los modelos Pydantic de
la respuesta y utilidades comunes. Las funciones de calculo se agregan en
tareas posteriores.
"""
from __future__ import annotations

import logging
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel

# Rangos de velocidad (pd.cut cerrado a la derecha)
RANGOS_ETIQUETAS = ["0-0.25", "0.25-0.5", "0.5-1", "1-2", ">2"]
RANGOS_BINS = [-0.01, 0.25, 0.5, 1, 2, 10]

UMBRAL_CLAVE = 0.5  # s > 0.5
UMBRAL_SCOUT = 1.0  # s >= 1.0
MIN_SNAPS_SCOUT = 100

CRUCE_MIN, CRUCE_MAX = -1.5, 0.5


class DatosNoDisponibles(Exception):
    """Falta un archivo requerido de data/ o no se puede leer."""


def nan_a_none(valor: Any) -> Any:
    """Convierte NaN (float, numpy o pandas NA) a None; deja otros valores igual."""
    if valor is None:
        return None
    try:
        if isinstance(valor, float) and math.isnan(valor):
            return None
        # numpy floats y pd.NA / NaT
        if valor != valor:  # NaN no es igual a si mismo
            return None
    except (TypeError, ValueError):
        # pd.NA lanza TypeError al evaluarse como bool
        try:
            import pandas as pd

            if pd.isna(valor):
                return None
        except (TypeError, ValueError):
            pass
    return valor


class Rango(BaseModel):
    rango: str
    rusher_snaps: int
    offsides: int
    offsides_por_1000: float | None
    pct_presion: float | None


class NumeroClave(BaseModel):
    x_pct_snaps: float | None
    y_pct_offsides: float | None
    umbral: str


class JugadorScout(BaseModel):
    nflId: int
    nombre: str
    rusher_snaps: int
    pct_movimiento: float
    pct_presion: float
    offsides: int


class Top10Scout(BaseModel):
    umbral: str
    jugadores: list[JugadorScout]


class PorDown(BaseModel):
    down: int
    rusher_snaps: int
    offsides: int
    pct_offsides: float | None


class Totales(BaseModel):
    rusher_snaps: int
    offsides: int
    juegos_omitidos: list[int]


class OffsideResponse(BaseModel):
    rangos: list[Rango]
    numero_clave: NumeroClave
    top10_scout: Top10Scout
    por_down: list[PorDown]
    totales: Totales
    nota_umbrales: str


# ---------------------------------------------------------------------------
# Funciones puras de calculo: snap, rushers y cruce
# ---------------------------------------------------------------------------
EVENTOS_SNAP = ("ball_snap", "autoevent_ballsnap")
ROL_RUSHER = "Pass Rush"


def frame_snap(tracking: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (gameId, playId) con el frameId del evento de snap.

    Las jugadas sin evento ball_snap/autoevent_ballsnap no aparecen.
    """
    cols = ["gameId", "playId", "frameId"]
    if tracking.empty or "event" not in tracking.columns:
        return pd.DataFrame(columns=cols).astype(
            {"gameId": "int64", "playId": "int64", "frameId": "int64"}
        )
    snaps = tracking.loc[tracking["event"].isin(EVENTOS_SNAP), cols]
    return (
        snaps.groupby(["gameId", "playId"], as_index=False)["frameId"]
        .min()
        .reset_index(drop=True)
    )


def rushers_en_snap(tracking_snap: pd.DataFrame, pff: pd.DataFrame) -> pd.DataFrame:
    """Rusher_Snap: rushers (pff_role == 'Pass Rush') con posicion en el Frame_Snap.

    `tracking_snap` trae solo las filas del Frame_Snap de cada jugada (jugadores
    y balon) con gameId, playId, nflId, team, x, s y playDirection.
    Se excluyen las jugadas sin fila `football` y los rushers sin posicion.
    Columnas: gameId, playId, nflId, x, s, bx, playDirection.
    """
    salida = ["gameId", "playId", "nflId", "x", "s", "bx", "playDirection"]
    vacio = pd.DataFrame(columns=salida)
    if tracking_snap.empty or pff.empty:
        return vacio

    balon = tracking_snap.loc[tracking_snap["team"] == "football", ["gameId", "playId", "x"]]
    balon = (
        balon.dropna(subset=["x"])
        .groupby(["gameId", "playId"], as_index=False)["x"]
        .first()
        .rename(columns={"x": "bx"})
    )

    rushers = pff.loc[pff["pff_role"] == ROL_RUSHER, ["gameId", "playId", "nflId"]]
    rushers = rushers.dropna(subset=["nflId"]).drop_duplicates()
    rushers["nflId"] = rushers["nflId"].astype("int64")

    jugadores = tracking_snap.loc[
        tracking_snap["nflId"].notna() & (tracking_snap["team"] != "football"),
        ["gameId", "playId", "nflId", "x", "s", "playDirection"],
    ].dropna(subset=["x"])
    jugadores = jugadores.assign(nflId=jugadores["nflId"].astype("int64"))
    jugadores = jugadores.drop_duplicates(subset=["gameId", "playId", "nflId"])

    res = rushers.merge(jugadores, on=["gameId", "playId", "nflId"], how="inner")
    res = res.merge(balon, on=["gameId", "playId"], how="inner")
    return res[salida].reset_index(drop=True)


def calcular_cruce(x, bx, play_direction):
    """Cruce = (x - bx) * signo; signo = -1 si 'right', +1 si 'left'.

    Acepta escalares o Series/arreglos (play_direction del mismo tipo).
    """
    if isinstance(play_direction, str):
        signo = -1.0 if play_direction == "right" else 1.0
    else:
        signo = np.where(np.asarray(play_direction) == "right", -1.0, 1.0)
        if isinstance(x, pd.Series):
            signo = pd.Series(signo, index=x.index)
    return (x - bx) * signo


def es_alineado(cruce):
    """True si -1.5 <= cruce <= 0.5 (extremos incluidos)."""
    return (cruce >= CRUCE_MIN) & (cruce <= CRUCE_MAX)


# ---------------------------------------------------------------------------
# Rango de velocidad, presion individual y vinculacion de offsides
# ---------------------------------------------------------------------------
FALTA_OFFSIDE = "Defensive Offside"


def rango_velocidad(s: pd.Series) -> pd.Series:
    """Rango_Velocidad con pd.cut cerrado a la derecha; `s` se usa sin recalcular."""
    return pd.cut(
        pd.Series(s),
        bins=RANGOS_BINS,
        labels=RANGOS_ETIQUETAS,
        right=True,
    )


def presion_individual(df: pd.DataFrame) -> pd.Series:
    """True si pff_hit + pff_hurry + pff_sack > 0 (vacios o columnas ausentes = 0)."""
    total = pd.Series(0.0, index=df.index)
    for col in ("pff_hit", "pff_hurry", "pff_sack"):
        if col in df.columns:
            total = total + pd.to_numeric(df[col], errors="coerce").fillna(0)
    return total > 0


def ligar_offsides(rusher_snaps: pd.DataFrame, plays: pd.DataFrame) -> pd.DataFrame:
    """Agrega la columna `offside` (0/1) a cada Rusher_Snap con un left join.

    Solo se revisan foulName1/foulNFLId1 y foulName2/foulNFLId2. Conserva el
    numero de filas de entrada y deja `nflId` como Int64.
    """
    res = rusher_snaps.copy()
    res["nflId"] = res["nflId"].astype("Int64")

    pares = []
    for n in ("1", "2"):
        nombre, ident = f"foulName{n}", f"foulNFLId{n}"
        if nombre not in plays.columns or ident not in plays.columns:
            continue
        sel = plays.loc[plays[nombre] == FALTA_OFFSIDE, ["gameId", "playId", ident]]
        sel = sel.rename(columns={ident: "nflId"})
        sel = sel.dropna(subset=["nflId"])
        pares.append(sel)

    if pares:
        ligados = pd.concat(pares, ignore_index=True)
        ligados["nflId"] = ligados["nflId"].astype("int64").astype("Int64")
        ligados = ligados.drop_duplicates(subset=["gameId", "playId", "nflId"])
        ligados["offside"] = 1
        res = res.merge(ligados, on=["gameId", "playId", "nflId"], how="left")
        res["offside"] = res["offside"].fillna(0).astype("int64")
    else:
        res["offside"] = 0
    return res


# ---------------------------------------------------------------------------
# Metricas agregadas sobre Rusher_Alineado
# `alineados`: una fila por Rusher_Alineado con columnas gameId, playId, nflId,
# s, down, presion (bool) y offside (0/1). `rango` se calcula si falta.
# ---------------------------------------------------------------------------
def _pct(parte: float, total: float) -> float | None:
    """parte / total * 100, o None si total == 0."""
    return None if total == 0 else float(parte) / float(total) * 100.0


def _con_rango_presion(alineados: pd.DataFrame) -> pd.DataFrame:
    df = alineados.copy()
    if "rango" not in df.columns:
        df["rango"] = rango_velocidad(df["s"]).values
    if "presion" not in df.columns:
        df["presion"] = presion_individual(df).values
    return df


def metricas_por_rango(alineados: pd.DataFrame) -> list[dict]:
    """Cinco entradas, una por Rango_Velocidad, en el orden de RANGOS_ETIQUETAS."""
    df = _con_rango_presion(alineados)
    salida = []
    for etiqueta in RANGOS_ETIQUETAS:
        sub = df[df["rango"].astype(object) == etiqueta]
        n = int(len(sub))
        ofs = int(sub["offside"].sum()) if n else 0
        pres = int(sub["presion"].astype(bool).sum()) if n else 0
        salida.append(
            {
                "rango": etiqueta,
                "rusher_snaps": n,
                "offsides": ofs,
                "offsides_por_1000": None if n == 0 else ofs / n * 1000.0,
                "pct_presion": _pct(pres, n),
            }
        )
    return salida


def metricas_por_down(alineados: pd.DataFrame) -> list[dict]:
    """Una entrada por down presente en `alineados` (denominador: sus rusher-snaps)."""
    df = alineados.dropna(subset=["down"])
    salida = []
    for down in sorted(df["down"].unique()):
        sub = df[df["down"] == down]
        n = int(len(sub))
        ofs = int(sub["offside"].sum())
        salida.append(
            {
                "down": int(down),
                "rusher_snaps": n,
                "offsides": ofs,
                "pct_offsides": _pct(ofs, n),
            }
        )
    return salida


def top10_scout(alineados: pd.DataFrame, players: pd.DataFrame) -> list[dict]:
    """Top 10 por % de Rusher_Alineado con s >= UMBRAL_SCOUT (min MIN_SNAPS_SCOUT)."""
    if alineados.empty:
        return []
    df = _con_rango_presion(alineados)
    df = df.assign(
        _mov=(df["s"] >= UMBRAL_SCOUT).astype(int),
        _pres=df["presion"].astype(bool).astype(int),
    )
    g = (
        df.groupby("nflId")
        .agg(
            rusher_snaps=("s", "size"),
            movimiento=("_mov", "sum"),
            presion=("_pres", "sum"),
            offsides=("offside", "sum"),
        )
        .reset_index()
    )
    g = g[g["rusher_snaps"] >= MIN_SNAPS_SCOUT].copy()
    if g.empty:
        return []
    g["pct_movimiento"] = g["movimiento"] / g["rusher_snaps"] * 100.0
    g["pct_presion"] = g["presion"] / g["rusher_snaps"] * 100.0
    g = g.sort_values(["pct_movimiento", "rusher_snaps", "nflId"], ascending=[False, False, True])
    g = g.head(10)

    nombres: dict[int, str] = {}
    if players is not None and not players.empty and "displayName" in players.columns:
        p = players.dropna(subset=["nflId"])
        nombres = {int(k): str(v) for k, v in zip(p["nflId"], p["displayName"])}

    return [
        {
            "nflId": int(r.nflId),
            "nombre": nombres.get(int(r.nflId), str(int(r.nflId))),
            "rusher_snaps": int(r.rusher_snaps),
            "pct_movimiento": float(r.pct_movimiento),
            "pct_presion": float(r.pct_presion),
            "offsides": int(r.offsides),
        }
        for r in g.itertuples(index=False)
    ]


def numero_clave(alineados: pd.DataFrame) -> dict:
    """X: % de alineados con s > 0.5. Y: % de los offsides ligados con s > 0.5."""
    n = int(len(alineados))
    umbral = "s > 0.5 yd/s"
    if n == 0:
        return {"x_pct_snaps": None, "y_pct_offsides": None, "umbral": umbral}
    rapido = alineados["s"] > UMBRAL_CLAVE
    total_of = int(alineados["offside"].sum())
    of_rapido = int(alineados.loc[rapido, "offside"].sum())
    return {
        "x_pct_snaps": _pct(int(rapido.sum()), n),
        "y_pct_offsides": _pct(of_rapido, total_of),
        "umbral": umbral,
    }


# ---------------------------------------------------------------------------
# Carga de datos (solo lectura) y ensamblado de la respuesta
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "nfl-big-data-bowl-regional-event-data-main"
    / "nfl-big-data-bowl-regional-event-data-main"
    / "data"
)

COLS_TRACKING = ["gameId", "playId", "frameId", "nflId", "team", "x", "s", "event", "playDirection"]
COLS_PFF = ["gameId", "playId", "nflId", "pff_role", "pff_hit", "pff_hurry", "pff_sack"]
COLS_PLAYS = [
    "gameId", "playId", "down",
    "foulName1", "foulNFLId1", "foulName2", "foulNFLId2",
]
COLS_PLAYERS = ["nflId", "displayName"]

NOTA_UMBRALES = (
    "El Número_Clave usa s > 0.5 yd/s y el Top_10_Scout usa s >= 1.0 yd/s "
    "por decisión deliberada."
)


def _leer_requerido(ruta: Path, columnas: list[str]) -> pd.DataFrame:
    """Lee un CSV requerido; DatosNoDisponibles si falta o no se puede leer."""
    if not ruta.is_file():
        logger.error("Archivo requerido no encontrado: %s", ruta.name)
        raise DatosNoDisponibles(f"Falta el archivo requerido: {ruta.name}")
    try:
        return pd.read_csv(ruta, usecols=lambda c: c in columnas)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de lectura
        logger.error("No se pudo leer %s: %s", ruta.name, type(exc).__name__)
        raise DatosNoDisponibles(f"No se pudo leer el archivo requerido: {ruta.name}") from exc


def _leer_tracking_snap(ruta: Path) -> pd.DataFrame:
    """Lee un tracking y conserva solo las filas del Frame_Snap de cada jugada."""
    df = pd.read_csv(ruta, usecols=lambda c: c in COLS_TRACKING)
    faltan = {"gameId", "playId", "frameId", "event", "team", "x"} - set(df.columns)
    if faltan:
        raise ValueError(f"columnas ausentes: {sorted(faltan)}")
    fs = frame_snap(df)
    return df.merge(fs, on=["gameId", "playId", "frameId"], how="inner")


def cargar_datos(data_dir: Path | None = None) -> dict:
    """Lee los CSV de `data_dir` (solo lectura, un juego de tracking a la vez).

    Devuelve {"tracking_snap", "pff", "plays", "players", "juegos_omitidos"}.
    Lanza DatosNoDisponibles si falta un CSV requerido o no hay tracking legible.
    """
    data_dir = Path(data_dir) if data_dir is not None else DATA_DIR

    pff = _leer_requerido(data_dir / "pffScoutingData.csv", COLS_PFF)
    plays = _leer_requerido(data_dir / "plays.csv", COLS_PLAYS)
    players = _leer_requerido(data_dir / "players.csv", COLS_PLAYERS)

    carpeta = data_dir / "tracking"
    archivos = sorted(carpeta.glob("tracking_*.csv")) if carpeta.is_dir() else []
    if not archivos:
        logger.error("No hay archivos de tracking en la carpeta de datos")
        raise DatosNoDisponibles("No se encontraron archivos tracking_<gameId>.csv")

    partes: list[pd.DataFrame] = []
    omitidos: list[int] = []
    for ruta in archivos:
        try:
            partes.append(_leer_tracking_snap(ruta))
        except Exception as exc:  # noqa: BLE001 - juego ilegible: se omite
            m = re.search(r"tracking_(\d+)", ruta.name)
            game_id = int(m.group(1)) if m else -1
            logger.warning(
                "Juego omitido gameId=%s (%s)", game_id, type(exc).__name__
            )
            omitidos.append(game_id)

    if not partes:
        logger.error("Ningun archivo de tracking se pudo leer")
        raise DatosNoDisponibles("Ningún archivo de tracking se pudo leer")

    return {
        "tracking_snap": pd.concat(partes, ignore_index=True),
        "pff": pff,
        "plays": plays,
        "players": players,
        "juegos_omitidos": sorted(omitidos),
    }


def preparar_alineados(datos: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (rusher_snaps, alineados) con down, presion y offside."""
    rs = rushers_en_snap(datos["tracking_snap"], datos["pff"])
    if rs.empty:
        vacio = rs.assign(cruce=[], down=[], presion=[], offside=[])
        return vacio, vacio
    rs = rs.assign(cruce=calcular_cruce(rs["x"], rs["bx"], rs["playDirection"]))

    pff = datos["pff"]
    pres = pff.loc[pff["pff_role"] == ROL_RUSHER].dropna(subset=["nflId"]).copy()
    pres["nflId"] = pres["nflId"].astype("int64")
    pres["presion"] = presion_individual(pres)
    pres = pres.groupby(["gameId", "playId", "nflId"], as_index=False)["presion"].max()

    rs = rs.merge(pres, on=["gameId", "playId", "nflId"], how="left")
    rs["presion"] = rs["presion"].fillna(False).astype(bool)

    plays = datos["plays"]
    downs = plays[["gameId", "playId", "down"]].drop_duplicates(["gameId", "playId"])
    rs = rs.merge(downs, on=["gameId", "playId"], how="left")
    rs = ligar_offsides(rs, plays)

    alineados = rs.loc[es_alineado(rs["cruce"])].reset_index(drop=True)
    alineados = alineados.assign(rango=rango_velocidad(alineados["s"]).values)
    return rs, alineados


def calcular_metricas(datos: dict) -> dict:
    """Arma la respuesta completa (compatible con OffsideResponse)."""
    _, alineados = preparar_alineados(datos)

    rangos = metricas_por_rango(alineados) if len(alineados) else [
        {"rango": e, "rusher_snaps": 0, "offsides": 0,
         "offsides_por_1000": None, "pct_presion": None}
        for e in RANGOS_ETIQUETAS
    ]
    por_down = metricas_por_down(alineados) if len(alineados) else []

    resultado = {
        "rangos": rangos,
        "numero_clave": numero_clave(alineados),
        "top10_scout": {
            "umbral": "s >= 1.0 yd/s",
            "jugadores": top10_scout(alineados, datos["players"]),
        },
        "por_down": por_down,
        "totales": {
            "rusher_snaps": int(len(alineados)),
            "offsides": int(alineados["offside"].sum()) if len(alineados) else 0,
            "juegos_omitidos": list(datos.get("juegos_omitidos", [])),
        },
        "nota_umbrales": NOTA_UMBRALES,
    }
    return _limpiar_nan(resultado)


def _limpiar_nan(obj: Any) -> Any:
    """Reemplaza NaN por None de forma recursiva (JSON valido)."""
    if isinstance(obj, dict):
        return {k: _limpiar_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_limpiar_nan(v) for v in obj]
    return nan_a_none(obj)
