# Implementation Plan: jugada-control

## Tasks

- [x] 1. Backend
  - [x] 1.1 `elegir_controles` con Distancia_Situacion, desempates y `criterio`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.2_
  - [x] 1.2 `leer_ventanas` (segunda pasada) y `data_dir` en `cargar_datos`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 1.3 Extraer `_detalle_jugada`, agregar `control` al detalle y `tiene_control` a la lista
    - _Requirements: 2.1, 2.3, 2.4, 2.5_
  - [ ]* 1.4 Pruebas de propiedades 1 a 3, sin candidata y archivo ilegible
    - _Requirements: 1.x, 2.x, 3.4_

- [x] 2. Dashboard
  - [x] 2.1 `Campo` por `t` (cuadro más cercano) y línea de tiempo común en `VisorJugada`
    - _Requirements: 4.2_
  - [x] 2.2 Dos canchas lado a lado (apiladas en pantallas angostas), criterio y velocidades en el snap
    - _Requirements: 4.1, 4.4, 4.5_
  - [x] 2.3 Gráfica de velocidad con tres líneas
    - _Requirements: 4.3_

- [ ] 3. Checkpoint: pruebas, build y `--check`
