import type { OffsideResponse } from './types'

function fmt(valor: number): string {
  return `${valor.toFixed(1)}%`
}

export function construirFrase(datos: OffsideResponse): string {
  const clave = datos?.numero_clave
  const x = clave?.x_pct_snaps ?? null
  const y = clave?.y_pct_offsides ?? null
  const umbral = clave?.umbral ?? 's > 0.5 yd/s'

  if (x !== null && y !== null) {
    return `Cuando el rusher sale en movimiento (${umbral}), ocurre en ${fmt(x)} de los snaps, pero concentra ${fmt(y)} de los offsides.`
  }
  if (x !== null) {
    return `${fmt(x)} de los snaps de los rushers alineados salen en movimiento (${umbral}). No hay offsides registrados para comparar.`
  }
  if (y !== null) {
    return `${fmt(y)} de los offsides ocurren con el rusher en movimiento (${umbral}).`
  }
  return 'No hay datos suficientes para construir la frase del análisis.'
}
