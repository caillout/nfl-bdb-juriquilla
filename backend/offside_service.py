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
    offsides_por_1000: float | None
    pct_del_total: float | None


class SinDownValido(BaseModel):
    rusher_snaps: int
    offsides: int


class Totales(BaseModel):
    rusher_snaps: int
    offsides: int
    juegos_omitidos: list[int]
    sin_down_valido: SinDownValido


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


DECIMALES_CRUCE = 2  # misma precision que x en el tracking


def calcular_cruce(x, bx, play_direction):
    """Cruce = round((x - bx) * signo, 2) en float64; signo = -1 si 'right', +1 si 'left'.

    Se redondea para que los valores exactamente en -1.5 o 0.5 no dependan de
    errores de punto flotante. Acepta escalares o Series/arreglos.
    """
    if isinstance(play_direction, str):
        signo = -1.0 if play_direction == "right" else 1.0
        return round((float(x) - float(bx)) * signo, DECIMALES_CRUCE)
    signo = np.where(np.asarray(play_direction) == "right", -1.0, 1.0)
    if isinstance(x, pd.Series):
        signo = pd.Series(signo, index=x.index)
        return ((x.astype("float64") - bx.astype("float64")) * signo).round(DECIMALES_CRUCE)
    return np.round((np.asarray(x, dtype="float64") - np.asarray(bx, dtype="float64")) * signo, DECIMALES_CRUCE)


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


DOWNS_VALIDOS = (1, 2, 3, 4)


def metricas_por_down(alineados: pd.DataFrame) -> tuple[list[dict], dict]:
    """Cuatro entradas (downs 1-4) con tasa por 1,000 y % del total, y el resumen
    de los alineados sin down valido (por ejemplo down = 0 en los datos)."""
    if alineados.empty or "down" not in alineados.columns:
        downs = pd.Series(dtype="float64")
        offs = pd.Series(dtype="int64")
    else:
        downs = pd.to_numeric(alineados["down"], errors="coerce")
        offs = alineados["offside"]
    valido = downs.isin(DOWNS_VALIDOS)
    total_validos = int(offs[valido].sum())

    salida = []
    for down in DOWNS_VALIDOS:
        sel = downs == down
        n = int(sel.sum())
        ofs = int(offs[sel].sum())
        salida.append(
            {
                "down": down,
                "rusher_snaps": n,
                "offsides": ofs,
                "offsides_por_1000": None if n == 0 else ofs / n * 1000.0,
                "pct_del_total": _pct(ofs, total_validos),
            }
        )
    sin_down = {"rusher_snaps": int((~valido).sum()), "offsides": int(offs[~valido].sum())}
    return salida, sin_down


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

DATA_RAIZ = Path(__file__).resolve().parent.parent / "data"
MAX_NIVELES_DATA = 4


def resolver_data_dir(raiz: Path | None = None) -> Path:
    """Primera carpeta dentro de `raiz` (incluida) con plays.csv y tracking/.

    La profundidad depende de como se descomprimio el zip, por eso se busca en
    lugar de fijarla. Orden: menos profunda primero y luego alfabetico.
    """
    raiz = Path(raiz) if raiz is not None else DATA_RAIZ
    if not raiz.is_dir():
        raise DatosNoDisponibles("No existe la carpeta data/ en la raiz del proyecto")
    candidatos = []
    for plays in raiz.rglob("plays.csv"):
        carpeta = plays.parent
        niveles = len(carpeta.relative_to(raiz).parts)
        if niveles <= MAX_NIVELES_DATA and (carpeta / "tracking").is_dir():
            candidatos.append((niveles, str(carpeta).lower(), carpeta))
    if not candidatos:
        raise DatosNoDisponibles("No se encontro plays.csv con una carpeta tracking/ dentro de data/")
    return sorted(candidatos)[0][2]


COLS_TRACKING = ["gameId", "playId", "frameId", "nflId", "team", "x", "y", "s",
                 "jerseyNumber", "event", "playDirection"]
COLS_PFF = ["gameId", "playId", "nflId", "pff_role", "pff_hit", "pff_hurry", "pff_sack"]
COLS_PLAYS = [
    "gameId", "playId", "down", "quarter", "yardsToGo", "gameClock",
    "possessionTeam", "defensiveTeam", "playDescription",
    "foulName1", "foulNFLId1", "foulName2", "foulNFLId2",
]
COLS_PLAYERS = ["nflId", "displayName", "height", "weight", "birthDate", "collegeName", "officialPosition"]

