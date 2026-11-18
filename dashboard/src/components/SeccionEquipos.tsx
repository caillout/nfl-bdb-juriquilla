import { useEffect, useMemo, useState, type KeyboardEvent } from 'react'
import { cargarEquipos } from '../api'
import { coloresEquipo } from '../equipos'
import type { EquipoDefensa, EquipoOfensiva, EquiposResponse, JugadorLista } from '../types'
import InsigniaEquipo from './InsigniaEquipo'

interface Props {
  jugadores: JugadorLista[] | null
  onAbrirPerfil: (nflId: number) => void
}

type Pestana = 'defensas' | 'ofensivas'

const PESTANAS: { id: Pestana; etiqueta: string }[] = [
  { id: 'defensas', etiqueta: 'Defensas' },
  { id: 'ofensivas', etiqueta: 'Ofensivas' },
]

function entero(valor: number | null | undefined): string {
  return valor === null || valor === undefined ? 's/d' : valor.toLocaleString('es-MX')
}

function dec(valor: number | null | undefined, decimales = 1): string {
  return valor === null || valor === undefined
    ? 's/d'
    : valor.toLocaleString('es-MX', { minimumFractionDigits: decimales, maximumFractionDigits: decimales })
}

function pct(valor: number | null | undefined): string {
  return valor === null || valor === undefined ? 's/d' : `${dec(valor)}%`
}

/** Celda con barra horizontal proporcional al máximo, en el color primario del equipo. */
function BarraPct({ valor, maximo, equipo }: { valor: number; maximo: number; equipo: string }) {
  const ancho = maximo > 0 ? Math.max(0, Math.min(100, (valor / maximo) * 100)) : 0
  return (
    <div className="flex items-center justify-end gap-2">
      <div className="h-2 w-16 shrink-0 overflow-hidden rounded bg-gray-100 sm:w-24" aria-hidden="true">
        <div
          className="h-full rounded"
          style={{ width: `${ancho}%`, backgroundColor: coloresEquipo(equipo).primario }}
        />
      </div>
      <span className="w-12 text-right tabular-nums">{pct(valor)}</span>
    </div>
  )
}

