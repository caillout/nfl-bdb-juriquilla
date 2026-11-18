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
  pct_offsides: number | null
}

export interface Totales {
  rusher_snaps: number
  offsides: number
  juegos_omitidos: number[]
}

export interface OffsideResponse {
  rangos: Rango[]
  numero_clave: NumeroClave
  top10_scout: Top10Scout
  por_down: PorDown[]
  totales: Totales
  nota_umbrales: string
}
