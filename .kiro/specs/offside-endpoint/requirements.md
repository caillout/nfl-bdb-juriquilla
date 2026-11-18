# Requirements Document

## Introduction

Esta función expone el endpoint `GET /api/offside` y un tablero que relacionan la velocidad de los pass rushers en el snap con los offsides defensivos. Todo se calcula al arrancar el servidor a partir de los archivos de solo lectura en `data/`, sin escribir a disco. El análisis cubre únicamente rushers alineados en la línea de golpeo. Los números de referencia previos (36,263 rusher-snaps, 50 jugadas con offside, 48 rusher-snaps, 44 alineados) pueden cambiar con la regla "solo foulName1 y foulName2", así que los criterios se verifican contra los datos y no contra valores fijos. La definición de costo del offside (bootstrap) queda fuera de alcance. La app respeta el stack y el contrato de despliegue de `.kiro/steering/rules.md`. La IA no se requiere.

## Glossary

- **Backend**: Aplicación FastAPI en `backend/main.py` que expone `app`.
- **Dashboard**: Frontend React 18 + Vite + Tailwind 3 + Recharts en `dashboard/`.
- **Data_Dir**: Primera carpeta dentro de `data/` (incluida `data/` misma) que contiene `plays.csv` y una subcarpeta `tracking/` con `tracking_<gameId>.csv` (122 archivos), además de `pffScoutingData.csv` y `players.csv`. Se busca en lugar de fijarse porque la profundidad cambia según cómo se descomprimió el zip (por ejemplo `data/nfl-big-data-bowl-regional-event-data-main/data/` o con la carpeta repetida).
- **Offside_Service**: Módulo del Backend que calcula todas las métricas al arrancar y las mantiene en memoria.
- **Frame_Snap**: `frameId` de la fila de tracking de una jugada `(gameId, playId)` cuyo `event` es `ball_snap` o `autoevent_ballsnap`.
- **Rusher**: Jugador con `pff_role` igual a `Pass Rush` (R mayúscula) en `pffScoutingData.csv`.
- **Rusher_Snap**: Tupla `(gameId, playId, nflId)` de un Rusher con posición en el Frame_Snap.
- **Cruce**: `round((x_rusher - bx) * signo, 2)`, calculado en float64, donde `bx` es la `x` de la fila `team == "football"` en el Frame_Snap, y `signo` es -1 si `playDirection == "right"` y +1 si `playDirection == "left"`. Se redondea a 2 decimales (la precisión de `x` en el tracking) para que los valores exactamente en -1.5 o 0.5 no dependan de errores de punto flotante (119 rusher-snaps caen exactamente en -1.50).
- **Rusher_Alineado**: Rusher_Snap con `-1.5 <= Cruce <= 0.5` (extremos incluidos).
- **Velocidad_Snap**: Valor de la columna `s` del Rusher en el Frame_Snap, en yd/s, sin recalcular.
- **Rango_Velocidad**: Categoría de Velocidad_Snap obtenida con `pd.cut(s, bins=[-0.01,0.25,0.5,1,2,10])`, cerrada a la derecha, con etiquetas `0-0.25`, `0.25-0.5`, `0.5-1`, `1-2` y `>2`.
- **Presión_Individual**: Condición `pff_hit + pff_hurry + pff_sack > 0` para un Rusher en una jugada, con valores vacíos tomados como 0.
- **Offside_Ligado**: Rusher_Snap cuyo `nflId` coincide con `foulNFLId1` cuando `foulName1 == "Defensive Offside"`, o con `foulNFLId2` cuando `foulName2 == "Defensive Offside"`. `foulName3` no se revisa.
- **Umbral_Clave**: Velocidad_Snap mayor que 0.5 yd/s (rangos `0.5-1`, `1-2` y `>2`), usado en el Número_Clave.
- **Umbral_Scout**: Velocidad_Snap mayor o igual que 1.0 yd/s, usado en el Top_10_Scout.
- **Número_Clave**: Par "X% de los snaps → Y% de los offsides", donde X es el porcentaje de Rusher_Alineado con Velocidad_Snap > 0.5 y Y es el porcentaje de los Offside_Ligado de Rusher_Alineado que ocurren en esos snaps.
- **Top_10_Scout**: Ranking de 10 jugadores por porcentaje de Rusher_Alineado con Velocidad_Snap >= 1.0, con mínimo 100 Rusher_Alineado por jugador.
- **Tarjeta_Clave**: Componente del Dashboard que muestra el Número_Clave.
- **Tabla_Scout**: Componente del Dashboard que muestra el Top_10_Scout.
- **Frase_Broadcaster**: Frase de texto del Dashboard construida con valores calculados.

