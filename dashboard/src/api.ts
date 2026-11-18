import type {
  EquiposResponse,
  JugadaDetalle,
  JugadaResumen,
  JugadorLista,
  OffsideResponse,
  PerfilJugador,
} from './types'

export type { OffsideResponse } from './types'

const ESPERA_MS = 3000
const MAX_INTENTOS = 40 // 40 x 3 s = 2 minutos

const dormir = (ms: number) => new Promise((resolver) => setTimeout(resolver, ms))

/**
 * GET con ruta relativa (sin diagonal inicial, para que funcione en la subruta del hosting).
 * Mientras el backend responde 503 con estado "calculando", espera 3 s y reintenta.
 */
async function obtener<T>(ruta: string, alEsperar?: () => void): Promise<T> {
  for (let intento = 0; intento < MAX_INTENTOS; intento++) {
    const res = await fetch(ruta)
    if (res.ok) return (await res.json()) as T
    if (res.status === 503) {
      const cuerpo = await res.json().catch(() => null)
      if (cuerpo?.detail?.estado === 'calculando') {
        alEsperar?.()
        await dormir(ESPERA_MS)
        continue
      }
    }
    throw new Error(`Error ${res.status} al cargar ${ruta}`)
  }
  throw new Error('El servidor tardó demasiado en calcular los datos')
}

export function cargarOffside(alEsperar?: () => void): Promise<OffsideResponse> {
  return obtener<OffsideResponse>('api/offside', alEsperar)
}

export function cargarJugadas(): Promise<JugadaResumen[]> {
  return obtener<JugadaResumen[]>('api/jugadas')
}

export function cargarJugada(gameId: number, playId: number): Promise<JugadaDetalle> {
  return obtener<JugadaDetalle>(`api/jugadas/${gameId}/${playId}`)
}

export function cargarJugadores(): Promise<JugadorLista[]> {
  return obtener<JugadorLista[]>('api/jugadores')
}

export function cargarPerfil(nflId: number): Promise<PerfilJugador> {
  return obtener<PerfilJugador>(`api/jugadores/${nflId}`)
}

export function cargarEquipos(): Promise<EquiposResponse> {
  return obtener<EquiposResponse>('api/equipos')
}
