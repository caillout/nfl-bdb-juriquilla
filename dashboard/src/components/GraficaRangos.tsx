import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
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

interface FilaTooltip {
  payload?: { rango: string; rusher_snaps: number; offsides: number; offsides_por_1000: number | null; pct_presion: number | null }
}

function TooltipRango({ active, payload }: { active?: boolean; payload?: FilaTooltip[] }) {
  const d = payload?.[0]?.payload
  if (!active || !d) return null
  return (
    <div className="rounded border border-gray-200 bg-white p-2 text-sm shadow">
      <p className="font-semibold">{d.rango} yd/s</p>
      <p>Offsides por 1,000: {d.offsides_por_1000 === null ? 's/d' : d.offsides_por_1000.toFixed(2)}</p>
      <p>% presión: {d.pct_presion === null ? 's/d' : `${d.pct_presion.toFixed(1)}%`}</p>
      <p className="text-gray-500">
        Muestra: {d.rusher_snaps.toLocaleString('es-MX')} snaps, {d.offsides} offsides
      </p>
    </div>
  )
}

export default function GraficaRangos({ rangos }: Props) {
  const datos = ORDEN_RANGOS.map((etiqueta) => {
    const r = rangos.find((x) => x.rango === etiqueta)
    return {
      rango: etiqueta,
      offsides_por_1000: r?.offsides_por_1000 ?? null,
      pct_presion: r?.pct_presion ?? null,
      rusher_snaps: r?.rusher_snaps ?? 0,
      offsides: r?.offsides ?? 0,
    }
  })

  return (
    <section className="tarjeta">
      <h2 className="titulo-seccion mb-1">Riesgo contra recompensa</h2>
      <p className="mb-3 text-sm text-gray-600">
        Barras: offsides por cada 1,000 snaps (riesgo). Línea: % de snaps con presión al QB (recompensa). Velocidad del
        rusher en el snap, en yd/s.
      </p>
      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={datos} margin={{ top: 8, right: 8, bottom: 24, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="rango"
              label={{ value: 'Velocidad en el snap (yd/s)', position: 'insideBottom', offset: -12 }}
            />
            <YAxis yAxisId="riesgo" label={{ value: 'por 1,000', angle: -90, position: 'insideLeft' }} />
            <YAxis
              yAxisId="presion"
              orientation="right"
              unit="%"
              domain={[0, 'auto']}
              label={{ value: '% presión', angle: 90, position: 'insideRight' }}
            />
            <Tooltip content={<TooltipRango />} />
            <Legend verticalAlign="top" height={28} />
            <Bar yAxisId="riesgo" dataKey="offsides_por_1000" name="Offsides por 1,000" fill="#b91c1c" />
            <Line
              yAxisId="presion"
              dataKey="pct_presion"
              name="% presión"
              stroke="#15803d"
              strokeWidth={3}
              dot={{ r: 4 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
