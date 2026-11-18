import { useEffect, useState } from 'react'
import { cargarEquipos } from '../api'
import { coloresEquipo, colorTexto } from '../equipos'
import type { EquiposResponse, JugadorLista } from '../types'
import AvatarJugador from './AvatarJugador'
import InsigniaEquipo from './InsigniaEquipo'

interface Props {
  local: string
  visita: string
  jugadores: JugadorLista[] | null
  onAbrirPerfil: (nflId: number) => void
}

interface Lado {
  equipo: string
  pctAnticipa: number | null
  lugarAnticipa: number | null
  offsides: number | null
  provocados: number | null
  lugarProvocados: number | null
  rushers: JugadorLista[]
}

function lado(equipo: string, datos: EquiposResponse, jugadores: JugadorLista[] | null): Lado {
  const iDef = datos.defensas.findIndex((d) => d.equipo === equipo)
  const iOf = datos.ofensivas.findIndex((o) => o.equipo === equipo)
  const def = iDef >= 0 ? datos.defensas[iDef] : null
  const of = iOf >= 0 ? datos.ofensivas[iOf] : null
  return {
    equipo,
    pctAnticipa: def?.pct_anticipa ?? null,
    lugarAnticipa: iDef >= 0 ? iDef + 1 : null,
    offsides: def?.offsides ?? null,
    provocados: of?.offsides_provocados ?? null,
    lugarProvocados: iOf >= 0 ? iOf + 1 : null,
    rushers: (jugadores ?? []).filter((j) => j.equipo === equipo).slice(0, 3),
  }
}

function Columna({ l, total, onAbrirPerfil }: { l: Lado; total: number; onAbrirPerfil: (id: number) => void }) {
  const c = coloresEquipo(l.equipo)
  return (
    <div className="overflow-hidden rounded-lg bg-white/95 text-slate-900 shadow-lg">
      <div className="flex items-center gap-3 px-3 py-2" style={{ backgroundColor: c.primario, color: colorTexto(c.primario) }}>
        <InsigniaEquipo equipo={l.equipo} tamano="lg" />
        <span className="font-titular text-lg font-black uppercase italic">{c.nombre}</span>
      </div>
      <dl className="marcador grid grid-cols-2 gap-x-3 gap-y-2 p-3 text-sm">
        <dt className="text-gray-500">Su defensa se anticipa</dt>
        <dd className="text-right font-bold">
          {l.pctAnticipa === null ? 's/d' : `${l.pctAnticipa.toFixed(1)}%`}
          {l.lugarAnticipa && <span className="ml-1 text-xs font-normal text-gray-500">({l.lugarAnticipa}º de {total})</span>}
        </dd>
        <dt className="text-gray-500">Offsides cometidos</dt>
        <dd className="text-right font-bold">{l.offsides ?? 's/d'}</dd>
        <dt className="text-gray-500">Offsides que provoca su ofensiva</dt>
        <dd className="text-right font-bold">
          {l.provocados ?? 's/d'}
          {l.lugarProvocados && <span className="ml-1 text-xs font-normal text-gray-500">({l.lugarProvocados}º de {total})</span>}
        </dd>
      </dl>
      <div className="border-t px-3 py-2">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Sus rushers que más se anticipan</p>
        {l.rushers.length === 0 ? (
          <p className="text-xs text-gray-500">Sin rushers con 100+ snaps alineados.</p>
        ) : (
          <ul className="space-y-1">
            {l.rushers.map((j) => (
              <li key={j.nflId}>
                <button
                  type="button"
                  onClick={() => onAbrirPerfil(j.nflId)}
                  className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-sm hover:bg-slate-100"
                >
                  <AvatarJugador numero={j.numero} equipo={j.equipo} tamano="sm" />
                  <span className="font-semibold">{j.nombre}</span>
                  <span className="marcador ml-auto text-xs text-gray-600">{j.pct_anticipa.toFixed(1)}% se anticipa</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

/** Duelo del domingo: los dos equipos del partido, con sus datos de 2021 (spec equipos, requisito 5). */
export default function DueloDomingo({ local, visita, jugadores, onAbrirPerfil }: Props) {
  const [datos, setDatos] = useState<EquiposResponse | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    cargarEquipos()
      .then(setDatos)
      .catch(() => setError(true))
  }, [])

  return (
    <section className="overflow-hidden rounded-xl bg-gradient-to-br from-nfl-navy via-[#0a2550] to-nfl-night p-4 text-white shadow-xl shadow-black/40 ring-1 ring-white/10 sm:p-5">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-nfl-gold">Duelo del domingo · Ciudad de México</p>
      <h2 className="font-titular text-2xl font-black uppercase italic tracking-tight sm:text-3xl">
        {local} vs {visita}: ¿quién se anticipa al snap?
      </h2>
      <p className="mb-4 text-sm text-blue-100">
        Cómo llegaban sus defensas y ofensivas en las semanas 1 a 8 de 2021, con los mismos datos del tablero.
      </p>
      {error && <p role="alert" className="text-sm text-red-200">No se pudieron cargar los datos de los equipos.</p>}
      {!datos && !error && <p className="text-sm text-blue-100">Cargando equipos…</p>}
      {datos && (
        <div className="grid gap-4 md:grid-cols-2">
          <Columna l={lado(local, datos, jugadores)} total={datos.defensas.length} onAbrirPerfil={onAbrirPerfil} />
          <Columna l={lado(visita, datos, jugadores)} total={datos.defensas.length} onAbrirPerfil={onAbrirPerfil} />
        </div>
      )}
      {datos && <p className="mt-3 text-xs text-blue-200">{datos.nota}</p>}
    </section>
  )
}
