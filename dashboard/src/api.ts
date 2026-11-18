import type { OffsideResponse } from './types'

export type { OffsideResponse } from './types'

export async function cargarOffside(): Promise<OffsideResponse> {
  const res = await fetch('api/offside')
  if (!res.ok) {
    throw new Error(`Error ${res.status} al cargar los datos de offside`)
  }
  return (await res.json()) as OffsideResponse
}
