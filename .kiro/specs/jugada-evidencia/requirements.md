# Requirements Document

## Introduction

Esta función agrega un visor de jugadas que muestra, con los datos de tracking, la evidencia del hallazgo principal: el rusher marcado con offside ya se está moviendo en el snap mientras el resto de la línea defensiva sigue quieta. El Backend expone la lista de jugadas con offside y el detalle cuadro por cuadro de cada una; el Dashboard las anima sobre una cancha dibujada en SVG y grafica la velocidad del infractor contra el resto de la línea. Reutiliza las definiciones de `offside-endpoint` (Frame_Snap, Rusher, Cruce, Rusher_Alineado, Offside_Ligado) y se calcula en el mismo paso de carga, en segundo plano. Respeta `.kiro/steering/rules.md`: stack fijo, `data/` en solo lectura, sin escribir a disco y rutas relativas en el Dashboard.

## Glossary

- **Jugada_Offside**: Jugada `(gameId, playId)` con un Offside_Ligado cuyo infractor aparece como Rusher_Snap (tiene posición en el Frame_Snap).
- **Infractor**: Rusher del Offside_Ligado de una Jugada_Offside.
- **Ventana**: Cuadros de tracking de la jugada con `frameId` entre `Frame_Snap - 15` y `Frame_Snap + 20` que existan en el archivo (el tracking suele empezar unos 6 cuadros antes del snap).
- **t**: Tiempo relativo al snap en segundos, `(frameId - Frame_Snap) / 10`.
- **Coordenadas_Normalizadas**: `x`, `y` transformadas para que la ofensiva siempre avance hacia la derecha: si `playDirection == "left"`, `x' = 120 - x` y `y' = 53.3 - y`; si no, sin cambio.
- **Resto_Linea**: Rushers alineados (Rusher_Alineado) de la misma jugada distintos del Infractor.
- **Visor**: Componente del Dashboard que dibuja la cancha, los jugadores y el balón de la Ventana, con controles de reproducción.

## Requirements

### Requirement 1: Lista de jugadas con offside

**User Story:** Como espectador, quiero elegir una jugada con offside, para ver la evidencia en una jugada real.

#### Acceptance Criteria

1. WHEN un cliente solicita `GET /api/jugadas`, THE Backend SHALL responder 200 con una lista de todas las Jugada_Offside.
2. THE Backend SHALL incluir por jugada `gameId`, `playId`, `infractor` (nflId y nombre), `equipo_defensa`, `equipo_ofensiva`, `quarter`, `down`, `yardsToGo`, `gameClock`, `s_snap`, `cruce_snap`, `alineado` y `descripcion` (`playDescription`).
3. THE Backend SHALL ordenar la lista de mayor a menor `s_snap`, con desempate por `gameId` y `playId` ascendentes.
4. WHILE el cálculo está en curso o falló, THE Backend SHALL responder igual que `GET /api/offside` (503 con `estado`).

### Requirement 2: Detalle cuadro por cuadro

**User Story:** Como espectador, quiero ver a todos los jugadores moviéndose alrededor del snap, para notar que el infractor arranca antes.

#### Acceptance Criteria

1. WHEN un cliente solicita `GET /api/jugadas/{gameId}/{playId}` de una Jugada_Offside, THE Backend SHALL responder 200 con el resumen de la jugada y sus `frames`.
2. IF la jugada no es una Jugada_Offside, THEN THE Backend SHALL responder 404 con un mensaje en español.
3. THE Backend SHALL incluir un elemento en `frames` por cada cuadro de la Ventana, en orden de `frameId`, con `frameId`, `t` y la lista de `jugadores`.
4. THE Backend SHALL incluir por jugador `nflId` (null para el balón), `x`, `y` en Coordenadas_Normalizadas redondeadas a 2 decimales, `s`, `numero` (jerseyNumber, null para el balón) y `rol` con valor `infractor`, `defensa`, `ofensiva` o `balon`.
5. THE Backend SHALL incluir `linea_golpeo_x`, la `x` normalizada del balón en el Frame_Snap.
6. THE Backend SHALL incluir `velocidad`, una lista por cuadro de la Ventana con `t`, `infractor` (su `s`) y `resto_linea` (promedio de `s` del Resto_Linea, o null si no hay).

### Requirement 3: Visor en el Dashboard

**User Story:** Como espectador, quiero ver la jugada animada y la velocidad del infractor, para entender el hallazgo sin leer tablas.

#### Acceptance Criteria

1. WHEN el Dashboard recibe la lista, THE Visor SHALL mostrar un selector de jugadas y cargar por defecto la primera (la de mayor `s_snap`).
2. THE Visor SHALL dibujar en SVG una cancha con líneas de yarda cada 5 yardas, la línea de golpeo y los jugadores como círculos con su número, con colores distintos para infractor, defensa, ofensiva y balón.
3. THE Visor SHALL ofrecer reproducir, pausar y un control deslizante para moverse por los cuadros, y SHALL mostrar el `t` del cuadro actual y una marca cuando `t == 0` (snap).
4. THE Visor SHALL mostrar una gráfica de líneas Recharts de `infractor` y `resto_linea` contra `t`, con una línea de referencia en `t = 0`.
5. THE Visor SHALL mostrar el resumen de la jugada: equipos, cuarto, down y distancia, reloj, infractor, `s_snap` y la descripción.
6. IF la petición de la lista o del detalle falla, THEN THE Visor SHALL mostrar un mensaje de error en español sin afectar al resto del Dashboard.
7. THE Visor SHALL usar `fetch('api/jugadas')` y `fetch('api/jugadas/<gameId>/<playId>')` sin diagonal inicial.

### Requirement 4: Contrato y recursos

**User Story:** Como integrante del equipo, quiero que el visor no rompa el contrato de despliegue ni haga lento el arranque.

#### Acceptance Criteria

1. THE Backend SHALL construir los datos de las Jugada_Offside en la misma lectura de tracking que `offside-endpoint`, sin volver a leer los archivos. (La spec `jugada-control` agrega una segunda pasada solo para los partidos de las jugadas control.)
2. THE Backend SHALL conservar en memoria solo las filas de la Ventana de las Jugada_Offside.
3. THE Backend SHALL no escribir archivos a disco ni agregar dependencias fuera del stack.
