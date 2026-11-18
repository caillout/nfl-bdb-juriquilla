# Requirements Document

## Introduction

Esta función agrega al visor de `jugada-evidencia` una jugada control: el mismo Infractor, en una jugada sin offside en la que estaba quieto en el snap y en una situación de juego parecida. Las dos jugadas se muestran lado a lado y sincronizadas en el snap, para que la diferencia se vea en el mismo jugador y no entre jugadores distintos. Reutiliza las definiciones de `offside-endpoint` (Frame_Snap, Rusher_Alineado, Velocidad_Snap, Offside_Ligado) y de `jugada-evidencia` (Jugada_Offside, Infractor, Ventana, t, Coordenadas_Normalizadas, Resto_Linea). Respeta `.kiro/steering/rules.md`.

## Glossary

- **Candidata_Control**: Rusher_Alineado del mismo `nflId` que el Infractor, en una jugada distinta, con `offside = 0` y Velocidad_Snap ≤ 0.25 yd/s (el rango "quieto" `0-0.25`).
- **Distancia_Situacion**: `10 * |down_candidata - down_offside| + |yardsToGo_candidata - yardsToGo_offside|`. Pondera más el down que la distancia.
- **Jugada_Control**: La Candidata_Control con menor Distancia_Situacion. Desempates, en orden: (1) mismo `gameId` que la Jugada_Offside, (2) menor Velocidad_Snap, (3) menor `gameId`, (4) menor `playId`.
- **Visor_Comparado**: Vista del Dashboard con dos canchas (offside y control) y una gráfica de velocidad común.

## Requirements

### Requirement 1: Selección de la jugada control

**User Story:** Como espectador, quiero comparar al infractor consigo mismo en una jugada normal, para ver que la diferencia es su arranque y no el jugador.

#### Acceptance Criteria

1. THE Backend SHALL elegir para cada Jugada_Offside una Jugada_Control según el Glossary.
2. THE Backend SHALL considerar como Candidata_Control solo jugadas en las que el Infractor es Rusher_Alineado, sin Offside_Ligado y con Velocidad_Snap ≤ 0.25.
3. IF el Infractor no tiene ninguna Candidata_Control, THEN THE Backend SHALL devolver `control = null` para esa jugada.
4. THE Backend SHALL ser determinista: con los mismos datos, la Jugada_Control elegida es siempre la misma.

### Requirement 2: Datos de la jugada control

**User Story:** Como espectador, quiero ver la jugada control con el mismo detalle que la de offside, para compararlas cuadro por cuadro.

#### Acceptance Criteria

1. WHEN un cliente solicita `GET /api/jugadas/{gameId}/{playId}`, THE Backend SHALL incluir el campo `control` con el mismo formato que el detalle de `jugada-evidencia` (resumen, `linea_golpeo_x`, `frames`, `velocidad`), o `null` si no hay Jugada_Control.
2. THE Backend SHALL incluir en `control` la `distancia_situacion` y el texto `criterio` que explica por qué se eligió (por ejemplo, "Mismo jugador, mismo partido, 3er y 7, quieto en el snap").
3. THE Backend SHALL calcular `frames` y `velocidad` de la Jugada_Control con la misma Ventana, la misma normalización y la misma definición de Resto_Linea que la Jugada_Offside.
4. THE Backend SHALL marcar al Infractor en la Jugada_Control con `rol = "infractor"`, aunque en esa jugada no cometió falta, para que el Dashboard lo resalte igual.
5. THE Backend SHALL incluir `GET /api/jugadas` sin cambios en su formato, más el campo `tiene_control` (booleano) por jugada.

### Requirement 3: Lectura de los datos de control

**User Story:** Como integrante del equipo, quiero que la jugada control no haga lento ni frágil el arranque.

#### Acceptance Criteria

1. THE Backend SHALL elegir las Jugada_Control después de la primera lectura del tracking (cuando ya se conoce la Velocidad_Snap) y SHALL leer en una segunda pasada solo los archivos `tracking_<gameId>.csv` de los partidos que contienen Jugada_Control.
2. THE Backend SHALL conservar en memoria solo las filas de la Ventana de las Jugada_Control.
3. THE Backend SHALL hacer la segunda pasada dentro del mismo cálculo en segundo plano, de modo que `/health` siga respondiendo y las rutas de datos sigan en 503 `calculando` hasta que termine.
4. IF un archivo de la segunda pasada no se puede leer, THEN THE Backend SHALL devolver `control = null` para las jugadas afectadas y registrar el `gameId`, sin fallar el cálculo completo.

### Requirement 4: Visor comparado

**User Story:** Como espectador, quiero ver las dos jugadas al mismo tiempo, para notar que en la de offside arranca antes y en la control no.

#### Acceptance Criteria

1. WHEN la jugada seleccionada tiene `control`, THE Visor_Comparado SHALL mostrar dos canchas: "Con offside" y "Control: sin offside", lado a lado en pantallas anchas y una sobre otra en pantallas angostas.
2. THE Visor_Comparado SHALL sincronizar ambas canchas por `t` (tiempo relativo al snap): un solo control de reproducción, pausa y deslizador mueve las dos. IF una jugada no tiene cuadro para el `t` actual, THEN su cancha SHALL mostrar el cuadro más cercano.
3. THE Visor_Comparado SHALL mostrar una gráfica de velocidad con tres líneas contra `t`: Infractor en la Jugada_Offside, Infractor en la Jugada_Control y Resto_Linea de la Jugada_Offside, con una línea de referencia en `t = 0`.
4. THE Visor_Comparado SHALL mostrar el `criterio` de la Jugada_Control y la velocidad en el snap de ambas jugadas.
5. WHEN la jugada seleccionada no tiene `control`, THE Visor SHALL mostrar solo la jugada con offside y un aviso de que no hay jugada control.
