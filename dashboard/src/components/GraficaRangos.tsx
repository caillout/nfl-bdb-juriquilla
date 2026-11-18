import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Rango } from '../types'

export const ORDEN_RANGOS = ['0-0.25', '0.25-0.5', '0.5-1', '1-2', '>2']

interface Props {
  rangos: Rango[]
}

export default function GraficaRangos({ rangos }: Props) {
  const datos = ORDEN_RANGOS.map((etiqueta) => {
    const r = rangos.find((x) => x.rango === etiqueta)
    return {
      rango: etiqueta,
      offsides_por_1000: r?.offsides_por_1000 ?? null,
      rusher_snaps: r?.rusher_snaps ?? 0,
      offsides: r?.offsides ?? 0,
    }
  })

  return (
    <section className="rounded-lg bg-white p-4 shadow">
      <h2 className="mb-1 text-lg font-semibold">Offsides por cada 1,000 snaps según la velocidad</h2>
      <p className="mb-3 text-sm text-gray-600">
        Velocidad del rusher en el snap (yd/s). Rangos sin snaps se muestran vacíos (s/d).
      </p>
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos} margin={{ top: 8, right: 16, bottom: 24, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="rango"
              label={{ value: 'Velocidad en el snap (yd/s)', position: 'insideBottom', offset: -12 }}
            />
            <YAxis />
            <Tooltip
              formatter={(valor, nombre) => [
                valor === null || valor === undefined ? 's/d' : Number(valor).toFixed(2),
                nombre === 'offsides_por_1000' ? 'Offsides por 1,000' : String(nombre),
              ]}
            />
            <Bar dataKey="offsides_por_1000" name="offsides_por_1000" fill="#2F7D4F" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
