# Implementation Plan: equipos

## Tasks

- [x] 1. Backend
  - [x] 1.1 `metricas_equipos` (defensas, ofensivas, orden y nota)
    - _Requirements: 1.2, 1.3, 2.1, 2.2, 2.3_
  - [x] 1.2 Ruta `GET /api/equipos`
    - _Requirements: 1.1_
  - [ ]* 1.3 Pruebas de propiedades 1 y 2 y API
    - _Requirements: 1.x, 2.x_

- [x] 2. Dashboard
  - [x] 2.1 `equipos.ts` (Paleta_Equipos, `colorTexto`) e `InsigniaEquipo`
    - _Requirements: 4.1, 4.3, 4.4_
  - [x] 2.2 `SeccionEquipos` con pestañas, nota y clic en defensa que muestra sus jugadores
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 2.3 Insignias en el visor y en el perfil
    - _Requirements: 4.2_
  - [x] 2.4 `DueloDomingo` (MIN vs SF por defecto) con rankings, offsides y sus tres rushers que más se anticipan
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 3. Checkpoint: pruebas, build y `--check`
