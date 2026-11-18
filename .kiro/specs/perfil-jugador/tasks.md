# Implementation Plan: perfil-jugador

## Tasks

- [x] 1. Backend
  - [x] 1.1 Columnas de ficha en `COLS_PLAYERS` y `_edad`
    - _Requirements: 2.3_
  - [x] 1.2 `construir_perfiles` (lista ordenada, ficha, stats, distribución, jugadas con offside)
    - _Requirements: 1.2, 1.3, 2.3, 2.4, 2.5, 2.6_
  - [x] 1.3 Rutas `GET /api/jugadores` y `GET /api/jugadores/{nflId}` con 404
    - _Requirements: 1.1, 2.1, 2.2_
  - [ ]* 1.4 Pruebas de propiedades 1 a 3, edad y API
    - _Requirements: 1.x, 2.x_

- [x] 2. Dashboard
  - [x] 2.1 `AvatarJugador` y `BuscadorJugadores`
    - _Requirements: 3.1, 3.2_
  - [x] 2.2 `PanelPerfil` con ficha, stats, gráfica de distribución, presión y aviso de muestra chica
    - _Requirements: 3.3, 3.4, 3.6, 3.7_
  - [x] 2.3 Abrir desde el top 10 y el visor; "Ver en el visor" con scroll
    - _Requirements: 3.1, 3.5_

- [ ] 3. Checkpoint: pruebas, build y `--check`
