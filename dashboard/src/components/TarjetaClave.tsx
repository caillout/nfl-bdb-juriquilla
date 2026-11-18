import type { NumeroClave } from '../types'

interface Props {
  clave: NumeroClave
}

function pct(valor: number | null): string {
  return valor === null || valor === undefined ? 's/d' : `${valor.toFixed(1)}%`
}

export default function TarjetaClave({ clave }: Props) {
  return (
    <section className="rounded-lg bg-white p-4 shadow">
      <h2 className="mb-2 text-lg font-semibold">Número clave</h2>
      <p className="text-3xl font-bold text-green-800">
        {pct(clave.x_pct_snaps)} de los snaps → {pct(clave.y_pct_offsides)} de los offsides
      </p>
      <p className="mt-2 text-sm text-gray-600">Umbral: {clave.umbral}</p>
    </section>
  )
}
