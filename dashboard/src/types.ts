export interface Rango {
  rango: string
  rusher_snaps: number
  offsides: number
  offsides_por_1000: number | null
  pct_presion: number | null
}

export interface NumeroClave {
  x_pct_snaps: number | null
  y_pct_offsides: number | null
  umbral: string
}

export interface JugadorScout {
  nflId: number
  nombre: string
  rusher_snaps: number
  pct_movimiento: number
  pct_presion: number
  offsides: number
}

export interface Top10Scout {
  umbral: string
  jugadores: JugadorScout[]
}

export interface PorDown {
  down: number
  rusher_snaps: number
  offsides: number
  offsides_por_1000: number | null
  pct_del_total: number | null
}

export interface SinDownValido {
  rusher_snaps: number
  offsides: number
}

export interface Totales {
  rusher_snaps: number
  offsides: number
  juegos_omitidos: number[]
  sin_down_valido: SinDownValido
}

export interface OffsideResponse {
  rangos: Rango[]
  numero_clave: NumeroClave
  top10_scout: Top10Scout
  por_down: PorDown[]
  totales: Totales
  nota_umbrales: string
}

// ---- Visor de jugadas (spec jugada-evidencia) ----

export type Rol = 'infractor' | 'defensa' | 'ofensiva' | 'balon'

export interface JugadorFrame {
  nflId: number | null
  x: number
  y: number
  s: number | null
  numero: number | null
  rol: Rol
}

export interface Frame {
  frameId: number
  t: number
  jugadores: JugadorFrame[]
}

export interface PuntoVelocidad {
  t: number
  infractor: number | null
  resto_linea: number | null
}

export interface JugadaResumen {
  gameId: number
  playId: number
  infractor: { nflId: number; nombre: string }
  equipo_defensa: string
  equipo_ofensiva: string
  quarter: number
  down: number
  yardsToGo: number
  gameClock: string
  s_snap: number
  cruce_snap: number
  alineado: boolean
  descripcion: string
  tiene_control: boolean
}

// ---- Jugada control (spec jugada-control) ----

export interface JugadaControl extends JugadaResumen {
  linea_golpeo_x: number
  frames: Frame[]
  velocidad: PuntoVelocidad[]
  distancia_situacion: number
  criterio: string
}

export interface JugadaDetalle extends JugadaResumen {
  linea_golpeo_x: number
  frames: Frame[]
  velocidad: PuntoVelocidad[]
  control: JugadaControl | null
}

// ---- Perfil de jugador (spec perfil-jugador) ----

export interface JugadorLista {
  nflId: number
  nombre: string
  equipo: string | null
  posicion: string | null
  numero: number | null
  rusher_snaps: number
  pct_anticipa: number
  pct_presion: number
  offsides: number
}

export interface Ficha {
  nombre: string
  posicion: string | null
  equipo: string | null
  numero: number | null
  estatura: string | null
  peso: number | null
  edad: number | null
  universidad: string | null
}

export interface PresionGrupo {
  snaps: number
  pct_presion: number | null
}

export interface StatsJugador {
  rusher_snaps: number
  pct_anticipa: number
  percentil_anticipacion: number
  velocidad_media_snap: number
  pct_presion: number
  offsides: number
  anticipando: PresionGrupo
  sin_anticipar: PresionGrupo
}

export interface PuntoDistribucion {
  rango: string
  pct_jugador: number
  pct_liga: number
}

export interface JugadaDeJugador {
  gameId: number
  playId: number
  s_snap: number
  rival: string
}

export interface PerfilJugador {
  nflId: number
  ficha: Ficha
  stats: StatsJugador
  distribucion: PuntoDistribucion[]
  jugadas_offside: JugadaDeJugador[]
}

// ---- Equipos (spec equipos) ----

export interface EquipoDefensa {
  equipo: string
  rusher_snaps: number
  pct_anticipa: number
  pct_presion: number
  offsides: number
  offsides_por_1000: number
}

export interface EquipoOfensiva {
  equipo: string
  rusher_snaps_rival: number
  pct_anticipa_rival: number
  offsides_provocados: number
  offsides_por_1000: number
}

export interface EquiposResponse {
  defensas: EquipoDefensa[]
  ofensivas: EquipoOfensiva[]
  nota: string
}