## Requirements

### Requirement 1: Carga de datos al arrancar

**User Story:** Como integrante del equipo, quiero que el servidor cargue y calcule los datos al arrancar, para que la API responda sin escribir a disco.

#### Acceptance Criteria

1. WHEN el Backend arranca, THE Offside_Service SHALL leer `tracking/tracking_<gameId>.csv`, `pffScoutingData.csv`, `plays.csv` y `players.csv` desde Data_Dir y calcular todas las métricas en memoria.
2. THE Offside_Service SHALL abrir los archivos de Data_Dir solo en modo lectura y no escribir ningún archivo en disco.
3. THE Offside_Service SHALL resolver Data_Dir con una ruta relativa a la raíz del proyecto.
4. THE Backend SHALL exponer `app` en `backend/main.py` con `GET /health` que responde `{"status": "ok"}`.
5. THE Backend SHALL servir todas las rutas de la API bajo el prefijo `/api`.
6. IF falta un archivo requerido de Data_Dir o no se puede leer, THEN THE Backend SHALL registrar el error sin credenciales y responder `GET /api/offside` con código 503 y un mensaje descriptivo.
7. IF un archivo `tracking_<gameId>.csv` no se puede leer, THEN THE Offside_Service SHALL omitir ese juego, registrar el `gameId` omitido y continuar con los demás.

### Requirement 2: Snap, balón y alineación

**User Story:** Como analista, quiero identificar el snap, el balón y la alineación de cada rusher, para medir solo rushers alineados en la línea.

#### Acceptance Criteria

1. THE Offside_Service SHALL determinar el Frame_Snap de cada `(gameId, playId)` con el `frameId` de la fila cuyo `event` es `ball_snap` o `autoevent_ballsnap`.
2. IF una jugada no tiene ninguna fila con `event` igual a `ball_snap` o `autoevent_ballsnap`, THEN THE Offside_Service SHALL excluir esa jugada de todos los cálculos.
3. IF una jugada no tiene fila con `team == "football"` en el Frame_Snap, THEN THE Offside_Service SHALL excluir esa jugada de todos los cálculos.
4. THE Offside_Service SHALL calcular el Cruce usando el centro del balón como referencia y el `signo` definido en el Glossary.
5. THE Offside_Service SHALL clasificar como Rusher_Alineado a todo Rusher_Snap con `-1.5 <= Cruce <= 0.5`, incluyendo ambos extremos.
6. THE Offside_Service SHALL identificar a los Rusher mediante `pff_role == "Pass Rush"` con R mayúscula.
7. IF un Rusher no tiene posición en el Frame_Snap, THEN THE Offside_Service SHALL excluir ese Rusher de esa jugada.

### Requirement 3: Velocidad, presión y offside por rusher

**User Story:** Como analista, quiero asignar velocidad, presión y offside a cada rusher alineado, para agregar las métricas.

#### Acceptance Criteria

1. THE Offside_Service SHALL tomar la Velocidad_Snap de la columna `s` en el Frame_Snap sin recalcularla.
2. THE Offside_Service SHALL asignar cada Rusher_Alineado a un Rango_Velocidad con `pd.cut(s, bins=[-0.01,0.25,0.5,1,2,10])` cerrado a la derecha y las etiquetas `0-0.25`, `0.25-0.5`, `0.5-1`, `1-2` y `>2`.
3. THE Offside_Service SHALL calcular la Presión_Individual de cada Rusher_Alineado a partir de `pff_hit`, `pff_hurry` y `pff_sack`, con valores vacíos tomados como 0.
4. THE Offside_Service SHALL marcar un offside en un Rusher_Alineado solo cuando exista un Offside_Ligado, revisando únicamente `foulName1`/`foulNFLId1` y `foulName2`/`foulNFLId2`.
5. THE Offside_Service SHALL ligar los offsides a los Rusher_Snap mediante un left join en el que los Rusher_Snap sin Offside_Ligado tengan 0 offsides.
6. THE Offside_Service SHALL aplicar la misma regla de Offside_Ligado al conteo por Rango_Velocidad, por down y por jugador.

### Requirement 4: Métricas por rango de velocidad

**User Story:** Como analista, quiero las métricas por rango de velocidad, para ver cómo cambian los offsides con la velocidad en el snap.

#### Acceptance Criteria

