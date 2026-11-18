# Implementation Plan: jugada-evidencia

## Tasks

- [x] 1. Backend
  - [x] 1.1 `claves_offside` y lectura única de tracking que devuelve filas del Frame_Snap y de la Ventana
    - _Requirements: 4.1, 4.2_
  - [x] 1.2 `normalizar` y `construir_jugadas` (resúmenes ordenados y detalles con frames y velocidad)
    - _Requirements: 1.2, 1.3, 2.3, 2.4, 2.5, 2.6_
  - [x] 1.3 Rutas `GET /api/jugadas` y `GET /api/jugadas/{gameId}/{playId}` con el control de estado y 404
    - _Requirements: 1.1, 1.4, 2.1, 2.2_
  - [x]* 1.4 Pruebas de propiedades 1 a 4 y de la API
    - _Requirements: 1.3, 2.2, 2.3, 2.4_

- [x] 2. Dashboard
  - [x] 2.1 Tipos y funciones `cargarJugadas` / `cargarJugada` con rutas relativas
    - _Requirements: 3.7_
  - [x] 2.2 `Campo` (SVG) y `GraficaVelocidad` (Recharts)
    - _Requirements: 3.2, 3.4_
  - [x] 2.3 `VisorJugada` con selector, resumen, reproducción, deslizador y manejo de errores
    - _Requirements: 3.1, 3.3, 3.5, 3.6_

- [ ] 3. Checkpoint: build, `--check` y revisión visual
