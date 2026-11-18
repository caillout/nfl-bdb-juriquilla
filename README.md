# ¿Vale la pena adivinar el snap?

**Resumen.** Con el tracking de las semanas 1 a 8 de 2021 medimos la velocidad de cada pass rusher en el instante exacto del snap, y encontramos que el 10.4% de los snaps en que el rusher ya se mueve (más de 0.5 yd/s) concentra el 63.6% de los offsides defensivos. Adivinar el snap sí tiene recompensa: los rushers que salen a más de 1 yd/s presionan al QB en 18.9% de los snaps, contra 10.7% de los que están quietos. Pero el riesgo crece mucho más rápido: su tasa de offside pasa de 0.6 a 22 por cada 1,000 snaps, y comparando a cada jugador consigo mismo la presión extra es de apenas unos 3 puntos, porque quienes se anticipan ya son los mejores rushers. Nuestra conclusión: adivinar el snap no conviene como estrategia general, solo es una apuesta que les funciona a unos cuantos rushers de élite. Para el entrenador, el tablero muestra a quién vigilar, en qué situaciones las defensas se arriesgan más (3er down) y qué ofensivas, como Kansas City, provocan más offsides.

Proyecto para el hackathon del NFL Big Data Bowl en la UNAM. Con los datos de tracking (10 cuadros por segundo) de las semanas 1 a 8 de la temporada 2021, medimos **qué tan rápido se mueve cada pass rusher en el instante exacto del snap** y lo cruzamos con los **offsides defensivos** marcados por los árbitros.

## El hallazgo

**El 10.4% de los snaps concentra el 63.6% de los offsides.** Son los snaps en los que el rusher ya va a más de 0.5 yd/s cuando se centra el balón.

| Velocidad en el snap | Rusher-snaps | Offsides | Offsides por 1,000 | % con presión al QB |
|---|---|---|---|---|
| 0–0.25 yd/s (quieto) | 20,594 | 13 | 0.63 | 10.7% |
| 0.25–0.5 yd/s | 6,389 | 3 | 0.47 | 11.8% |
| 0.5–1 yd/s | 2,691 | 16 | 5.95 | 13.6% |
| 1–2 yd/s | 403 | 9 | 22.33 | 18.9% |
| > 2 yd/s | 39 | 3 | 76.92 | 20.5% |

- **El offside se delata por el movimiento, no por la posición.** En el cuadro del snap casi ningún infractor ya pasó el balón, pero ya iban en movimiento.
- **Es un dilema de riesgo contra recompensa.** Los rushers que salen en movimiento presionan más al QB, pero su tasa de offside se multiplica.
- **Las defensas se arriesgan más en 3er down:** 2.29 offsides por cada 1,000 snaps, contra 0.73 en 1er down.
- **La evidencia en una jugada real:** Jamal Adams (SEA) iba a 2.8 yd/s medio segundo antes del snap, mientras el resto de su línea estaba en 0.0 yd/s. El tablero anima esa jugada y las otras 47 con offside.

**Cautela.** De 1 yd/s en adelante solo hay 442 snaps y 12 offsides. La relación es correlación, no causa: los rushers que más se anticipan también son de los mejores (Barrett, Judon, Bosa), y esos presionan más de todos modos.

## Qué muestra el tablero

1. **Número clave:** qué % de los snaps concentra qué % de los offsides.
2. **La evidencia, el mismo jugador con y sin offside:** dos canchas animadas y sincronizadas en el snap. Izquierda: la jugada en que lo marcaron. Derecha: una jugada control del mismo jugador, alineado, sin falta, quieto en el snap y en la situación de juego más parecida. Las 48 jugadas con offside tienen control. Una gráfica muestra su velocidad en ambas jugadas contra el resto de la línea.
3. **Riesgo contra recompensa:** offsides por 1,000 (barras) y % de presión (línea) por rango de velocidad.
4. **Offsides por down:** tasa por cada 1,000 snaps.
5. **Top 10 scout:** rushers que más seguido salen en movimiento (s ≥ 1 yd/s, mínimo 100 snaps).
6. **Perfil de jugador:** de los 130 rushers con 100+ snaps, con buscador. Incluye ficha, percentil de anticipación, presión anticipando contra sin anticipar, distribución de velocidad contra la liga y sus jugadas con offside enlazadas al visor.
7. **Equipos:** qué defensas se anticipan más y qué ofensivas provocan más offsides. Kansas City provoca 9, más que nadie.
8. **Duelo del domingo, MIN vs SF:** cómo llegaban esas dos defensas y ofensivas en 2021, con sus rushers que más se anticipan.

