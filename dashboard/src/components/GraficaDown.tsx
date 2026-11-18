import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PorDown, SinDownValido } from '../types'

interface Props {
  porDown: PorDown[]
  sinDown: SinDownValido
}

const NOMBRE_DOWN: Record<number, string> = { 1: '1er down', 2: '2do down', 3: '3er down', 4: '4to down' }

export default function GraficaDown({ porDown, sinDown }: Props) {
  const datos = porDown.map((d) => ({
    ...d,
    nombre: NOMBRE_DOWN[d.down] ?? `${d.down}`,
    etiqueta: d.offsides_por_1000 === null ? 's/d' : d.offsides_por_1000.toFixed(2),
  }))

  return (
    <section className="tarjeta">
      <h2 className="titulo-seccion mb-1">¿Cuándo se arriesga la defensa?</h2>
      <p className="mb-3 text-sm text-gray-600">Offsides por cada 1,000 snaps de rushers alineados, según el down.</p>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos} margin={{ top: 20, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="nombre" />
            <YAxis />
            <Tooltip
              formatter={(_v, _n, item) => {
                const d = item?.payload as (typeof datos)[number] | undefined
                if (!d) return ['s/d', '']
                const pct = d.pct_del_total === null ? 's/d' : `${d.pct_del_total.toFixed(1)}%`
                return [`${d.etiqueta} (${d.offsides} offsides en ${d.rusher_snaps.toLocaleString('es-MX')} snaps, ${pct} del total)`, 'Por 1,000']
              }}
            />
            <Bar dataKey="offsides_por_1000" fill="#1d4ed8">
              <LabelList dataKey="etiqueta" position="top" className="text-xs" />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {sinDown.rusher_snaps > 0 && (
        <p className="mt-2 text-xs text-gray-500">
          Se excluyen {sinDown.rusher_snaps.toLocaleString('es-MX')} snaps con down inválido en los datos (
          {sinDown.offsides} offsides).
        </p>
      )}
    </section>
  )
}
