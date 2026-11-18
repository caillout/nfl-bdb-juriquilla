# Implementation Plan: offside-endpoint

## Overview

Plan en Python (backend, FastAPI + pandas) y TypeScript (dashboard, React + Recharts). Primero se construye el módulo puro `backend/offside_service.py` por funciones, luego se conecta a `backend/main.py` y por último el dashboard. Las pruebas son opcionales (pytest, sin dependencias nuevas, generadores con `numpy.random.default_rng`). El scaffolding existente de `backend/main.py` y `dashboard/` se revisa y se ajusta, no se recrea.

## Tasks

- [x] 1. Preparar el módulo de servicio y los modelos
  - [x] 1.1 Crear `backend/offside_service.py` con constantes, `DatosNoDisponibles` y modelos Pydantic
    - Constantes: `RANGOS_ETIQUETAS`, `RANGOS_BINS`, `UMBRAL_CLAVE`, `UMBRAL_SCOUT`, `MIN_SNAPS_SCOUT`, `CRUCE_MIN`, `CRUCE_MAX`
    - Modelos `Rango`, `NumeroClave`, `JugadorScout`, `Top10Scout`, `PorDown`, `Totales`, `OffsideResponse` (pueden vivir en `backend/models.py`)
    - Helper para convertir `NaN` a `None`
    - _Requirements: 4.2, 4.4, 5.4, 5.5, 6.2, 7.3, 9.4_

- [x] 2. Implementar funciones puras de cálculo
  - [x] 2.1 Implementar `frame_snap`, `rushers_en_snap`, `calcular_cruce` y `es_alineado`
    - Snap por `ball_snap`/`autoevent_ballsnap`; excluir jugadas sin snap o sin fila `football`; `pff_role == "Pass Rush"`; excluir rushers sin posición
    - Cruce `(x - bx) * signo`, alineado con `-1.5 <= cruce <= 0.5`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ]* 2.2 Escribir pruebas de propiedad para selección de Rusher_Snap
    - **Property 1: Selección de Rusher_Snap**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.6, 2.7**

  - [ ]* 2.3 Escribir pruebas de propiedad para cruce y alineación
    - **Property 2: Cruce y alineación**
    - **Validates: Requirements 2.4, 2.5**

  - [x] 2.4 Implementar `rango_velocidad`, presión individual y `ligar_offsides`
    - `pd.cut` con `RANGOS_BINS` y etiquetas, `right=True`; `s` sin recalcular
    - Presión `pff_hit + pff_hurry + pff_sack > 0` con vacíos como 0
    - Offside_Ligado solo con `foulName1/foulNFLId1` y `foulName2/foulNFLId2`; left join sin duplicar filas; `nflId` como `Int64`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 2.5 Escribir pruebas de propiedad para rangos y umbrales
    - **Property 3: Asignación de Rango_Velocidad y umbrales**
    - **Validates: Requirements 3.1, 3.2, 5.6**

  - [ ]* 2.6 Escribir pruebas de propiedad para presión individual
    - **Property 4: Presión_Individual**
    - **Validates: Requirements 3.3**

  - [ ]* 2.7 Escribir pruebas de propiedad para vinculación de offsides
    - **Property 5: Vinculación de offsides**
    - **Validates: Requirements 3.4, 3.5, 3.6**

  - [x] 2.8 Implementar `metricas_por_rango`, `metricas_por_down`, `top10_scout` y `numero_clave`
    - Cinco rangos en orden; `offsides_por_1000`, `pct_presion`, `pct_offsides` en `null` cuando no hay snaps
    - Top 10 con mínimo 100 snaps, `s >= 1.0`, orden descendente, nombre desde `players.csv`
    - X y Y con `s > 0.5`; Y `null` si no hay offsides; X `null` si no hay alineados
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 2.9 Escribir pruebas de propiedad para métricas por rango
    - **Property 6: Métricas por rango**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

  - [ ]* 2.10 Escribir pruebas de propiedad para Top_10_Scout
    - **Property 7: Top_10_Scout**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

  - [ ]* 2.11 Escribir pruebas de propiedad para offsides por down
    - **Property 8: Offsides por down**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

  - [ ]* 2.12 Escribir pruebas de propiedad para Número_Clave
    - **Property 9: Número_Clave**
    - **Validates: Requirements 7.1, 7.2, 7.4, 7.5**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Carga de datos y ensamblado de la respuesta
  - [x] 4.1 Implementar `cargar_datos` y `calcular_metricas`
    - Ruta de `Data_Dir` relativa a la raíz; lectura solo de columnas necesarias, un juego a la vez, conservando solo filas del Frame_Snap
    - Omitir y registrar `tracking_<gameId>.csv` ilegibles (`juegos_omitidos`); `DatosNoDisponibles` si falta un CSV requerido o no hay tracking legible; sin escribir a disco ni registrar credenciales
    - Armar `rangos`, `numero_clave`, `top10_scout`, `por_down`, `totales` y `nota_umbrales`
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 1.7, 5.7, 7.5_

