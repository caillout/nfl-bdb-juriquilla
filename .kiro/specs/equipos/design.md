# Design Document

## Overview

Agregación de `alineados` por `defensiveTeam` y por `possessionTeam` de `plays.csv`, calculada una vez en segundo plano. La identidad visual vive solo en el Dashboard: una tabla de colores por siglas y un componente de insignia.

## Components and Interfaces

`backend/offside_service.py`
- `metricas_equipos(alineados, plays) -> dict` con `defensas`, `ofensivas` y `nota`.

`backend/main.py`
- `GET /api/equipos`.

`dashboard/src`
- `equipos.ts`: `PALETA_EQUIPOS: Record<string, {primario, secundario}>` con los 32 equipos y `colorTexto(hex)` (blanco u oscuro según la luminancia relativa, umbral 0.5).
- `components/InsigniaEquipo.tsx`: siglas sobre el color primario con borde del secundario.
- `components/SeccionEquipos.tsx`: pestañas "Defensas" y "Ofensivas"; al dar clic en una defensa muestra sus Jugador_Elegible (de `api/jugadores`, filtrados por `equipo`) y abre su perfil.

## Data Models

```python
class EquipoDefensa(BaseModel):
    equipo: str; rusher_snaps: int; pct_anticipa: float; pct_presion: float
    offsides: int; offsides_por_1000: float

class EquipoOfensiva(BaseModel):
    equipo: str; rusher_snaps_rival: int; pct_anticipa_rival: float
    offsides_provocados: int; offsides_por_1000: float

class EquiposResponse(BaseModel):
    defensas: list[EquipoDefensa]; ofensivas: list[EquipoOfensiva]; nota: str
```

## Error Handling

| Situación | Comportamiento |
|---|---|
| Siglas sin color en la paleta | Gris `#6b7280` con texto blanco |
| Cálculo en curso o fallido | 503 con `estado` |

## Correctness Properties

### Property 1: Conservación
For any `alineados`, la suma de `rusher_snaps` de las defensas y de `rusher_snaps_rival` de las ofensivas es igual al total de Rusher_Alineado, y la suma de `offsides` y de `offsides_provocados` es igual al total de offsides ligados.

**Validates: Requirements 1.2, 2.1**

### Property 2: Orden
For any respuesta, `defensas` está ordenada por `pct_anticipa` desc y `equipo` asc, y `ofensivas` por `offsides_por_1000` desc, `pct_anticipa_rival` desc y `equipo` asc.

**Validates: Requirements 1.3, 2.2**

## Testing Strategy

Pruebas pytest con datos sintéticos para las propiedades 1 y 2 y la API. Con datos reales: 32 defensas y 32 ofensivas, y la conservación contra los totales de `/api/offside`.