# Ventana de cuadros alrededor del snap para el visor de jugadas
VENTANA_ANTES, VENTANA_DESPUES = 15, 20

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


def claves_offside(plays: pd.DataFrame) -> set[tuple[int, int]]:
    """(gameId, playId) con Defensive Offside en foulName1 o foulName2."""
    mascara = pd.Series(False, index=plays.index)
    for n in ("1", "2"):
        col = f"foulName{n}"
        if col in plays.columns:
            mascara |= plays[col] == FALTA_OFFSIDE
    sel = plays.loc[mascara, ["gameId", "playId"]]
    return {(int(g), int(p)) for g, p in zip(sel["gameId"], sel["playId"])}


def _leer_tracking(ruta: Path, claves: set[tuple[int, int]] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Una sola lectura del tracking: filas del Frame_Snap de cada jugada y filas
    de la Ventana (snap-15 a snap+20) de las jugadas en `claves`."""
    df = pd.read_csv(ruta, usecols=lambda c: c in COLS_TRACKING)
    faltan = {"gameId", "playId", "frameId", "event", "team", "x"} - set(df.columns)
    if faltan:
        raise ValueError(f"columnas ausentes: {sorted(faltan)}")
    fs = frame_snap(df)
    snap_rows = df.merge(fs, on=["gameId", "playId", "frameId"], how="inner")

    ventana = df.iloc[0:0]
    if claves:
        llaves = pd.MultiIndex.from_frame(df[["gameId", "playId"]].astype("int64"))
        sel = llaves.isin(list(claves))
        if sel.any():
            sub = df.loc[sel].merge(fs.rename(columns={"frameId": "frame_snap"}), on=["gameId", "playId"])
            rel = sub["frameId"] - sub["frame_snap"]
            ventana = sub.loc[(rel >= -VENTANA_ANTES) & (rel <= VENTANA_DESPUES)]
    return snap_rows, ventana


def _leer_tracking_snap(ruta: Path) -> pd.DataFrame:
    """Compatibilidad: solo las filas del Frame_Snap."""
    return _leer_tracking(ruta)[0]


def cargar_datos(data_dir: Path | None = None) -> dict:
    """Lee los CSV de `data_dir` (solo lectura, un juego de tracking a la vez).

    Devuelve {"tracking_snap", "tracking_ventana", "pff", "plays", "players",
    "juegos_omitidos"}. Si `data_dir` es None se busca con resolver_data_dir().
    Lanza DatosNoDisponibles si falta un CSV requerido o no hay tracking legible.
    """
    data_dir = Path(data_dir) if data_dir is not None else resolver_data_dir()

    pff = _leer_requerido(data_dir / "pffScoutingData.csv", COLS_PFF)
    plays = _leer_requerido(data_dir / "plays.csv", COLS_PLAYS)
    players = _leer_requerido(data_dir / "players.csv", COLS_PLAYERS)

    carpeta = data_dir / "tracking"
    archivos = sorted(carpeta.glob("tracking_*.csv")) if carpeta.is_dir() else []
    if not archivos:
        logger.error("No hay archivos de tracking en la carpeta de datos")
        raise DatosNoDisponibles("No se encontraron archivos tracking_<gameId>.csv")

    claves = claves_offside(plays)
    partes: list[pd.DataFrame] = []
    ventanas: list[pd.DataFrame] = []
    omitidos: list[int] = []
    for ruta in archivos:
        try:
            snap_rows, ventana = _leer_tracking(ruta, claves)
            partes.append(snap_rows)
            if not ventana.empty:
                ventanas.append(ventana)
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
        "tracking_ventana": pd.concat(ventanas, ignore_index=True) if ventanas else pd.DataFrame(),
        "pff": pff,
        "plays": plays,
        "players": players,
        "juegos_omitidos": sorted(omitidos),
        "data_dir": data_dir,
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


def calcular_metricas(datos: dict, preparados: tuple[pd.DataFrame, pd.DataFrame] | None = None) -> dict:
    """Arma la respuesta completa (compatible con OffsideResponse)."""
    _, alineados = preparados if preparados is not None else preparar_alineados(datos)

    rangos = metricas_por_rango(alineados) if len(alineados) else [
        {"rango": e, "rusher_snaps": 0, "offsides": 0,
         "offsides_por_1000": None, "pct_presion": None}
        for e in RANGOS_ETIQUETAS
    ]
    por_down, sin_down = metricas_por_down(alineados)

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
            "sin_down_valido": sin_down,
        },
        "nota_umbrales": NOTA_UMBRALES,
    }
    return _limpiar_nan(resultado)


# ---------------------------------------------------------------------------
# Visor de jugadas con offside (spec jugada-evidencia)
# ---------------------------------------------------------------------------
LARGO_CANCHA, ANCHO_CANCHA = 120.0, 53.3


class JugadorFrame(BaseModel):
    nflId: int | None
    x: float
    y: float
    s: float | None
    numero: int | None
    rol: str


class Frame(BaseModel):
    frameId: int
    t: float
    jugadores: list[JugadorFrame]


class PuntoVelocidad(BaseModel):
    t: float
    infractor: float | None
    resto_linea: float | None


class Infractor(BaseModel):
    nflId: int
    nombre: str


class JugadaResumen(BaseModel):
    gameId: int
    playId: int
    infractor: Infractor
    equipo_defensa: str
    equipo_ofensiva: str
    quarter: int
    down: int
    yardsToGo: int
    gameClock: str
    s_snap: float
    cruce_snap: float
    alineado: bool
    descripcion: str
    tiene_control: bool = False


class JugadaControl(JugadaResumen):
    linea_golpeo_x: float
    frames: list[Frame]
    velocidad: list[PuntoVelocidad]
    distancia_situacion: int
    criterio: str


class JugadaDetalle(JugadaResumen):
    linea_golpeo_x: float
    frames: list[Frame]
    velocidad: list[PuntoVelocidad]
    control: JugadaControl | None = None


def normalizar(x, y, play_direction):
    """Coordenadas con la ofensiva avanzando a la derecha (si 'left' se gira 180°)."""
    if isinstance(play_direction, str):
        if play_direction == "left":
            return LARGO_CANCHA - x, ANCHO_CANCHA - y
        return x, y
    izq = np.asarray(play_direction) == "left"
    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    return np.where(izq, LARGO_CANCHA - x, x), np.where(izq, ANCHO_CANCHA - y, y)


def _num(v, nd: int = 2) -> float | None:
    v = nan_a_none(v)
    return None if v is None else round(float(v), nd)


def _entero(v) -> int | None:
    v = nan_a_none(v)
    return None if v is None else int(v)


def _detalle_jugada(clave: tuple[int, int], id_resaltado: int, defensa: str, g: pd.DataFrame | None,
                    resto: set[int], bx_snap, direccion_snap) -> dict:
    """linea_golpeo_x, frames y velocidad de una jugada, resaltando a `id_resaltado`."""
    frames, velocidad = [], []
    linea = None
    if g is not None and not g.empty:
        g = g.sort_values("frameId")
        direccion = g["playDirection"].dropna()
        direccion = str(direccion.iloc[0]) if len(direccion) else "right"
        xs, ys = normalizar(g["x"].to_numpy(), g["y"].to_numpy(), direccion)
        g = g.assign(xn=xs, yn=ys)
        snap = int(g["frame_snap"].iloc[0])
        for fid, f in g.groupby("frameId", sort=True):
            t = round((int(fid) - snap) / 10.0, 1)
            jugadores = []
            for j in f.itertuples(index=False):
                es_balon = j.team == "football"
                nid = None if es_balon else _entero(j.nflId)
                if es_balon:
                    rol = "balon"
                    if int(fid) == snap:
                        linea = round(float(j.xn), 2)
                elif nid == id_resaltado:
                    rol = "infractor"
                elif j.team == defensa:
                    rol = "defensa"
                else:
                    rol = "ofensiva"
                jugadores.append({
                    "nflId": nid, "x": round(float(j.xn), 2), "y": round(float(j.yn), 2),
                    "s": _num(j.s), "numero": None if es_balon else _entero(getattr(j, "jerseyNumber", None)),
                    "rol": rol,
                })
            frames.append({"frameId": int(fid), "t": t, "jugadores": jugadores})
            s_inf = f.loc[f["nflId"] == id_resaltado, "s"]
            s_resto = f.loc[f["nflId"].isin(list(resto)), "s"]
            velocidad.append({
                "t": t,
                "infractor": _num(s_inf.iloc[0]) if len(s_inf) else None,
                "resto_linea": _num(s_resto.mean()) if len(s_resto) else None,
            })
    if linea is None:
        if bx_snap is not None and nan_a_none(bx_snap) is not None:
            linea = round(float(normalizar(float(bx_snap), 0.0, str(direccion_snap))[0]), 2)
        else:
            linea = 60.0
    return {"linea_golpeo_x": linea, "frames": frames, "velocidad": velocidad}


def _nombres(players: pd.DataFrame | None) -> dict[int, str]:
    if players is None or players.empty or "displayName" not in players.columns:
        return {}
    p = players.dropna(subset=["nflId"])
    return {int(k): str(v) for k, v in zip(p["nflId"], p["displayName"])}


def _resumen(clave, id_inf, nombres, pl, s, cruce) -> dict:
    return {
        "gameId": clave[0], "playId": clave[1],
        "infractor": {"nflId": id_inf, "nombre": nombres.get(id_inf, str(id_inf))},
        "equipo_defensa": str(pl.get("defensiveTeam", "")),
        "equipo_ofensiva": str(pl.get("possessionTeam", "")),
        "quarter": _entero(pl.get("quarter")) or 0,
        "down": _entero(pl.get("down")) or 0,
        "yardsToGo": _entero(pl.get("yardsToGo")) or 0,
        "gameClock": str(nan_a_none(pl.get("gameClock")) or ""),
        "s_snap": _num(s) or 0.0,
        "cruce_snap": _num(cruce) or 0.0,
        "alineado": bool(es_alineado(cruce)),
        "descripcion": str(nan_a_none(pl.get("playDescription")) or ""),
    }


def _alineados_por_jugada(alineados: pd.DataFrame) -> dict[tuple[int, int], set[int]]:
    if alineados.empty:
        return {}
    return {(int(k[0]), int(k[1])): set(int(n) for n in g["nflId"])
            for k, g in alineados.groupby(["gameId", "playId"])}


def _grupos_ventana(vent: pd.DataFrame | None) -> dict[tuple[int, int], pd.DataFrame]:
    if vent is None or vent.empty:
        return {}
    return {(int(k[0]), int(k[1])): g for k, g in vent.groupby(["gameId", "playId"])}


def construir_jugadas(datos: dict, rusher_snaps: pd.DataFrame, alineados: pd.DataFrame) -> tuple[list[dict], dict]:
    """Resúmenes ordenados por s_snap desc y detalles {(gameId, playId): detalle} (sin control)."""
    if rusher_snaps.empty or "offside" not in rusher_snaps.columns:
        return [], {}
    plays = datos["plays"].drop_duplicates(["gameId", "playId"]).set_index(["gameId", "playId"])
    nombres = _nombres(datos.get("players"))
    grupos = _grupos_ventana(datos.get("tracking_ventana"))
    alin = _alineados_por_jugada(alineados)

    inf = (rusher_snaps.loc[rusher_snaps["offside"] == 1]
           .sort_values(["s", "gameId", "playId"], ascending=[False, True, True])
           .drop_duplicates(["gameId", "playId"]))

    lista, detalles = [], {}
    for r in inf.itertuples(index=False):
        clave = (int(r.gameId), int(r.playId))
        if clave not in plays.index:
            continue
        pl = plays.loc[clave]
        id_inf = int(r.nflId)
        resumen = _resumen(clave, id_inf, nombres, pl, r.s, r.cruce)
        lista.append(resumen)
        cuerpo = _detalle_jugada(clave, id_inf, resumen["equipo_defensa"], grupos.get(clave),
                                 alin.get(clave, set()) - {id_inf}, getattr(r, "bx", None), r.playDirection)
        detalles[clave] = {**resumen, **cuerpo}
    return lista, detalles


# ---------------------------------------------------------------------------
# Jugada control (spec jugada-control)
# ---------------------------------------------------------------------------
UMBRAL_QUIETO = 0.25
_ORD = {1: "1er", 2: "2do", 3: "3er", 4: "4to"}


def elegir_controles(rusher_snaps: pd.DataFrame, alineados: pd.DataFrame, plays: pd.DataFrame) -> dict:
    """{(g, p) offside: {"clave": (g_c, p_c), "distancia_situacion", "criterio", "s"}}."""
    if rusher_snaps.empty or alineados.empty or "offside" not in rusher_snaps.columns:
        return {}
    ytg = plays.drop_duplicates(["gameId", "playId"])[["gameId", "playId", "yardsToGo"]]
    inf = rusher_snaps.loc[rusher_snaps["offside"] == 1, ["gameId", "playId", "nflId"]].drop_duplicates(["gameId", "playId"])
    inf = inf.merge(plays.drop_duplicates(["gameId", "playId"])[["gameId", "playId", "down", "yardsToGo"]],
                    on=["gameId", "playId"], how="left")
    cand = alineados.loc[(alineados["offside"] == 0) & (alineados["s"] <= UMBRAL_QUIETO),
                         ["gameId", "playId", "nflId", "s", "down"]]
    cand = cand.merge(ytg, on=["gameId", "playId"], how="left")

    salida = {}
    for r in inf.itertuples(index=False):
        c = cand.loc[(cand["nflId"] == r.nflId) & ~((cand["gameId"] == r.gameId) & (cand["playId"] == r.playId))]
        if c.empty:
            continue
        d0 = pd.to_numeric(pd.Series([r.down]), errors="coerce").fillna(0).iloc[0]
        y0 = pd.to_numeric(pd.Series([r.yardsToGo]), errors="coerce").fillna(0).iloc[0]
        c = c.assign(
            dist=(10 * (pd.to_numeric(c["down"], errors="coerce").fillna(0) - d0).abs()
                  + (pd.to_numeric(c["yardsToGo"], errors="coerce").fillna(0) - y0).abs()).astype(int),
            otro_partido=(c["gameId"] != r.gameId).astype(int),
        )
        m = c.sort_values(["dist", "otro_partido", "s", "gameId", "playId"]).iloc[0]
        mismo = int(m["otro_partido"]) == 0
        down_c = _entero(m["down"]) or 0
        criterio = (f"Mismo jugador{', mismo partido' if mismo else ''}, "
                    f"{_ORD.get(down_c, str(down_c))} y {_entero(m['yardsToGo']) or 0}, "
                    f"quieto en el snap ({float(m['s']):.2f} yd/s)")
        salida[(int(r.gameId), int(r.playId))] = {
            "clave": (int(m["gameId"]), int(m["playId"])),
            "distancia_situacion": int(m["dist"]),
            "criterio": criterio,
        }
    return salida


def leer_ventanas(data_dir: Path, claves: set[tuple[int, int]]) -> tuple[pd.DataFrame, list[int]]:
    """Segunda pasada: solo los tracking de los partidos de `claves`."""
    partes, fallidos = [], []
    for game_id in sorted({g for g, _ in claves}):
        ruta = Path(data_dir) / "tracking" / f"tracking_{game_id}.csv"
        try:
            _, ventana = _leer_tracking(ruta, {k for k in claves if k[0] == game_id})
            if not ventana.empty:
                partes.append(ventana)
        except Exception as exc:  # noqa: BLE001 - se omite ese partido
            logger.warning("Control omitido gameId=%s (%s)", game_id, type(exc).__name__)
            fallidos.append(game_id)
    return (pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()), fallidos


def agregar_controles(datos: dict, rusher_snaps: pd.DataFrame, alineados: pd.DataFrame,
                      lista: list[dict], detalles: dict) -> None:
    """Agrega `control` a cada detalle y `tiene_control` a la lista (modifica en sitio)."""
    for j in lista:
        j["tiene_control"] = False
    for d in detalles.values():
        d["tiene_control"] = False
        d["control"] = None
    data_dir = datos.get("data_dir")
    if data_dir is None or not detalles:
        return
    elegidos = elegir_controles(rusher_snaps, alineados, datos["plays"])
    if not elegidos:
        return
    ventanas, _ = leer_ventanas(data_dir, {e["clave"] for e in elegidos.values()})
    grupos = _grupos_ventana(ventanas)
    plays = datos["plays"].drop_duplicates(["gameId", "playId"]).set_index(["gameId", "playId"])
    nombres = _nombres(datos.get("players"))
    alin = _alineados_por_jugada(alineados)
    rs_idx = rusher_snaps.set_index(["gameId", "playId", "nflId"])
    por_clave = {(j["gameId"], j["playId"]): j for j in lista}

    for clave_of, e in elegidos.items():
        det = detalles.get(clave_of)
        clave_c = e["clave"]
        if det is None or clave_c not in grupos or clave_c not in plays.index:
            continue
        id_inf = det["infractor"]["nflId"]
        try:
            r = rs_idx.loc[(clave_c[0], clave_c[1], id_inf)]
        except KeyError:
            continue
        if isinstance(r, pd.DataFrame):
            r = r.iloc[0]
        resumen = _resumen(clave_c, id_inf, nombres, plays.loc[clave_c], r["s"], r["cruce"])
        cuerpo = _detalle_jugada(clave_c, id_inf, resumen["equipo_defensa"], grupos[clave_c],
                                 alin.get(clave_c, set()) - {id_inf}, r.get("bx"), r.get("playDirection"))
        det["control"] = {**resumen, **cuerpo,
                          "distancia_situacion": e["distancia_situacion"], "criterio": e["criterio"]}
        det["tiene_control"] = True
        if clave_of in por_clave:
            por_clave[clave_of]["tiene_control"] = True


# ---------------------------------------------------------------------------
# Perfil de jugador (spec perfil-jugador)
# ---------------------------------------------------------------------------
FECHA_REFERENCIA = pd.Timestamp("2021-09-09")


class JugadorLista(BaseModel):
    nflId: int
    nombre: str
    equipo: str | None
    posicion: str | None
    numero: int | None
    rusher_snaps: int
    pct_anticipa: float
    pct_presion: float
    offsides: int


class Ficha(BaseModel):
    nombre: str
    posicion: str | None
    equipo: str | None
    numero: int | None
    estatura: str | None
    peso: int | None
    edad: int | None
    universidad: str | None


class PresionGrupo(BaseModel):
    snaps: int
    pct_presion: float | None


class StatsJugador(BaseModel):
    rusher_snaps: int
    pct_anticipa: float
    percentil_anticipacion: float
    velocidad_media_snap: float
    pct_presion: float
    offsides: int
    anticipando: PresionGrupo
    sin_anticipar: PresionGrupo


class PuntoDistribucion(BaseModel):
    rango: str
    pct_jugador: float
    pct_liga: float


class JugadaDeJugador(BaseModel):
    gameId: int
    playId: int
    s_snap: float
    rival: str


class PerfilJugador(BaseModel):
    nflId: int
    ficha: Ficha
    stats: StatsJugador
    distribucion: list[PuntoDistribucion]
    jugadas_offside: list[JugadaDeJugador]


def _edad(nacimiento, referencia: pd.Timestamp = FECHA_REFERENCIA) -> int | None:
    fecha = pd.to_datetime(nan_a_none(nacimiento), errors="coerce")
    if fecha is None or pd.isna(fecha):
        return None
    años = referencia.year - fecha.year - ((referencia.month, referencia.day) < (fecha.month, fecha.day))
    return int(años)


def _moda(serie: pd.Series):
    s = serie.dropna()
    if s.empty:
        return None
    conteo = s.value_counts()
    return sorted(conteo[conteo == conteo.max()].index)[0]


def _texto(v) -> str | None:
    v = nan_a_none(v)
    return None if v is None or str(v).strip() == "" else str(v)


def construir_perfiles(datos: dict, alineados: pd.DataFrame, jugadas: list[dict]) -> tuple[list[dict], dict]:
    """Lista de Jugador_Elegible ordenada y perfiles {nflId: perfil}."""
    if alineados.empty:
        return [], {}
    df = _con_rango_presion(alineados)
    df = df.assign(_ant=(df["s"] >= UMBRAL_SCOUT), _pres=df["presion"].astype(bool))
    plays = datos["plays"].drop_duplicates(["gameId", "playId"])[["gameId", "playId", "defensiveTeam"]]
    df = df.merge(plays, on=["gameId", "playId"], how="left")

    snap = datos.get("tracking_snap")
    numeros: dict[int, int | None] = {}
    if snap is not None and not snap.empty and "jerseyNumber" in snap.columns:
        js = snap.dropna(subset=["nflId"])[["gameId", "playId", "nflId", "jerseyNumber"]].copy()
        js["nflId"] = js["nflId"].astype("int64")
        llaves = df[["gameId", "playId", "nflId"]].astype({"nflId": "int64"})
        js = js.merge(llaves, on=["gameId", "playId", "nflId"])
        numeros = {int(k): _entero(_moda(g["jerseyNumber"])) for k, g in js.groupby("nflId")}

    players = datos.get("players")
    info = {} if players is None or players.empty else {
        int(r["nflId"]): r for _, r in players.dropna(subset=["nflId"]).iterrows()
    }

    g = df.groupby("nflId")
    tabla = pd.DataFrame({
        "snaps": g.size(),
        "ant": g["_ant"].sum(),
        "pres": g["_pres"].sum(),
        "offsides": g["offside"].sum(),
        "v_media": g["s"].mean(),
    })
    tabla = tabla[tabla["snaps"] >= MIN_SNAPS_SCOUT].copy()
    if tabla.empty:
        return [], {}
    tabla["pct_ant"] = tabla["ant"] / tabla["snaps"] * 100.0
    tabla["pct_pres"] = tabla["pres"] / tabla["snaps"] * 100.0
    tabla = tabla.reset_index().sort_values(["pct_ant", "snaps", "nflId"], ascending=[False, False, True])
    valores_ant = tabla["pct_ant"].to_numpy()

    liga = df["rango"].astype(object).value_counts(normalize=True) * 100.0
    jug_por_inf: dict[int, list[dict]] = {}
    for j in jugadas:
        jug_por_inf.setdefault(int(j["infractor"]["nflId"]), []).append(
            {"gameId": j["gameId"], "playId": j["playId"], "s_snap": j["s_snap"], "rival": j["equipo_ofensiva"]})

    lista, perfiles = [], {}
    for r in tabla.itertuples(index=False):
        nid = int(r.nflId)
        sub = df[df["nflId"] == nid]
        equipo = _texto(_moda(sub["defensiveTeam"]))
        p = info.get(nid)
        nombre = _texto(p["displayName"]) if p is not None and "displayName" in p else None
        nombre = nombre or str(nid)
        posicion = _texto(p.get("officialPosition")) if p is not None else None
        numero = numeros.get(nid)
        lista.append({
            "nflId": nid, "nombre": nombre, "equipo": equipo, "posicion": posicion, "numero": numero,
            "rusher_snaps": int(r.snaps), "pct_anticipa": float(r.pct_ant), "pct_presion": float(r.pct_pres),
            "offsides": int(r.offsides),
        })
        ant = sub[sub["_ant"]]
        no_ant = sub[~sub["_ant"]]
        dist_j = sub["rango"].astype(object).value_counts(normalize=True) * 100.0
        perfiles[nid] = {
            "nflId": nid,
            "ficha": {
                "nombre": nombre, "posicion": posicion, "equipo": equipo, "numero": numero,
                "estatura": _texto(p.get("height")) if p is not None else None,
                "peso": _entero(pd.to_numeric(p.get("weight"), errors="coerce")) if p is not None else None,
                "edad": _edad(p.get("birthDate")) if p is not None else None,
                "universidad": _texto(p.get("collegeName")) if p is not None else None,
            },
            "stats": {
                "rusher_snaps": int(r.snaps),
                "pct_anticipa": float(r.pct_ant),
                "percentil_anticipacion": float((valores_ant <= r.pct_ant).mean() * 100.0),
                "velocidad_media_snap": float(r.v_media),
                "pct_presion": float(r.pct_pres),
                "offsides": int(r.offsides),
                "anticipando": {"snaps": int(len(ant)), "pct_presion": _pct(int(ant["_pres"].sum()), len(ant))},
                "sin_anticipar": {"snaps": int(len(no_ant)), "pct_presion": _pct(int(no_ant["_pres"].sum()), len(no_ant))},
            },
            "distribucion": [
                {"rango": e, "pct_jugador": float(dist_j.get(e, 0.0)), "pct_liga": float(liga.get(e, 0.0))}
                for e in RANGOS_ETIQUETAS
            ],
            "jugadas_offside": jug_por_inf.get(nid, []),
        }
    return lista, perfiles


# ---------------------------------------------------------------------------
# Equipos (spec equipos)
# ---------------------------------------------------------------------------
NOTA_EQUIPOS = (
    "Los offsides por equipo son pocos (de 0 a 9), así que sus tasas cambian mucho con un solo caso. "
    "El % de anticipación tiene entre 700 y 1,200 snaps por equipo y es el dato más confiable."
)


class EquipoDefensa(BaseModel):
    equipo: str
    rusher_snaps: int
    pct_anticipa: float
    pct_presion: float
    offsides: int
    offsides_por_1000: float


class EquipoOfensiva(BaseModel):
    equipo: str
    rusher_snaps_rival: int
    pct_anticipa_rival: float
    offsides_provocados: int
    offsides_por_1000: float


class EquiposResponse(BaseModel):
    defensas: list[EquipoDefensa]
    ofensivas: list[EquipoOfensiva]
    nota: str


def metricas_equipos(alineados: pd.DataFrame, plays: pd.DataFrame) -> dict:
    """Rankings de defensas (por % anticipa) y ofensivas (por offsides provocados por 1,000)."""
    if alineados.empty:
        return {"defensas": [], "ofensivas": [], "nota": NOTA_EQUIPOS}
    df = _con_rango_presion(alineados)
    df = df.assign(_ant=(df["s"] >= UMBRAL_SCOUT), _pres=df["presion"].astype(bool))
    equipos = plays.drop_duplicates(["gameId", "playId"])[["gameId", "playId", "defensiveTeam", "possessionTeam"]]
    df = df.merge(equipos, on=["gameId", "playId"], how="left")

    d = df.groupby("defensiveTeam").agg(snaps=("s", "size"), ant=("_ant", "sum"), pres=("_pres", "sum"),
                                        off=("offside", "sum")).reset_index()
    d["pct_ant"] = d["ant"] / d["snaps"] * 100.0
    d = d.sort_values(["pct_ant", "defensiveTeam"], ascending=[False, True])
    defensas = [{
        "equipo": str(r.defensiveTeam), "rusher_snaps": int(r.snaps), "pct_anticipa": float(r.pct_ant),
        "pct_presion": float(r.pres / r.snaps * 100.0), "offsides": int(r.off),
        "offsides_por_1000": float(r.off / r.snaps * 1000.0),
    } for r in d.itertuples(index=False)]

    o = df.groupby("possessionTeam").agg(snaps=("s", "size"), ant=("_ant", "sum"), off=("offside", "sum")).reset_index()
    o["por_1000"] = o["off"] / o["snaps"] * 1000.0
    o["pct_ant"] = o["ant"] / o["snaps"] * 100.0
    o = o.sort_values(["por_1000", "pct_ant", "possessionTeam"], ascending=[False, False, True])
    ofensivas = [{
        "equipo": str(r.possessionTeam), "rusher_snaps_rival": int(r.snaps), "pct_anticipa_rival": float(r.pct_ant),
        "offsides_provocados": int(r.off), "offsides_por_1000": float(r.por_1000),
    } for r in o.itertuples(index=False)]
    return {"defensas": defensas, "ofensivas": ofensivas, "nota": NOTA_EQUIPOS}


def calcular_todo(datos: dict) -> dict:
    """Todo lo que sirve la API, con una sola preparación de los datos."""
    rs, alineados = preparar_alineados(datos)
    lista, detalles = construir_jugadas(datos, rs, alineados)
    agregar_controles(datos, rs, alineados, lista, detalles)
    jugadores, perfiles = construir_perfiles(datos, alineados, lista)
    return {
        "offside": calcular_metricas(datos, (rs, alineados)),
        "jugadas": lista,
        "detalles": detalles,
        "jugadores": jugadores,
        "perfiles": perfiles,
        "equipos": metricas_equipos(alineados, datos["plays"]),
    }


def _limpiar_nan(obj: Any) -> Any:
    """Reemplaza NaN por None de forma recursiva (JSON valido)."""
    if isinstance(obj, dict):
        return {k: _limpiar_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_limpiar_nan(v) for v in obj]
    return nan_a_none(obj)