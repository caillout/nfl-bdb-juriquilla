# Design Document

## Overview

Los perfiles se calculan una vez en el mismo cálculo en segundo plano, a partir de `alineados`, `tracking_snap` (para el número de jersey), `plays.csv` (equipo) y `players.csv` (ficha). Se guardan en memoria: una lista y un diccionario `nflId -> perfil`.

## Components and Interfaces

`backend/offside_service.py`
- `construir_perfiles(datos, alineados, jugadas) -> (lista, detalles)`.
- `COLS_PLAYERS` agrega `height`, `weight`, `birthDate`, `collegeName`, `officialPosition` (se leen si existen).
- `_edad(birthDate, referencia=2021-09-09) -> int | None`.

`backend/main.py`
- `GET /api/jugadores` → lista.
- `GET /api/jugadores/{nfl_id}` → perfil o 404.

`dashboard/src`
- `components/PanelPerfil.tsx`: panel modal; pide `api/jugadores/<nflId>`.
- `components/AvatarJugador.tsx`: círculo con el número en los colores del equipo (Paleta_Equipos de la spec `equipos`).
- `components/BuscadorJugadores.tsx`: campo de texto que filtra la lista por nombre o siglas.
- `App.tsx` guarda `perfilId` y `jugadaSeleccionada`; "Ver en el visor" cambia la jugada del visor y hace `scrollIntoView`.

## Data Models

```python
class JugadorLista(BaseModel):
    nflId: int; nombre: str; equipo: str | None; posicion: str | None; numero: int | None
    rusher_snaps: int; pct_anticipa: float; pct_presion: float; offsides: int

class Ficha(BaseModel):
    nombre: str; posicion: str | None; equipo: str | None; numero: int | None
    estatura: str | None; peso: int | None; edad: int | None; universidad: str | None

class PresionGrupo(BaseModel):
    snaps: int; pct_presion: float | None

class StatsJugador(BaseModel):
    rusher_snaps: int; pct_anticipa: float; percentil_anticipacion: float
    velocidad_media_snap: float; pct_presion: float; offsides: int
    anticipando: PresionGrupo; sin_anticipar: PresionGrupo

class PuntoDistribucion(BaseModel):
    rango: str; pct_jugador: float; pct_liga: float

class JugadaDeJugador(BaseModel):
    gameId: int; playId: int; s_snap: float; rival: str

class PerfilJugador(BaseModel):
    nflId: int; ficha: Ficha; stats: StatsJugador
    distribucion: list[PuntoDistribucion]; jugadas_offside: list[JugadaDeJugador]
```

## Error Handling

| Situación | Comportamiento |
|---|---|
| `nflId` no elegible | 404 "Ese jugador no tiene al menos 100 snaps alineados." |
| Campo de `players.csv` vacío o ausente | `null` en la ficha |
| Cálculo en curso o fallido | 503 con `estado`, igual que las demás rutas |
| Dashboard: fallo del perfil | Mensaje en español dentro del panel |

## Correctness Properties

### Property 1: Elegibilidad y orden
For any lista, todos tienen `rusher_snaps >= 100`, y el orden es `pct_anticipa` desc, `rusher_snaps` desc, `nflId` asc; los 10 primeros coinciden con el Top_10_Scout.

**Validates: Requirements 1.1, 1.3**

### Property 2: Consistencia de stats
For any perfil, `anticipando.snaps + sin_anticipar.snaps == rusher_snaps`, `pct_anticipa == anticipando.snaps / rusher_snaps * 100`, y `percentil_anticipacion` está en (0, 100].

**Validates: Requirements 2.4**

### Property 3: Distribución
For any perfil, `distribucion` tiene los cinco rangos en orden y tanto `pct_jugador` como `pct_liga` suman 100 (salvo redondeo).

**Validates: Requirements 2.5**

## Testing Strategy

Pruebas pytest con datos sintéticos para las propiedades 1 a 3, edad con y sin `birthDate`, y la API (200, 404, 503). Con datos reales: la lista tiene los mismos 10 primeros que el Top_10_Scout.
