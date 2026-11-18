# Requirements Document

## Introduction

Esta función agrega un perfil interactivo de cada pass rusher con muestra suficiente: su ficha (con avatar en los colores de su equipo), sus estadísticas de anticipación, presión y offsides, la distribución de su velocidad en el snap comparada con la liga, y sus jugadas con offside enlazadas al visor. Se abre desde el top 10, desde el infractor del visor o con un buscador. No usa fotos (no vienen en los datos y requerirían URLs externas, prohibidas por `.kiro/steering/rules.md`). Reutiliza las definiciones de `offside-endpoint`.

## Glossary

- **Jugador_Elegible**: Rusher con al menos 100 Rusher_Alineado (el mismo mínimo del Top_10_Scout).
- **Anticipa**: Rusher_Alineado con Velocidad_Snap ≥ 1.0 yd/s (el Umbral_Scout).
- **Equipo_Jugador**: El `defensiveTeam` de `plays.csv` más frecuente entre los Rusher_Alineado del jugador.
- **Numero_Jugador**: El `jerseyNumber` más frecuente del jugador en el Frame_Snap de sus Rusher_Alineado.
- **Edad**: Años cumplidos al 2021-09-09 (inicio de la temporada) según `birthDate` de `players.csv`.
- **Percentil_Anticipacion**: Porcentaje de Jugador_Elegible con un % de Anticipa menor o igual al del jugador.
- **Panel_Perfil**: Componente del Dashboard que muestra el perfil.

## Requirements

### Requirement 1: Lista de jugadores

**User Story:** Como scout, quiero buscar a cualquier rusher con muestra suficiente, para abrir su perfil.

#### Acceptance Criteria

1. WHEN un cliente solicita `GET /api/jugadores`, THE Backend SHALL responder 200 con todos los Jugador_Elegible.
2. THE Backend SHALL incluir por jugador `nflId`, `nombre`, `equipo`, `posicion`, `numero`, `rusher_snaps`, `pct_anticipa`, `pct_presion` y `offsides`.
3. THE Backend SHALL ordenar la lista de mayor a menor `pct_anticipa`, con desempate por `rusher_snaps` descendente y `nflId` ascendente (el mismo orden del Top_10_Scout).

### Requirement 2: Perfil del jugador

**User Story:** Como scout, quiero ver las estadísticas de un rusher, para entender cómo sale en el snap y qué le cuesta.

#### Acceptance Criteria

1. WHEN un cliente solicita `GET /api/jugadores/{nflId}` de un Jugador_Elegible, THE Backend SHALL responder 200 con `ficha`, `stats`, `distribucion` y `jugadas_offside`.
2. IF el `nflId` no es un Jugador_Elegible, THEN THE Backend SHALL responder 404 con un mensaje en español.
3. THE Backend SHALL incluir en `ficha`: `nombre`, `posicion` (`officialPosition`), `equipo`, `numero`, `estatura` (texto de `height`, por ejemplo "6-4"), `peso` (libras), `edad` y `universidad`; los campos sin dato SHALL ser `null`.
4. THE Backend SHALL incluir en `stats`: `rusher_snaps`, `pct_anticipa`, `percentil_anticipacion`, `velocidad_media_snap`, `pct_presion`, `offsides`, y la presión partida en `anticipando` y `sin_anticipar`, cada una con `snaps` y `pct_presion` (`null` si `snaps` es 0).
5. THE Backend SHALL incluir en `distribucion` una entrada por Rango_Velocidad, en el orden fijo, con `pct_jugador` (% de sus Rusher_Alineado en ese rango) y `pct_liga` (% de todos los Rusher_Alineado en ese rango).
6. THE Backend SHALL incluir en `jugadas_offside` las Jugada_Offside del jugador con `gameId`, `playId`, `s_snap` y `rival`.

### Requirement 3: Panel de perfil en el Dashboard

**User Story:** Como espectador, quiero abrir el perfil con un clic y verlo sin salir de la página.

#### Acceptance Criteria

1. THE Dashboard SHALL abrir el Panel_Perfil al dar clic en un jugador del Top_10_Scout, en el nombre del infractor en el visor, o al elegirlo en un buscador por nombre o siglas del equipo.
2. THE Panel_Perfil SHALL mostrar un avatar con el `numero` del jugador sobre los colores de su `equipo` (ver spec `equipos`), sin fotos.
3. THE Panel_Perfil SHALL mostrar la ficha, las estadísticas, una gráfica de barras Recharts de `distribucion` (jugador contra liga) y la presión anticipando contra sin anticipar.
4. IF `stats.anticipando.snaps` es menor que 10, THEN THE Panel_Perfil SHALL mostrar el aviso "Muestra chica: solo N snaps anticipando".
5. THE Panel_Perfil SHALL listar las `jugadas_offside` con un botón "Ver en el visor" que selecciona esa jugada en el visor y lleva la vista hasta él.
6. THE Panel_Perfil SHALL cerrarse con un botón, con la tecla Escape y al dar clic fuera de él, y SHALL ser usable en pantallas angostas.
7. IF la petición del perfil falla, THEN THE Panel_Perfil SHALL mostrar un mensaje de error en español sin afectar al resto del Dashboard.
