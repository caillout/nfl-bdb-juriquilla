# Requirements Document

## Introduction

Esta función agrega una vista por equipo con dos rankings: defensas (qué tanto se anticipan sus rushers y qué les cuesta) y ofensivas (qué tanto hacen que el rival se anticipe y cuántos offsides provocan, por ejemplo con hard counts del QB). También define la identidad visual por equipo que usa todo el Dashboard: siglas en una insignia con los colores oficiales, sin logos (son marcas registradas y requerirían URLs externas, prohibidas por `.kiro/steering/rules.md`). Reutiliza las definiciones de `offside-endpoint`.

Los offsides por equipo son pocos (cada defensa tiene entre 0 y 4 ligados a rushers alineados, y cada ofensiva provoca entre 0 y 9), así que un ranking por offsides sería sobre todo ruido. El ranking se ordena por el % de anticipación, que tiene entre 730 y 1,188 snaps por equipo, y los offsides se muestran como dato secundario con aviso de muestra chica.

## Glossary

- **Equipo_Defensa** de un Rusher_Alineado: el `defensiveTeam` de su jugada en `plays.csv`.
- **Equipo_Ofensiva** de un Rusher_Alineado: el `possessionTeam` de su jugada en `plays.csv`.
- **Anticipa**: Rusher_Alineado con Velocidad_Snap ≥ 1.0 yd/s (el Umbral_Scout).
- **Insignia_Equipo**: Componente del Dashboard con las siglas del equipo sobre su color primario, con borde del color secundario.
- **Paleta_Equipos**: Tabla en el código del Dashboard con el color primario y secundario de los 32 equipos, por siglas tal como vienen en los datos (por ejemplo `LA` para los Rams).

## Requirements

### Requirement 1: Ranking de defensas

**User Story:** Como analista, quiero ver qué defensas se anticipan más, para saber a quiénes les funciona y a quiénes les cuesta.

#### Acceptance Criteria

1. WHEN un cliente solicita `GET /api/equipos`, THE Backend SHALL responder 200 con `defensas` y `ofensivas`.
2. THE Backend SHALL incluir en `defensas` una entrada por Equipo_Defensa con `equipo`, `rusher_snaps`, `pct_anticipa`, `pct_presion`, `offsides` y `offsides_por_1000`, calculados sobre sus Rusher_Alineado.
3. THE Backend SHALL ordenar `defensas` de mayor a menor `pct_anticipa`, con desempate por `equipo` ascendente.

### Requirement 2: Ranking de ofensivas

**User Story:** Como analista, quiero ver qué ofensivas provocan más anticipación y offsides del rival.

#### Acceptance Criteria

1. THE Backend SHALL incluir en `ofensivas` una entrada por Equipo_Ofensiva con `equipo`, `rusher_snaps_rival` (Rusher_Alineado de las defensas que enfrentó), `pct_anticipa_rival`, `offsides_provocados` y `offsides_por_1000`.
2. THE Backend SHALL ordenar `ofensivas` de mayor a menor `offsides_por_1000`, con desempate por `pct_anticipa_rival` descendente y `equipo` ascendente.
3. THE Backend SHALL incluir en la respuesta una `nota` que explique que los offsides por equipo son pocos y deben leerse con cautela.

### Requirement 3: Vista de equipos en el Dashboard

**User Story:** Como espectador, quiero ver los rankings con la identidad de cada equipo, para ubicarlos de un vistazo.

#### Acceptance Criteria

1. THE Dashboard SHALL mostrar una sección con dos pestañas, "Defensas" y "Ofensivas", cada una con su ranking en tabla.
2. THE Dashboard SHALL mostrar cada equipo con su Insignia_Equipo.
3. THE Dashboard SHALL mostrar la `nota` de muestra chica junto a los offsides.
4. WHEN el usuario da clic en una defensa, THE Dashboard SHALL mostrar sus Jugador_Elegible (spec `perfil-jugador`) y permitir abrir su perfil.

### Requirement 4: Identidad visual por equipo

**User Story:** Como espectador, quiero que cada equipo se vea con sus colores en todo el tablero.

#### Acceptance Criteria

1. THE Dashboard SHALL definir la Paleta_Equipos en su propio código, sin cargar imágenes ni recursos externos.
2. THE Dashboard SHALL usar la Insignia_Equipo en el ranking de equipos, en el visor (equipos de la jugada) y en el perfil de jugador.
3. IF unas siglas no están en la Paleta_Equipos, THEN THE Insignia_Equipo SHALL usar gris con texto blanco.
4. THE Insignia_Equipo SHALL garantizar contraste legible entre el texto y el color primario (texto blanco u oscuro según la luminosidad del color).

### Requirement 5: Duelo del domingo

**User Story:** Como espectador del evento (el premio es ir al partido Vikings vs 49ers en la Ciudad de México), quiero ver cómo se comparan esos dos equipos con los datos del tablero.

#### Acceptance Criteria

1. THE Dashboard SHALL mostrar una sección "Duelo del domingo" con dos equipos configurables (por defecto `MIN` y `SF`), lado a lado, cada uno con su Insignia_Equipo y sus colores.
2. THE Dashboard SHALL mostrar por equipo: % de anticipación de su defensa y su lugar en el ranking, offsides cometidos, offsides que provoca su ofensiva y su lugar, y sus tres Jugador_Elegible con mayor % de anticipación, que abren su perfil al dar clic.
3. THE Dashboard SHALL indicar que los datos son de las semanas 1 a 8 de 2021 y mostrar la `nota` de muestra chica.
4. THE Dashboard SHALL calcular todo a partir de `GET /api/equipos` y `GET /api/jugadores`, sin valores fijos en el código salvo las siglas de los dos equipos.
