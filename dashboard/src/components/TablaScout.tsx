import type { Top10Scout } from '../types'

interface Props {
  top10: Top10Scout
}

function num(valor: number | null | undefined, decimales = 1): string {
  return valor === null || valor === undefined ? 's/d' : valor.toFixed(decimales)
}

export default function TablaScout({ top10 }: Props) {
  return (
    <section className="rounded-lg bg-white p-4 shadow">
      <h2 className="mb-1 text-lg font-semibold">Top 10 Scout: rushers que salen en movimiento</h2>
      <p className="mb-3 text-sm text-gray-600">Umbral: {top10.umbral}</p>
      {top10.jugadores.length === 0 ? (
        <p className="text-sm text-gray-600">No hay jugadores elegibles.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b text-gray-600">
                <th className="py-2 pr-3">#</th>
                <th className="py-2 pr-3">Jugador</th>
                <th className="py-2 pr-3 text-right">Snaps</th>
                <th className="py-2 pr-3 text-right">% en movimiento</th>
                <th className="py-2 pr-3 text-right">% presión</th>
                <th className="py-2 text-right">Offsides</th>
              </tr>
            </thead>
            <tbody>
              {top10.jugadores.map((j, i) => (
                <tr key={j.nflId} className="border-b last:border-0">
                  <td className="py-2 pr-3">{i + 1}</td>
                  <td className="py-2 pr-3">{j.nombre}</td>
                  <td className="py-2 pr-3 text-right">{j.rusher_snaps}</td>
                  <td className="py-2 pr-3 text-right">{num(j.pct_movimiento)}%</td>
                  <td className="py-2 pr-3 text-right">
                    {j.pct_presion === null || j.pct_presion === undefined ? 's/d' : `${num(j.pct_presion)}%`}
                  </td>
                  <td className="py-2 text-right">{j.offsides}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
