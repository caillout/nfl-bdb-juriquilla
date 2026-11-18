import type { Top10Scout } from '../types'
import InsigniaEquipo from './InsigniaEquipo'

interface Props {
  top10: Top10Scout
  equipoDe?: (nflId: number) => string | null
  onElegirJugador?: (nflId: number) => void
}

function num(valor: number | null | undefined, decimales = 1): string {
  return valor === null || valor === undefined ? 's/d' : valor.toFixed(decimales)
}

export default function TablaScout({ top10, equipoDe, onElegirJugador }: Props) {
  return (
    <section className="tarjeta">
      <h2 className="titulo-seccion mb-1">Top 10 Scout: rushers que salen en movimiento</h2>
      <p className="mb-3 text-sm text-gray-600">
        Umbral: {top10.umbral}. {onElegirJugador ? 'Da clic en un jugador para ver su perfil.' : ''}
      </p>
      {top10.jugadores.length === 0 ? (
        <p className="text-sm text-gray-600">No hay jugadores elegibles.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b-2 border-nfl-navy text-xs uppercase tracking-wide text-nfl-navy">
                <th className="py-2 pr-3">#</th>
                <th className="py-2 pr-3">Jugador</th>
                <th className="py-2 pr-3 text-right">Snaps</th>
                <th className="py-2 pr-3 text-right">% en movimiento</th>
                <th className="py-2 pr-3 text-right">% presión</th>
                <th className="py-2 text-right">Offsides</th>
              </tr>
            </thead>
            <tbody className="marcador">
              {top10.jugadores.map((j, i) => (
                <tr
                  key={j.nflId}
                  className={`border-b last:border-0 ${onElegirJugador ? 'cursor-pointer hover:bg-slate-50' : ''}`}
                  onClick={() => onElegirJugador?.(j.nflId)}
                >
                  <td className="py-2 pr-3 font-bold text-nfl-red">{i + 1}</td>
                  <td className="py-2 pr-3">
                    <span className="flex items-center gap-2">
                      {equipoDe && <InsigniaEquipo equipo={equipoDe(j.nflId)} tamano="sm" />}
                      {onElegirJugador ? (
                        <button
                          type="button"
                          className="text-left font-semibold text-nfl-navy hover:text-nfl-red hover:underline"
                          onClick={(e) => {
                            e.stopPropagation()
                            onElegirJugador(j.nflId)
                          }}
                        >
                          {j.nombre}
                        </button>
                      ) : (
                        <span className="font-semibold">{j.nombre}</span>
                      )}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right">{j.rusher_snaps}</td>
                  <td className="py-2 pr-3 text-right font-semibold">{num(j.pct_movimiento)}%</td>
                  <td className="py-2 pr-3 text-right">{num(j.pct_presion)}%</td>
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