Los equipos se identifican con sus siglas y colores. No se usan logos ni fotos, por ser marcas registradas y porque requerirían recursos externos.

## Definiciones

| Concepto | Definición |
|---|---|
| Snap | Primer cuadro de la jugada con `event` igual a `ball_snap` o `autoevent_ballsnap` |
| Rusher | Jugador con `pff_role == "Pass Rush"` en `pffScoutingData.csv` |
| Velocidad en el snap | Columna `s` del tracking (yd/s) en el cuadro del snap, sin recalcular |
| Cruce | `round((x_rusher − x_balón) × signo, 2)`, con signo −1 si `playDirection == "right"` y +1 si `"left"`. Positivo = ya pasó el centro del balón |
| Alineado en la línea | −1.5 ≤ cruce ≤ 0.5 yardas. Separa a los linieros de los linebackers que vienen caminando desde atrás |
| Presión | `pff_hit + pff_hurry + pff_sack > 0` para ese rusher en esa jugada (registro de PFF) |
| Offside ligado | `foulName1` o `foulName2` igual a `"Defensive Offside"`, ligado al jugador de `foulNFLId1` o `foulNFLId2` |

Umbrales: el número clave usa s > 0.5 yd/s y el top 10 usa s ≥ 1.0 yd/s, por decisión deliberada.

## Stack

Stack fijo del evento (`.kiro/steering/rules.md`), sin dependencias adicionales:

- **Backend:** Python 3.12, FastAPI, pandas, numpy. Todo se calcula en memoria al arrancar, en segundo plano (unos 25 s). `data/` es de solo lectura y no se escribe nada a disco.
- **Frontend:** React 18, Vite 5, TypeScript, Tailwind CSS 3 y Recharts. La cancha está dibujada en SVG.
- **Desarrollo:** con specs en `.kiro/specs/` (`offside-endpoint` y `jugada-evidencia`).

## Cómo correrlo

Requisito: los datos del Big Data Bowl dentro de `data/`, que no se versiona. El backend busca solo la carpeta que contiene `plays.csv` y `tracking/`.

**Desarrollo (dos terminales):**

```
.venv\Scripts\uvicorn backend.main:app --reload        # API en http://localhost:8000
cd dashboard && npm run dev                            # tablero en http://localhost:5173
```

**Como en producción (un solo puerto):**

```
cd dashboard && npm run build
.venv\Scripts\uvicorn backend.main:app                 # tablero y API en http://localhost:8000
```

**Pruebas:**

```
.venv\Scripts\python -m pytest backend/tests -q
```

## API

| Ruta | Respuesta |
|---|---|
| `GET /health` | `{"status": "ok"}`, desde el primer segundo |
| `GET /api/offside` | Métricas por rango, número clave, top 10, por down y totales |
| `GET /api/jugadas` | Las 48 jugadas con offside, de mayor a menor velocidad en el snap |
| `GET /api/jugadas/{gameId}/{playId}` | Cuadros de la jugada (de −1.5 s a +2 s del snap), velocidades y su jugada control |
| `GET /api/jugadores` | Los 130 rushers con 100+ snaps alineados |
| `GET /api/jugadores/{nflId}` | Perfil del jugador |
| `GET /api/equipos` | Rankings de defensas y ofensivas |

Mientras se calcula, las rutas `/api/...` responden `503` con `{"detail": {"estado": "calculando"}}` y el tablero reintenta solo.

## Limitaciones

- Solo hay 50 offsides defensivos en el periodo, y 44 se ligan a un rusher alineado. Los rangos de velocidad altos tienen pocos casos.
- El dataset solo incluye jugadas de pase que sí se jugaron. Los false starts, el encroachment y las neutral zone infractions detienen la jugada antes del snap, así que no aparecen.
- La referencia es el centro del balón, no la neutral zone oficial.
- La presión viene del registro de PFF, no del tracking.

## Equipo

- Norman Caillou Tinoco Rico
- José Luis Garza Romero

## Datos

NFL Big Data Bowl 2023 (Next Gen Stats y Pro Football Focus). Los datos no se incluyen en el repositorio.

<!-- Agreguen una captura del tablero, por ejemplo: ![Tablero](docs/tablero.png) -->