1. WHEN un cliente solicita `GET /api/offside`, THE Backend SHALL responder con código 200 y un JSON que incluya una entrada por cada uno de los cinco Rango_Velocidad.
2. THE Backend SHALL incluir en cada entrada de Rango_Velocidad los campos `rusher_snaps`, `offsides`, `offsides_por_1000` y `pct_presion`, calculados solo sobre Rusher_Alineado.
3. THE Offside_Service SHALL calcular `offsides_por_1000` como `offsides / rusher_snaps * 1000` y `pct_presion` como el porcentaje de Rusher_Alineado del rango con Presión_Individual.
4. IF un Rango_Velocidad tiene 0 `rusher_snaps`, THEN THE Offside_Service SHALL devolver `offsides_por_1000` y `pct_presion` como `null`.
5. THE Offside_Service SHALL calcular la suma de `rusher_snaps` de los cinco rangos igual al total de Rusher_Alineado y la suma de `offsides` igual al total de offsides ligados a Rusher_Alineado.

### Requirement 5: Top 10 Scout

**User Story:** Como scout, quiero el top 10 de jugadores que salen en movimiento, para identificar a quién vigilar.

#### Acceptance Criteria

1. THE Offside_Service SHALL calcular para cada jugador el porcentaje de sus Rusher_Alineado con Velocidad_Snap mayor o igual que 1.0 yd/s (Umbral_Scout).
2. THE Offside_Service SHALL incluir en el Top_10_Scout solo a jugadores con al menos 100 Rusher_Alineado.
3. THE Backend SHALL devolver el Top_10_Scout ordenado de mayor a menor por porcentaje de snaps en movimiento, con 10 jugadores o con todos los elegibles si son menos de 10.
4. THE Backend SHALL incluir por jugador `nflId`, nombre, `rusher_snaps`, porcentaje de snaps en movimiento, `pct_presion` y `offsides`.
5. THE Backend SHALL incluir en la respuesta una etiqueta que indique el umbral usado, "s >= 1.0 yd/s" para el Top_10_Scout.
6. THE Offside_Service SHALL contar una Velocidad_Snap de exactamente 1.0 como en movimiento en el Top_10_Scout y como perteneciente al Rango_Velocidad `0.5-1` en las métricas por rango.
7. THE Backend SHALL documentar en la respuesta o en el README que el Número_Clave usa Velocidad_Snap > 0.5 y el Top_10_Scout usa Velocidad_Snap >= 1.0 por decisión deliberada.

### Requirement 6: Offsides por down

**User Story:** Como analista, quiero la tasa de offsides por down, para ver si el down cambia el riesgo sin que lo distorsione cuántos snaps hay en cada down.

#### Acceptance Criteria

1. THE Offside_Service SHALL obtener el down de cada jugada desde `plays.csv`.
2. THE Backend SHALL devolver siempre cuatro entradas, una por down 1, 2, 3 y 4 en ese orden, con `down`, `rusher_snaps`, `offsides`, `offsides_por_1000` y `pct_del_total`.
3. THE Offside_Service SHALL calcular `offsides_por_1000` como `offsides / rusher_snaps * 1000`, donde `rusher_snaps` es el número de Rusher_Alineado de ese down (misma unidad que las métricas por rango).
4. THE Offside_Service SHALL calcular `pct_del_total` como `offsides` del down entre la suma de `offsides` de los downs 1 a 4, por 100.
5. IF un down no tiene Rusher_Alineado, THEN THE Offside_Service SHALL devolver `offsides_por_1000` como `null`; IF la suma de offsides de los downs 1 a 4 es 0, THEN `pct_del_total` SHALL ser `null`.
6. THE Offside_Service SHALL excluir de `por_down` los Rusher_Alineado cuyo down no sea 1, 2, 3 o 4 (en los datos hay jugadas con `down = 0`) y SHALL reportarlos en `totales.sin_down_valido` con sus `rusher_snaps` y `offsides`.
7. THE Dashboard SHALL mostrar una gráfica de barras de `offsides_por_1000` por down.

### Requirement 7: Número clave

**User Story:** Como espectador del tablero, quiero un número clave calculado de los datos, para entender el hallazgo de un vistazo.

#### Acceptance Criteria

1. THE Offside_Service SHALL calcular X como el porcentaje de Rusher_Alineado con Velocidad_Snap > 0.5 (Umbral_Clave).
2. THE Offside_Service SHALL calcular Y como el porcentaje de los offsides ligados a Rusher_Alineado que ocurren en Rusher_Alineado con Velocidad_Snap > 0.5.
3. THE Backend SHALL incluir en la respuesta X, Y y la etiqueta del umbral "s > 0.5 yd/s".
4. IF el total de offsides ligados a Rusher_Alineado es 0, THEN THE Offside_Service SHALL devolver Y como `null`.
5. THE Backend SHALL calcular X, Y y todos los textos derivados a partir de los datos, sin valores fijos en el código.