function TablaDefensas({
  defensas,
  seleccionado,
  onSeleccionar,
}: {
  defensas: EquipoDefensa[]
  seleccionado: string | null
  onSeleccionar: (equipo: string) => void
}) {
  const maximo = useMemo(() => Math.max(0, ...defensas.map((d) => d.pct_anticipa ?? 0)), [defensas])

  const alTeclear = (e: KeyboardEvent<HTMLTableRowElement>, equipo: string) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSeleccionar(equipo)
    }
  }

  if (defensas.length === 0) return <p className="text-sm text-gray-600">No hay datos de defensas.</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b text-gray-600">
            <th className="py-2 pr-3">#</th>
            <th className="py-2 pr-3">Equipo</th>
            <th className="py-2 pr-3 text-right">Snaps</th>
            <th className="py-2 pr-3 text-right">% se anticipa</th>
            <th className="py-2 pr-3 text-right">% presión</th>
            <th className="py-2 pr-3 text-right">Offsides</th>
            <th className="py-2 text-right">Por 1,000</th>
          </tr>
        </thead>
        <tbody>
          {defensas.map((d, i) => {
            const activo = d.equipo === seleccionado
            const nombre = coloresEquipo(d.equipo).nombre || d.equipo
            return (
              <tr
                key={d.equipo}
                tabIndex={0}
                onClick={() => onSeleccionar(d.equipo)}
                onKeyDown={(e) => alTeclear(e, d.equipo)}
                aria-label={`${nombre}: ver sus rushers`}
                className={`cursor-pointer border-b last:border-0 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 ${
                  activo ? 'bg-blue-50 hover:bg-blue-50' : ''
                }`}
              >
                <td className="py-2 pr-3 tabular-nums">{i + 1}</td>
                <td className="whitespace-nowrap py-2 pr-3">
                  <InsigniaEquipo equipo={d.equipo} tamano="sm" conNombre />
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">{entero(d.rusher_snaps)}</td>
                <td className="py-2 pr-3 text-right">
                  <BarraPct valor={d.pct_anticipa} maximo={maximo} equipo={d.equipo} />
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">{pct(d.pct_presion)}</td>
                <td className="py-2 pr-3 text-right tabular-nums">{entero(d.offsides)}</td>
                <td className="py-2 text-right tabular-nums">{dec(d.offsides_por_1000, 2)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function TablaOfensivas({ ofensivas }: { ofensivas: EquipoOfensiva[] }) {
  if (ofensivas.length === 0) return <p className="text-sm text-gray-600">No hay datos de ofensivas.</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b text-gray-600">
            <th className="py-2 pr-3">#</th>
            <th className="py-2 pr-3">Equipo</th>
            <th className="py-2 pr-3 text-right">Snaps del rival</th>
            <th className="py-2 pr-3 text-right">% el rival se anticipa</th>
            <th className="py-2 pr-3 text-right">Offsides provocados</th>
            <th className="py-2 text-right">Por 1,000</th>
          </tr>
        </thead>
        <tbody>
          {ofensivas.map((o, i) => (
            <tr key={o.equipo} className="border-b last:border-0">
              <td className="py-2 pr-3 tabular-nums">{i + 1}</td>
              <td className="whitespace-nowrap py-2 pr-3">
                <InsigniaEquipo equipo={o.equipo} tamano="sm" conNombre />
              </td>
              <td className="py-2 pr-3 text-right tabular-nums">{entero(o.rusher_snaps_rival)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{pct(o.pct_anticipa_rival)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{entero(o.offsides_provocados)}</td>
              <td className="py-2 text-right tabular-nums">{dec(o.offsides_por_1000, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function JugadoresDeEquipo({
  equipo,
  jugadores,
  onAbrirPerfil,
}: {
  equipo: string
  jugadores: JugadorLista[] | null
  onAbrirPerfil: (nflId: number) => void
}) {
  const delEquipo = useMemo(
    () =>
      (jugadores ?? [])
        .filter((j) => j.equipo === equipo)
        .sort((a, b) => (b.pct_anticipa ?? 0) - (a.pct_anticipa ?? 0)),
    [jugadores, equipo],
  )

  return (
    <div className="mt-4 rounded-md border border-gray-200 p-3" aria-live="polite">
      <h3 className="mb-2 flex flex-wrap items-center gap-2 text-sm font-semibold">
        <span>Rushers de</span>
        <InsigniaEquipo equipo={equipo} tamano="sm" conNombre />
      </h3>
      {jugadores === null ? (
        <p className="text-sm text-gray-600">Cargando jugadores…</p>
      ) : delEquipo.length === 0 ? (
        <p className="text-sm text-gray-600">Ningún rusher de este equipo tiene 100 snaps alineados.</p>
      ) : (
        <>
          <p className="mb-2 text-xs text-gray-500">Da clic en un jugador para abrir su perfil.</p>
          <ul className="flex flex-wrap gap-2">
            {delEquipo.map((j) => (
              <li key={j.nflId}>
                <button
                  type="button"
                  onClick={() => onAbrirPerfil(j.nflId)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-gray-300 bg-white px-3 py-1 text-sm hover:border-gray-400 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  title={`Abrir perfil de ${j.nombre}`}
                >
                  {j.numero !== null && j.numero !== undefined && (
                    <span className="font-semibold tabular-nums text-gray-500">#{j.numero}</span>
                  )}
                  <span>{j.nombre}</span>
                  <span className="tabular-nums text-gray-500">· {pct(j.pct_anticipa)} anticipa</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

export default function SeccionEquipos({ jugadores, onAbrirPerfil }: Props) {
  const [datos, setDatos] = useState<EquiposResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pestana, setPestana] = useState<Pestana>('defensas')
  const [seleccionado, setSeleccionado] = useState<string | null>(null)

  useEffect(() => {
    let vigente = true
    cargarEquipos()
      .then((r) => {
        if (vigente) setDatos(r)
      })
      .catch((e: unknown) => {
        if (!vigente) return
        const detalle = e instanceof Error ? e.message : String(e)
        setError(`No se pudieron cargar los equipos. ${detalle}`)
      })
    return () => {
      vigente = false
    }
  }, [])

  const alTeclearPestana = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
    e.preventDefault()
    const i = PESTANAS.findIndex((p) => p.id === pestana)
    const siguiente = PESTANAS[(i + (e.key === 'ArrowRight' ? 1 : PESTANAS.length - 1)) % PESTANAS.length]
    setPestana(siguiente.id)
    document.getElementById(`pestana-equipos-${siguiente.id}`)?.focus()
  }

  const alSeleccionar = (equipo: string) => setSeleccionado((actual) => (actual === equipo ? null : equipo))

  return (
    <section className="tarjeta">
      <h2 className="titulo-seccion mb-1">Equipos: ¿quién se anticipa y quién lo provoca?</h2>
      <p className="mb-3 text-sm text-gray-600">
        Defensas: qué tanto se anticipan sus rushers alineados. Ofensivas: qué tanto hacen que el rival se anticipe.
      </p>

      <div role="tablist" aria-label="Ranking de equipos" className="mb-3 flex gap-1 border-b">
        {PESTANAS.map((p) => {
          const activa = p.id === pestana
          return (
            <button
              key={p.id}
              id={`pestana-equipos-${p.id}`}
              type="button"
              role="tab"
              aria-selected={activa}
              aria-controls={`panel-equipos-${p.id}`}
              tabIndex={activa ? 0 : -1}
              onClick={() => setPestana(p.id)}
              onKeyDown={alTeclearPestana}
              className={`-mb-px rounded-t-md border-b-2 px-3 py-2 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                activa
                  ? 'border-blue-600 text-blue-700'
                  : 'border-transparent text-gray-600 hover:border-gray-300 hover:text-gray-800'
              }`}
            >
              {p.etiqueta}
            </button>
          )
        })}
      </div>

      <div
        id={`panel-equipos-${pestana}`}
        role="tabpanel"
        aria-labelledby={`pestana-equipos-${pestana}`}
      >
        {error ? (
          <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
            {error}
          </p>
        ) : datos === null ? (
          <p className="text-sm text-gray-600">Cargando equipos…</p>
        ) : pestana === 'defensas' ? (
          <>
            <p className="mb-2 text-xs text-gray-500">
              Ordenadas por % de snaps en que el rusher se anticipa. Da clic en una defensa para ver sus rushers.
            </p>
            <TablaDefensas defensas={datos.defensas} seleccionado={seleccionado} onSeleccionar={alSeleccionar} />
            {seleccionado && (
              <JugadoresDeEquipo equipo={seleccionado} jugadores={jugadores} onAbrirPerfil={onAbrirPerfil} />
            )}
          </>
        ) : (
          <>
            <p className="mb-2 text-xs text-gray-500">
              Ordenadas por offsides provocados por cada 1,000 snaps de rushers rivales.
            </p>
            <TablaOfensivas ofensivas={datos.ofensivas} />
          </>
        )}

        {datos && datos.nota && <p className="mt-3 text-xs text-gray-500">Nota: {datos.nota}</p>}
      </div>
    </section>
  )
}
