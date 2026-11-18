"""Generadores de datos sintéticos con los nombres de columna reales de data/.

Solo escriben dentro de carpetas temporales de pytest (tmp_path), nunca en el
proyecto.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

COLS_TRACKING = [
    "gameId", "playId", "nflId", "frameId", "time", "jerseyNumber", "team",
    "playDirection", "x", "y", "s", "a", "dis", "o", "dir", "event",
]
COLS_PLAYS = [
    "gameId", "playId", "playDescription", "quarter", "down", "yardsToGo",
    "possessionTeam", "defensiveTeam", "gameClock",
    "foulName1", "foulNFLId1", "foulName2", "foulNFLId2", "foulName3", "foulNFLId3",
]
COLS_PFF = ["gameId", "playId", "nflId", "pff_role", "pff_hit", "pff_hurry", "pff_sack"]
COLS_PLAYERS = ["nflId", "displayName", "height", "weight", "birthDate", "collegeName", "officialPosition"]

DESPLAZAMIENTO_POR_CUADRO = 0.05  # yardas por cuadro lejos del snap


def filas_jugada(
    game_id: int,
    play_id: int,
    direccion: str,
    n_frames: int,
    frame_snap: int,
    evento_snap: str | None,
    jugadores: list[dict],
    balon_x: float,
    balon_y: float = 26.65,
    con_balon: bool = True,
    balon_en_snap: bool = True,
    omitir: set[tuple[int, int]] | None = None,
) -> list[dict]:
    """Filas de tracking de una jugada.

    `jugadores`: dicts con nflId, team, numero, x, y, s (posición en el snap).
    `evento_snap`: "ball_snap", "autoevent_ballsnap" o None (jugada sin snap).
    `omitir`: pares (nflId, frameId) sin fila (jugador ausente en ese cuadro).
    En el cuadro del snap las posiciones son exactamente las dadas.
    """
    omitir = omitir or set()
    filas = []
    for f in range(1, n_frames + 1):
        if evento_snap is not None and f == frame_snap:
            evento = evento_snap
        elif f == 1:
            evento = "line_set"
        else:
            evento = "None"
        delta = (f - frame_snap) * DESPLAZAMIENTO_POR_CUADRO
        base = {
            "gameId": game_id, "playId": play_id, "frameId": f,
            "time": "2021-09-10T00:00:00Z", "playDirection": direccion,
            "a": 0.0, "dis": 0.0, "event": evento,
        }
        for j in jugadores:
            if (j["nflId"], f) in omitir:
                continue
            filas.append({
                **base,
                "nflId": j["nflId"], "jerseyNumber": j["numero"], "team": j["team"],
                "x": round(j["x"] + delta, 2), "y": round(j["y"], 2), "s": j["s"],
                "o": 90.0, "dir": 90.0,
            })
        if con_balon and not (f == frame_snap and not balon_en_snap):
            filas.append({
                **base,
                "nflId": None, "jerseyNumber": None, "team": "football",
                "x": round(balon_x, 2), "y": round(balon_y, 2), "s": 0.0,
                "o": None, "dir": None,
            })
    return filas


def escribir_data_dir(
    base: Path,
    tracking_por_juego: dict[int, list[dict]],
    plays: list[dict],
    pff: list[dict],
    players: list[dict],
    incluir_plays: bool = True,
) -> Path:
    """Escribe plays.csv, pffScoutingData.csv, players.csv y tracking/ en `base`."""
    base = Path(base)
    (base / "tracking").mkdir(parents=True, exist_ok=True)
    for game_id, filas in tracking_por_juego.items():
        df = pd.DataFrame(filas, columns=COLS_TRACKING)
        df["nflId"] = df["nflId"].astype("Int64")
        df["jerseyNumber"] = df["jerseyNumber"].astype("Int64")
        df.to_csv(base / "tracking" / f"tracking_{game_id}.csv", index=False)
    if incluir_plays:
        dp = pd.DataFrame(plays, columns=COLS_PLAYS)
        for c in ("foulNFLId1", "foulNFLId2", "foulNFLId3", "down", "quarter", "yardsToGo"):
            dp[c] = dp[c].astype("Int64")
        dp.to_csv(base / "plays.csv", index=False, na_rep="NA")
    dpf = pd.DataFrame(pff, columns=COLS_PFF)
    for c in ("pff_hit", "pff_hurry", "pff_sack"):
        dpf[c] = dpf[c].astype("Int64")
    dpf.to_csv(base / "pffScoutingData.csv", index=False, na_rep="NA")
    pd.DataFrame(players, columns=COLS_PLAYERS).to_csv(base / "players.csv", index=False)
    return base


def jugada_plays(game_id, play_id, down, fouls=(), descripcion=None) -> dict:
    """Fila de plays.csv. `fouls`: hasta 3 pares (foulName, foulNFLId)."""
    fila = {
        "gameId": game_id, "playId": play_id,
        "playDescription": descripcion or f"Jugada {game_id}-{play_id}",
        "quarter": 1, "down": down, "yardsToGo": 10,
        "possessionTeam": "OFF", "defensiveTeam": "DEF", "gameClock": "15:00",
    }
    for i in range(1, 4):
        nombre, ident = fouls[i - 1] if i <= len(fouls) else (None, None)
        fila[f"foulName{i}"] = nombre
        fila[f"foulNFLId{i}"] = ident
    return fila


# ---------------------------------------------------------------------------
# Conjunto fijo de datos sintéticos con resultados conocidos
# ---------------------------------------------------------------------------
G1, G2 = 2021000001, 2021000002
OFS = "Defensive Offside"

NOMBRES = {
    101: "Rusher Uno", 102: "Rusher Dos", 103: "Rusher Tres",
    104: "Esquinero", 105: "Rusher Fantasma", 201: "Mariscal",
}
NUMEROS = {101: 91, 102: 92, 103: 93, 104: 24, 201: 12}


def _j(nflId, x, s, team="DEF", y=None):
    return {"nflId": nflId, "team": team, "numero": NUMEROS[nflId], "x": x,
            "y": 20.0 + nflId % 10 if y is None else y, "s": s}


def _pff(g, p, nflId, rol, hit=None, hurry=None, sack=None):
    return {"gameId": g, "playId": p, "nflId": nflId, "pff_role": rol,
            "pff_hit": hit, "pff_hurry": hurry, "pff_sack": sack}


def construir_data_sintetica(base: Path) -> Path:
    """Dos juegos (derecha e izquierda) con casos frontera; ver ESPERADO."""
    tracking = {G1: [], G2: []}
    plays, pff = [], []

    # --- Juego 1, playDirection right, balón en x = 50.00 (cruce = bx - x) ---
    bx1 = 50.00
    # P10: down 1, offside en foulName1 de 101; 101 no tiene fila en el cuadro 30.
    tracking[G1] += filas_jugada(
        G1, 10, "right", 40, 10, "ball_snap",
        [_j(101, 49.70, 2.5), _j(102, 51.50, 0.25), _j(103, 51.00, 1.0),
         _j(104, 55.00, 0.0), _j(201, 49.00, 0.0, team="OFF")],
        bx1, omitir={(101, 30)},
    )
    plays.append(jugada_plays(G1, 10, 1, [(OFS, 101)]))
    pff += [_pff(G1, 10, 101, "Pass Rush", hit=1), _pff(G1, 10, 102, "Pass Rush"),
            _pff(G1, 10, 103, "Pass rush", hit=1),  # minúscula: se ignora
            _pff(G1, 10, 105, "Pass Rush"),           # sin posición en el snap
            _pff(G1, 10, 104, "Coverage"), _pff(G1, 10, 201, "Pass Block")]

    # P20: down 2, holding en foulName1, offside de 102 en foulName2, autoevent.
    tracking[G1] += filas_jugada(
        G1, 20, "right", 40, 20, "autoevent_ballsnap",
        [_j(101, 51.00, 1.0), _j(102, 50.50, 0.5), _j(201, 49.00, 0.0, team="OFF")],
        bx1,
    )
    plays.append(jugada_plays(G1, 20, 2, [("Offensive Holding", 201), (OFS, 102)]))
    pff += [_pff(G1, 20, 101, "Pass Rush", hurry=1), _pff(G1, 20, 102, "Pass Rush", 0, 0, 0),
            _pff(G1, 20, 201, "Pass Block")]

    # P30: down 3, offside solo en foulName3 (se ignora); 102 en cruce 0.5.
    tracking[G1] += filas_jugada(
        G1, 30, "right", 30, 10, "ball_snap",
        [_j(101, 52.00, 0.8), _j(102, 49.50, 2.0), _j(201, 49.00, 0.0, team="OFF")],
        bx1,
    )
    plays.append(jugada_plays(G1, 30, 3, [("Offensive Holding", 201), (None, None), (OFS, 101)]))
    pff += [_pff(G1, 30, 101, "Pass Rush"), _pff(G1, 30, 102, "Pass Rush", sack=1)]

    # P40: down 1, offside de 101, pero sin evento de snap: se excluye.
    tracking[G1] += filas_jugada(
        G1, 40, "right", 30, 10, None,
        [_j(101, 49.90, 3.0), _j(102, 50.50, 0.2)], bx1,
    )
    plays.append(jugada_plays(G1, 40, 1, [(OFS, 101)]))
    pff += [_pff(G1, 40, 101, "Pass Rush", hit=1), _pff(G1, 40, 102, "Pass Rush")]

    # P50: down 2, offside de 102, con snap pero sin filas del balón: se excluye.
    tracking[G1] += filas_jugada(
        G1, 50, "right", 30, 10, "ball_snap",
        [_j(101, 50.50, 0.1), _j(102, 49.90, 2.2)], bx1, con_balon=False,
    )
    plays.append(jugada_plays(G1, 50, 2, [(OFS, 102)]))
    pff += [_pff(G1, 50, 101, "Pass Rush"), _pff(G1, 50, 102, "Pass Rush")]

    # --- Juego 2, playDirection left, balón en x = 52.51 (cruce = x - bx) ---
    bx2 = 52.51
    # P10: down 4, offside de 101 que NO está alineado (cruce -3.0).
    tracking[G2] += filas_jugada(
        G2, 10, "left", 40, 10, "ball_snap",
        [_j(101, 49.51, 3.0), _j(102, 51.51, 0.0), _j(104, 47.00, 0.0),
         _j(201, 53.51, 0.0, team="OFF")],
        bx2,
    )
    plays.append(jugada_plays(G2, 10, 4, [(OFS, 101)]))
    pff += [_pff(G2, 10, 101, "Pass Rush"), _pff(G2, 10, 102, "Pass Rush"),
            _pff(G2, 10, 104, "Coverage"), _pff(G2, 10, 201, "Pass Block")]

    # P20: down 0 (inválido), offside de 102; 101 en cruce -1.5 calculado
    # con 51.01 - 52.51 (error de punto flotante sin redondeo).
    tracking[G2] += filas_jugada(
        G2, 20, "left", 40, 20, "ball_snap",
        [_j(101, 51.01, 0.3), _j(102, 52.81, 0.6), _j(201, 53.51, 0.0, team="OFF")],
        bx2,
    )
    plays.append(jugada_plays(G2, 20, 0, [(OFS, 102)]))
    pff += [_pff(G2, 20, 101, "Pass Rush", None, 0, 0), _pff(G2, 20, 102, "Pass Rush")]

    # P30: down 4, sin faltas.
    tracking[G2] += filas_jugada(
        G2, 30, "left", 30, 10, "ball_snap",
        [_j(101, 52.01, 1.5), _j(102, 53.51, 0.2), _j(201, 53.51, 0.0, team="OFF")],
        bx2,
    )
    plays.append(jugada_plays(G2, 30, 4))
    pff += [_pff(G2, 30, 101, "Pass Rush"), _pff(G2, 30, 102, "Pass Rush")]

    players = [{"nflId": k, "displayName": v} for k, v in NOMBRES.items()]
    return escribir_data_dir(base, tracking, plays, pff, players)


# Resultados esperados del conjunto fijo (calculados a mano).
ESPERADO = {
    "rusher_snaps_total": 12,  # todos los Rusher_Snap (alineados o no)
    "rangos": [
        # rango, rusher_snaps, offsides, offsides_por_1000, pct_presion
        ("0-0.25", 2, 0, 0.0, 0.0),
        ("0.25-0.5", 2, 1, 500.0, 0.0),
        ("0.5-1", 2, 1, 500.0, 50.0),
        ("1-2", 2, 0, 0.0, 50.0),
        (">2", 1, 1, 1000.0, 100.0),
    ],
    "por_down": [
        # down, rusher_snaps, offsides, offsides_por_1000, pct_del_total
        (1, 2, 1, 500.0, 50.0),
        (2, 2, 1, 500.0, 50.0),
        (3, 1, 0, 0.0, 0.0),
        (4, 2, 0, 0.0, 0.0),
    ],
    "sin_down_valido": {"rusher_snaps": 2, "offsides": 1},
    "totales": {"rusher_snaps": 9, "offsides": 3},
    "x_pct_snaps": 5 / 9 * 100,
    "y_pct_offsides": 2 / 3 * 100,
    # (gameId, playId, infractor, s_snap, cruce_snap, alineado) en orden
    "jugadas": [
        (G2, 10, 101, 3.0, -3.0, False),
        (G1, 10, 101, 2.5, 0.3, True),
        (G2, 20, 102, 0.6, 0.3, True),
        (G1, 20, 102, 0.5, -0.5, True),
    ],
    # (gameId, playId) -> (frame_snap, n_frames del archivo, linea_golpeo_x)
    "ventanas": {
        (G2, 10): (10, 40, 67.49),
        (G1, 10): (10, 40, 50.0),
        (G2, 20): (20, 40, 67.49),
        (G1, 20): (20, 40, 50.0),
    },
    "sin_jugada": [(G1, 30), (G1, 40), (G1, 50), (G2, 30), (G1, 99)],
    # Jugada control (spec jugada-control):
    # (gameId, playId) offside -> (clave control, distancia_situacion, criterio) o None.
    # 102 está quieto (s = 0.25, frontera incluida) y alineado (cruce -1.5) en G1-P10
    # (down 1); en G2-P10 también está quieto y alineado pero en down 4 (más lejos).
    # 101 no tiene ninguna Candidata_Control (G1-P50 no tiene balón).
    "controles": {
        (G2, 10): None,
        (G1, 10): None,
        (G2, 20): ((G1, 10), 10, "Mismo jugador, 1er y 10, quieto en el snap (0.25 yd/s)"),
        (G1, 20): ((G1, 10), 10, "Mismo jugador, mismo partido, 1er y 10, quieto en el snap (0.25 yd/s)"),
    },
}


# ---------------------------------------------------------------------------
# Segundo conjunto fijo: jugada control y perfil de jugador
# ---------------------------------------------------------------------------
G3, G4, G5, G6 = 2021000003, 2021000004, 2021000005, 2021000006
BX_CP = 50.00
N_FRAMES_CP, SNAP_CP = 8, 4  # jugadas de los escenarios de control
N_MASIVAS = 160              # jugadas de G6 (un solo cuadro, el del snap)

# (gameId, playId, down, yardsToGo, [(nflId, cruce, s[, pff_role])], nflId con offside o None)
ESCENARIOS_CONTROL = [
    # 401: empate en distancia 2 entre G3-P2 (mismo partido, s 0.20) y G4-P1 (otro, s 0.10)
    (G3, 1, 3, 7, [(401, -0.5, 1.5)], 401),
    (G3, 2, 3, 9, [(401, -0.5, 0.20)], None),
    (G4, 1, 3, 5, [(401, -0.5, 0.10)], None),
    (G4, 2, 2, 7, [(401, -0.5, 0.00)], None),
    (G4, 3, 3, 7, [(401, -0.5, 0.30)], None),               # no está quieto
    (G4, 4, 3, 7, [(401, -3.0, 0.00)], None),               # no está alineado
    (G4, 5, 3, 7, [(401, -0.5, 0.00, "Coverage")], None),   # no es rusher
    (G4, 6, 3, 7, [(401, -0.5, 0.00)], 401),                # con offside: no es candidata
    # 402: empate en distancia 1 entre dos partidos distintos: gana la menor s;
    # G4-P11 es del mismo partido y con s menor pero distancia 10.
    (G4, 10, 2, 5, [(402, -0.5, 0.80)], 402),
    (G3, 10, 2, 6, [(402, -0.5, 0.20)], None),
    (G5, 10, 2, 4, [(402, -0.5, 0.05)], None),
    (G4, 11, 1, 5, [(402, -0.5, 0.00)], None),
    # 403: distancia 0 y misma s en dos partidos distintos: gana el menor gameId.
    (G5, 20, 1, 10, [(403, 0.5, 2.20)], 403),                # cruce 0.5: alineado
    (G4, 20, 1, 10, [(403, -0.5, 0.10)], None),
    (G3, 20, 1, 10, [(403, -1.5, 0.10)], None),              # cruce -1.5: alineado
    # 404: distancia 0, misma s y mismo gameId: gana el menor playId.
    (G5, 30, 4, 1, [(404, -0.5, 0.60)], 404),
    (G3, 31, 4, 1, [(404, -0.5, 0.00)], None),
    (G3, 30, 4, 1, [(404, -0.5, 0.00)], None),
    (G4, 30, 4, 1, [(404, -0.5, 0.25)], None),
    # 405: sin ninguna Candidata_Control.
    (G3, 40, 2, 8, [(405, -0.5, 1.10)], 405),
    (G4, 40, 2, 8, [(405, -0.5, 0.50)], None),
    (G5, 40, 2, 8, [(405, -3.0, 0.00)], None),
    (G5, 41, 2, 8, [(405, 0.6, 0.00)], None),                # cruce 0.6: no alineado
    # 406: s = 0.25 es candidata (distancia 10); s = 0.26 no lo es (aunque distancia 0).
    (G3, 50, 1, 10, [(406, -0.5, 0.90)], 406),
    (G4, 50, 2, 10, [(406, -0.5, 0.25)], None),
    (G4, 51, 1, 10, [(406, -0.5, 0.26)], None),
]
RELLENO, OFENSIVO = 499, 501  # otro rusher (Resto_Linea) y un ofensivo en cada escenario

FICHAS_CP = {
    # nflId: (displayName, height, weight, birthDate, collegeName, officialPosition)
    300: ("Perfil Cero", "6-5", 270, "1990-01-15", "Alabama", "DE"),
    301: ("Perfil Uno", "6-2", 250, "1992-11-17", "Colorado State", "OLB"),
    302: ("Perfil Dos", "6-3", 300, "", "Ohio State", "DT"),       # sin birthDate
    303: ("Perfil Tres", "6-1", None, "1995-09-09", "", "OLB"),    # cumple el 2021-09-09
    304: ("Perfil Cuatro", "6-0", 240, "1996-05-05", "Iowa", "ILB"),
    401: ("Control A", None, None, None, None, None),
    402: ("Control B", None, None, None, None, None),
    403: ("Control C", None, None, None, None, None),
    404: ("Control D", None, None, None, None, None),
    405: ("Sin Control", None, None, None, None, None),
    406: ("Control E", None, None, None, None, None),
    RELLENO: ("Relleno", None, None, None, None, None),
    OFENSIVO: ("Ofensivo", None, None, None, None, None),
}


def _x_desde_cruce(cruce: float, direccion: str, bx: float = BX_CP) -> float:
    """x tal que calcular_cruce(x, bx, direccion) == cruce."""
    return round(bx - cruce if direccion == "right" else bx + cruce, 2)


def _s_masivas(i: int) -> dict[int, tuple[float, int] | None]:
    """{nflId: (s, jerseyNumber)} de la jugada masiva i (1..160) de G6."""
    s301 = 1.2 if i <= 29 else (0.1 if i <= 59 else 0.4)
    return {
        300: (1.5 if i <= 50 else 0.0, 90) if i <= 100 else None,
        301: (s301, 99 if i <= 10 else 55) if i <= 118 else None,
        302: (1.0 if i <= 40 else 0.25, 92),
        303: (2.0 if i > 120 else 0.5, 93),
        304: (1.0, 94) if i <= 99 else None,
    }


def construir_data_control_perfil(base: Path) -> Path:
    """Escenarios de jugada control (G3-G5) y jugadores con >= 100 snaps (G6); ver ESPERADO_CP."""
    tracking = {G3: [], G4: [], G5: [], G6: []}
    plays, pff = [], []
    for g, p, down, ytg, rushers, ofensor in ESCENARIOS_CONTROL:
        direccion = "left" if g == G4 else "right"
        jugadores = []
        for r in rushers:
            nid, cruce, s = r[0], r[1], r[2]
            rol = r[3] if len(r) > 3 else "Pass Rush"
            jugadores.append({"nflId": nid, "team": "NYG", "numero": nid % 100,
                              "x": _x_desde_cruce(cruce, direccion), "y": 25.0, "s": s})
            pff.append({"gameId": g, "playId": p, "nflId": nid, "pff_role": rol,
                        "pff_hit": None, "pff_hurry": None, "pff_sack": None})
        jugadores.append({"nflId": RELLENO, "team": "NYG", "numero": 98,
                          "x": _x_desde_cruce(-1.0, direccion), "y": 30.0, "s": 0.3})
        jugadores.append({"nflId": OFENSIVO, "team": "DAL", "numero": 12,
                          "x": _x_desde_cruce(1.0, direccion), "y": 26.0, "s": 0.0})
        pff.append({"gameId": g, "playId": p, "nflId": RELLENO, "pff_role": "Pass Rush",
                    "pff_hit": None, "pff_hurry": 1, "pff_sack": None})
        pff.append({"gameId": g, "playId": p, "nflId": OFENSIVO, "pff_role": "Pass Block",
                    "pff_hit": None, "pff_hurry": None, "pff_sack": None})
        tracking[g] += filas_jugada(g, p, direccion, N_FRAMES_CP, SNAP_CP, "ball_snap", jugadores, BX_CP)
        fila = jugada_plays(g, p, down, [(OFS, ofensor)] if ofensor else [])
        fila.update(yardsToGo=ytg, possessionTeam="DAL", defensiveTeam="NYG")
        plays.append(fila)

    # G6: jugadas de un solo cuadro (el del snap) para llegar a >= 100 Rusher_Alineado.
    # down = i % 4 + 1, yardsToGo = i % 10 + 1; defensa KC en 1..40 y TB en 41..160.
    def masiva(p, down, ytg, defensa, ofensiva, jugadores_s, ofensor=None, hits=()):
        jugadores = [{"nflId": nid, "team": defensa, "numero": num,
                      "x": _x_desde_cruce(-0.5, "right"), "y": 10.0 + nid % 10 * 3, "s": s}
                     for nid, (s, num) in jugadores_s.items()]
        tracking[G6].extend(filas_jugada(G6, p, "right", 1, 1, "ball_snap", jugadores, BX_CP))
        for nid in jugadores_s:
            pff.append({"gameId": G6, "playId": p, "nflId": nid, "pff_role": "Pass Rush",
                        "pff_hit": 1 if nid in hits else None, "pff_hurry": None, "pff_sack": None})
        fila = jugada_plays(G6, p, down, [(OFS, ofensor)] if ofensor else [])
        fila.update(yardsToGo=ytg, possessionTeam=ofensiva, defensiveTeam=defensa)
        plays.append(fila)

    for i in range(1, N_MASIVAS + 1):
        js = {k: v for k, v in _s_masivas(i).items() if v is not None}
        masiva(i, i % 4 + 1, i % 10 + 1, "KC" if i <= 40 else "TB", "BUF" if i % 3 == 0 else "NE",
               js, hits={301} if i % 5 == 0 else set())
    # offsides de 301 (ambos en defensa KC contra BUF)
    masiva(201, 3, 7, "KC", "BUF", {301: (1.8, 55)}, ofensor=301, hits={301})
    masiva(202, 1, 10, "KC", "BUF", {301: (0.7, 55)}, ofensor=301)

    players = [{"nflId": k, "displayName": v[0], "height": v[1], "weight": v[2], "birthDate": v[3],
                "collegeName": v[4], "officialPosition": v[5]} for k, v in FICHAS_CP.items()]
    return escribir_data_dir(base, tracking, plays, pff, players)


ESPERADO_CP = {
    # (gameId, playId) offside -> (infractor, clave control, distancia_situacion, criterio) o control None
    "controles": {
        (G3, 1): (401, (G3, 2), 2, "Mismo jugador, mismo partido, 3er y 9, quieto en el snap (0.20 yd/s)"),
        (G4, 6): (401, (G4, 1), 2, "Mismo jugador, mismo partido, 3er y 5, quieto en el snap (0.10 yd/s)"),
        (G4, 10): (402, (G5, 10), 1, "Mismo jugador, 2do y 4, quieto en el snap (0.05 yd/s)"),
        (G5, 20): (403, (G3, 20), 0, "Mismo jugador, 1er y 10, quieto en el snap (0.10 yd/s)"),
        (G5, 30): (404, (G3, 30), 0, "Mismo jugador, 4to y 1, quieto en el snap (0.00 yd/s)"),
        (G3, 40): (405, None, None, None),
        (G3, 50): (406, (G4, 50), 10, "Mismo jugador, 2do y 10, quieto en el snap (0.25 yd/s)"),
        (G6, 201): (301, (G6, 46), 0, "Mismo jugador, mismo partido, 3er y 7, quieto en el snap (0.10 yd/s)"),
        (G6, 202): (301, (G6, 48), 1, "Mismo jugador, mismo partido, 1er y 9, quieto en el snap (0.10 yd/s)"),
    },
    # Lista de Jugador_Elegible en orden: (nflId, nombre, rusher_snaps, pct_anticipa).
    # 302 y 303 empatan en % y snaps (gana el menor nflId); 301 empata en % con menos snaps;
    # 300 tiene exactamente 100 snaps; 304 tiene 99 y no es elegible.
    "jugadores": [
        (300, "Perfil Cero", 100, 50.0),
        (302, "Perfil Dos", 160, 25.0),
        (303, "Perfil Tres", 160, 25.0),
        (301, "Perfil Uno", 120, 25.0),
    ],
    "no_elegibles": [304, 401, 405, RELLENO, 999999],
    "fichas": {
        # numero: 99 en sus 10 primeras jugadas y 55 en las demás -> 55.
        # equipo: KC en 42 snaps y TB en 78 -> TB. Edad al 2021-09-09: 28.
        301: {"nombre": "Perfil Uno", "posicion": "OLB", "equipo": "TB", "numero": 55,
              "estatura": "6-2", "peso": 250, "edad": 28, "universidad": "Colorado State"},
        300: {"nombre": "Perfil Cero", "posicion": "DE", "equipo": "TB", "numero": 90,
              "estatura": "6-5", "peso": 270, "edad": 31, "universidad": "Alabama"},
        302: {"nombre": "Perfil Dos", "posicion": "DT", "equipo": "TB", "numero": 92,
              "estatura": "6-3", "peso": 300, "edad": None, "universidad": "Ohio State"},
        303: {"nombre": "Perfil Tres", "posicion": "OLB", "equipo": "TB", "numero": 93,
              "estatura": "6-1", "peso": None, "edad": 26, "universidad": None},
    },
    # Stats de 301: 30 de 120 anticipando (29 con s 1.2 y el offside con s 1.8).
    # Presión (hit en i % 5 == 0 y en el offside 201): 6 de 30 anticipando, 18 de 90 sin anticipar.
    "stats_301": {
        "rusher_snaps": 120, "pct_anticipa": 25.0, "percentil_anticipacion": 75.0,
        "velocidad_media_snap": (29 * 1.2 + 30 * 0.1 + 59 * 0.4 + 1.8 + 0.7) / 120,
        "pct_presion": 20.0, "offsides": 2,
        "anticipando": {"snaps": 30, "pct_presion": 20.0},
        "sin_anticipar": {"snaps": 90, "pct_presion": 20.0},
    },
    "distribucion_301": [("0-0.25", 25.0), ("0.25-0.5", 59 / 120 * 100), ("0.5-1", 1 / 120 * 100),
                         ("1-2", 25.0), (">2", 0.0)],
    "jugadas_offside_301": [
        {"gameId": G6, "playId": 201, "s_snap": 1.8, "rival": "BUF"},
        {"gameId": G6, "playId": 202, "s_snap": 0.7, "rival": "BUF"},
    ],
}