- [x] 5. Backend FastAPI
  - [x] 5.1 Actualizar `backend/main.py`
    - Conservar `cargar_env()` del contrato si ya existe; `lifespan` que calcula y guarda `app.state.resultado` o `app.state.error`
    - `GET /health` → `{"status": "ok"}`; `GET /api/offside` con `response_model=OffsideResponse` y 503 con mensaje descriptivo
    - Montar `StaticFiles` de `dashboard/dist` al final y solo si existe
    - _Requirements: 1.1, 1.4, 1.5, 1.6, 9.3, 9.4, 9.5_

  - [ ]* 5.2 Escribir pruebas de ejemplo de la API con `TestClient`
    - `/health`, 200 con cinco rangos y etiquetas de umbral, 503 sin `plays.csv`, juego corrupto omitido, rutas bajo `/api`
    - _Requirements: 1.4, 1.5, 1.6, 1.7, 4.1, 5.5, 7.3_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Dashboard
  - [x] 7.1 Verificar configuración de `vite.config.ts`, Tailwind 3 e `index.css`
    - `base: './'`, proxy `/api` a `http://localhost:8000`, directivas `@tailwind`, sin sintaxis de Tailwind 4
    - _Requirements: 9.1, 9.2, 9.6_

  - [x] 7.2 Crear `src/api.ts`, tipos de respuesta y `src/frase.ts`
    - `cargarOffside()` con `fetch('api/offside')` y error si `!res.ok`
    - `construirFrase(datos)` pura, tolerante a `null`
    - _Requirements: 8.1, 8.5_

  - [ ]* 7.3 Escribir verificación de `construirFrase`
    - **Property 10: Frase_Broadcaster**
    - Sin runner nuevo: revisión manual o chequeo mediante `tsc`, no se agrega Vitest
    - **Validates: Requirements 8.5**

  - [x] 7.4 Crear `GraficaRangos`, `TarjetaClave` y `TablaScout`
    - Barras Recharts de `offsides_por_1000` en el orden fijo de rangos
    - Tarjeta "X% de los snaps → Y% de los offsides" con etiqueta `s > 0.5 yd/s`; tabla con etiqueta `s >= 1.0 yd/s`; "s/d" para `null`
    - _Requirements: 8.2, 8.3, 8.4_

  - [x] 7.5 Integrar en `src/App.tsx` con estados de carga y error
    - Mensaje de error en español si falla el fetch o el código no es 200; resto de la página funcional; rutas relativas sin diagonal inicial; mostrar `nota_umbrales`
    - _Requirements: 5.7, 8.1, 8.5, 8.6, 8.7_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Las sub-tareas con `*` son opcionales (pytest, sin Hypothesis ni otras dependencias).
- Cada tarea referencia requisitos para trazabilidad.
- Los valores de referencia previos no se codifican; todo sale de los datos.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "7.1"] },
    { "id": 1, "tasks": ["2.1", "7.2"] },
    { "id": 2, "tasks": ["2.4", "7.4", "7.3"] },
    { "id": 3, "tasks": ["2.8", "2.2", "2.3"] },
    { "id": 4, "tasks": ["4.1", "2.5", "2.6", "2.7"] },
    { "id": 5, "tasks": ["5.1", "2.9", "2.10", "2.11", "2.12"] },
    { "id": 6, "tasks": ["5.2", "7.5"] }
  ]
}
```
