import { useMemo } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PuntoVelocidad } from '../types'

interface Props {
  velocidad: PuntoVelocidad[]
  velocidadControl: PuntoVelocidad[] | null
  tActual: number
  nombreInfractor: string
}

interface Fila {
  t: number
  offside: number | null
  control: number | null
  resto: number | null
}

/** Une las dos jugadas por t (tiempo respecto al snap). */
function unir(offside: PuntoVelocidad[], control: PuntoVelocidad[] | null): Fila[] {
  const filas = new Map<number, Fila>()
  const fila = (t: number) => {
    const k = Math.round(t * 10) / 10
    if (!filas.has(k)) filas.set(k, { t: k, offside: null, control: null, resto: null })
    return filas.get(k)!
  }
  offside.forEach((p) => {
    const f = fila(p.t)
    f.offside = p.infractor
    f.resto = p.resto_linea
  })
  control?.forEach((p) => {
    fila(p.t).control = p.infractor
  })
  return [...filas.values()].sort((a, b) => a.t - b.t)
}

export default function GraficaVelocidad({ velocidad, velocidadControl, tActual, nombreInfractor }: Props) {
  // Memorizado y sin animación: el cursor (tActual) cambia cada 100 ms al reproducir
  const datos = useMemo(() => unir(velocidad, velocidadControl), [velocidad, velocidadControl])
  return (
    <div className="h-60 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={datos} margin={{ top: 8, right: 12, bottom: 20, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="t"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(v: number) => `${v.toFixed(1)}s`}
            label={{ value: 'Segundos respecto al snap', position: 'insideBottom', offset: -10 }}
          />
          <YAxis unit=" yd/s" width={60} />
          <Tooltip
            labelFormatter={(v) => `t = ${Number(v).toFixed(1)} s`}
            formatter={(v) => (v === null || v === undefined ? 's/d' : `${Number(v).toFixed(2)} yd/s`)}
          />
          <Legend verticalAlign="top" height={40} />
          <ReferenceLine x={0} stroke="#013369" strokeWidth={2} label={{ value: 'SNAP', position: 'insideTopLeft', fill: '#013369', fontWeight: 700, fontSize: 12 }} />
          <ReferenceLine x={tActual} stroke="#6b7280" strokeDasharray="4 3" />
          <Line dataKey="offside" name={`${nombreInfractor} · con offside`} stroke="#D50A0A" strokeWidth={3} dot={false} connectNulls isAnimationActive={false} />
          {velocidadControl && (
            <Line dataKey="control" name={`${nombreInfractor} · jugada control`} stroke="#FFB612" strokeWidth={3} strokeDasharray="6 3" dot={false} connectNulls isAnimationActive={false} />
          )}
          <Line dataKey="resto" name="Resto de la línea (con offside)" stroke="#013369" strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