### Requirement 8: Presentación en el Dashboard

**User Story:** Como espectador del tablero, quiero ver gráfica, tarjeta, tabla y frase, para presentar el hallazgo.

#### Acceptance Criteria

1. WHEN el Dashboard carga, THE Dashboard SHALL solicitar los datos con `fetch('api/offside')`, sin diagonal inicial y sin `localhost` ni URLs absolutas.
2. WHEN el Dashboard recibe la respuesta, THE Dashboard SHALL mostrar una gráfica de barras Recharts de `offsides_por_1000` por Rango_Velocidad en el orden `0-0.25`, `0.25-0.5`, `0.5-1`, `1-2`, `>2`.
3. WHEN el Dashboard recibe la respuesta, THE Tarjeta_Clave SHALL mostrar el Número_Clave con el formato "X% de los snaps → Y% de los offsides" y la etiqueta del umbral "s > 0.5 yd/s".
4. WHEN el Dashboard recibe la respuesta, THE Tabla_Scout SHALL mostrar el Top_10_Scout con la etiqueta del umbral "s >= 1.0 yd/s".
5. WHEN el Dashboard recibe la respuesta, THE Dashboard SHALL mostrar la Frase_Broadcaster construida con valores calculados de la respuesta.
6. IF `fetch('api/offside')` falla o devuelve un código distinto de 200, THEN THE Dashboard SHALL mostrar un mensaje de error en español y permanecer funcional.
7. THE Dashboard SHALL referenciar imágenes, CSS y enlaces con rutas relativas sin diagonal inicial.

### Requirement 9: Contrato de despliegue

**User Story:** Como integrante del equipo, quiero que el proyecto cumpla el contrato de despliegue, para que AWS lo hospede tal cual.

#### Acceptance Criteria

1. THE Dashboard SHALL generar `dashboard/dist` con `vite build`.
2. THE Dashboard SHALL configurar en `vite.config.ts` `base: './'` y un proxy de `/api` hacia `http://localhost:8000`.
3. THE Backend SHALL servir `dashboard/dist` y la API en la misma URL y puerto.
4. THE Backend SHALL usar solo las dependencias y versiones del stack fijo de `.kiro/steering/rules.md`.
5. THE Backend SHALL no requerir IA ni servicios de AWS para calcular y servir `GET /api/offside`.
6. THE Dashboard SHALL usar Tailwind CSS 3 sin la sintaxis de Tailwind 4.

### Requirement 10: Cálculo en segundo plano

**User Story:** Como integrante del equipo, quiero que el servidor responda `/health` desde el primer segundo, para que el hosting no lo dé por caído mientras se leen los 122 archivos de tracking (unos 15 s).

#### Acceptance Criteria

1. WHEN el Backend arranca, THE Backend SHALL iniciar el cálculo en un hilo en segundo plano y quedar listo para recibir peticiones sin esperar a que termine.
2. WHILE el cálculo está en curso, THE Backend SHALL responder `GET /health` con `{"status": "ok"}`.
3. WHILE el cálculo está en curso, THE Backend SHALL responder las rutas de datos bajo `/api` con código 503, el encabezado `Retry-After` y `detail = {"estado": "calculando", "mensaje": <texto>}`.
4. IF el cálculo falla, THEN THE Backend SHALL responder las rutas de datos con 503 y `detail = {"estado": "error", "mensaje": <texto sin credenciales>}`.
5. WHEN el Dashboard recibe 503 con `estado == "calculando"`, THE Dashboard SHALL mostrar "Calculando…" y reintentar automáticamente cada 3 s durante un máximo de 2 minutos.

### Requirement 11: Análisis por presión en la gráfica de rangos

**User Story:** Como espectador, quiero ver en la misma gráfica el riesgo (offsides por 1,000) y la recompensa (% de presión) de cada rango, para entender el dilema de anticipar el snap.

#### Acceptance Criteria

1. THE Dashboard SHALL mostrar en la gráfica de rangos barras de `offsides_por_1000` (eje izquierdo) y una línea de `pct_presion` (eje derecho), en el orden fijo de los rangos.
2. THE Dashboard SHALL indicar el número de `rusher_snaps` de cada rango en el tooltip, para que se vea el tamaño de muestra de los rangos altos.
