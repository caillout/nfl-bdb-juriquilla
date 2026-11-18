import { useEffect, useId, useRef, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { cargarPerfil } from '../api'
import { PALETA_EQUIPOS, coloresEquipo } from '../equipos'
import type { PerfilJugador, PresionGrupo } from '../types'
import AvatarJugador from './AvatarJugador'
import { ORDEN_RANGOS } from './GraficaRangos'

interface Props {
  nflId: number | null
  onCerrar: () => void
  onVerJugada: (gameId: number, playId: number) => void
}

type Estado =
  | { tipo: 'cargando' }
  | { tipo: 'error'; mensaje: string }
  | { tipo: 'listo'; perfil: PerfilJugador }

const GRIS_LIGA = '#9ca3af'
const AZUL_SIN_EQUIPO = '#2563eb'

function sd(valor: number | string | null | undefined, sufijo = ''): string {
  return valor === null || valor === undefined || valor === '' ? 's/d' : `${valor}${sufijo}`
}

/** "6-4" -> 6'4"; cualquier otro formato se muestra tal cual. */
function formatoEstatura(estatura: string | null): string {
  if (!estatura) return 's/d'
  const m = estatura.trim().match(/^(\d+)-(\d+)$/)
  return m ? `${m[1]}'${m[2]}"` : estatura
}

function pct(valor: number | null | undefined, decimales = 1): string {
  return valor === null || valor === undefined ? 's/d' : `${valor.toFixed(decimales)}%`
}

export default function PanelPerfil({ nflId, onCerrar, onVerJugada }: Props) {
  const [estado, setEstado] = useState<Estado>({ tipo: 'cargando' })
  const botonCerrar = useRef<HTMLButtonElement>(null)
  const idTitulo = useId()
  // Ref para que un onCerrar nuevo en cada render del padre no reinstale el listener ni robe el foco.
  const cerrarRef = useRef(onCerrar)
  cerrarRef.current = onCerrar

  // Carga del perfil cada vez que cambia el jugador.
  useEffect(() => {
    if (nflId === null) return
    let vigente = true
    setEstado({ tipo: 'cargando' })
    cargarPerfil(nflId)
      .then((perfil) => {
        if (vigente) setEstado({ tipo: 'listo', perfil })
      })
      .catch((err: unknown) => {
        if (!vigente) return
        const detalle = err instanceof Error ? err.message : ''
        setEstado({
          tipo: 'error',
          mensaje: detalle.includes('404')
            ? 'Ese jugador no tiene al menos 100 snaps alineados.'
            : 'No se pudo cargar el perfil del jugador. Intenta de nuevo en un momento.',
        })
      })
    return () => {
      vigente = false
    }
  }, [nflId])

  // Escape cierra, foco al botón de cerrar y bloqueo del scroll de la página.
  useEffect(() => {
    if (nflId === null) return
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cerrarRef.current()
    }
    window.addEventListener('keydown', alTeclear)
    botonCerrar.current?.focus()
    const overflowPrevio = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', alTeclear)
      document.body.style.overflow = overflowPrevio
    }
  }, [nflId])

  if (nflId === null) return null

  const alClicFondo = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onCerrar()
  }

  const perfil = estado.tipo === 'listo' ? estado.perfil : null
  const equipo = perfil?.ficha.equipo ?? null
  const colores = coloresEquipo(equipo)
  const colorJugador = equipo && PALETA_EQUIPOS[equipo] ? colores.primario : AZUL_SIN_EQUIPO

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-center bg-black/60 sm:items-center sm:p-4"
      onClick={alClicFondo}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        className="relative flex h-full w-full max-w-3xl flex-col overflow-y-auto bg-gray-50 shadow-xl sm:h-auto sm:max-h-[90vh] sm:rounded-lg"
        style={{ borderTop: `6px solid ${perfil ? colorJugador : '#d1d5db'}` }}
      >
        <button
          ref={botonCerrar}
          type="button"
          onClick={onCerrar}
          aria-label="Cerrar perfil"
          className="absolute right-2 top-2 z-10 flex h-9 w-9 items-center justify-center rounded-full bg-white text-xl leading-none text-gray-600 shadow hover:bg-gray-100 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          ×
        </button>

        {estado.tipo === 'cargando' && (
          <div className="p-6">
            <h2 id={idTitulo} className="sr-only">
              Perfil del jugador
            </h2>
            <p className="text-sm text-gray-600" aria-live="polite">
              Cargando perfil…
            </p>
          </div>
        )}

        {estado.tipo === 'error' && (
          <div className="p-6">
            <h2 id={idTitulo} className="mb-2 text-lg font-semibold">
              Perfil del jugador
            </h2>
            <p role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              {estado.mensaje}
            </p>
          </div>
        )}

        {perfil && (
          <ContenidoPerfil
            perfil={perfil}
            idTitulo={idTitulo}
            colorJugador={colorJugador}
            nombreEquipo={colores.nombre}
            onVerJugada={(g, p) => {
              onVerJugada(g, p)
              onCerrar()
            }}
          />
        )}
      </div>
    </div>
  )
}

interface PropsContenido {
  perfil: PerfilJugador
  idTitulo: string
  colorJugador: string
  nombreEquipo: string
  onVerJugada: (gameId: number, playId: number) => void
}

function ContenidoPerfil({ perfil, idTitulo, colorJugador, nombreEquipo, onVerJugada }: PropsContenido) {
  const { ficha, stats, distribucion, jugadas_offside } = perfil
  const subtitulo = [ficha.posicion, nombreEquipo || ficha.equipo].filter(Boolean).join(' · ')

  return (
    <div className="space-y-4 p-4 sm:p-6">
      {/* Encabezado */}
      <header className="flex items-center gap-4 pr-10">
        <AvatarJugador numero={ficha.numero} equipo={ficha.equipo} tamano="lg" />
        <div className="min-w-0">
          <h2 id={idTitulo} className="text-2xl font-bold leading-tight text-gray-900 sm:text-3xl">
            {ficha.nombre}
          </h2>
          <p className="text-sm text-gray-600">
            {subtitulo || 's/d'}
            {ficha.equipo && <span className="ml-2 rounded bg-gray-200 px-1.5 py-0.5 text-xs font-semibold text-gray-700">{ficha.equipo}</span>}
          </p>
        </div>
      </header>

      {/* Ficha */}
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="sr-only">Ficha</h3>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <DatoFicha etiqueta="Estatura" valor={formatoEstatura(ficha.estatura)} />
          <DatoFicha etiqueta="Peso" valor={sd(ficha.peso, ' lb')} />
          <DatoFicha etiqueta="Edad" valor={sd(ficha.edad, ' años')} />
          <DatoFicha etiqueta="Universidad" valor={sd(ficha.universidad)} />
        </dl>
      </section>

      {/* Stats */}
      <section>
        <h3 className="titulo-seccion mb-2 !text-base">Estadísticas</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <TarjetaStat etiqueta="Snaps alineados" valor={stats.rusher_snaps.toLocaleString('es-MX')} />
          <TarjetaStat
            etiqueta="% se anticipa (s ≥ 1 yd/s)"
            valor={pct(stats.pct_anticipa)}
            nota={`Percentil ${Math.round(stats.percentil_anticipacion)} de la liga`}
          />
          <TarjetaStat
            etiqueta="Velocidad media en el snap"
            valor={stats.velocidad_media_snap.toFixed(2)}
            unidad="yd/s"
          />
          <TarjetaStat etiqueta="% presión" valor={pct(stats.pct_presion)} />
          <TarjetaStat etiqueta="Offsides" valor={String(stats.offsides)} />
        </div>
      </section>

      {/* Presión anticipando vs. sin anticipar */}
      <ComparaPresion
        anticipando={stats.anticipando}
        sinAnticipar={stats.sin_anticipar}
        color={colorJugador}
      />

      {/* Distribución */}
      <GraficaDistribucion distribucion={distribucion} colorJugador={colorJugador} />

      {/* Jugadas con offside */}
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="titulo-seccion mb-2 !text-base">Sus jugadas con offside</h3>
        {jugadas_offside.length === 0 ? (
          <p className="text-sm text-gray-600">No tiene offsides ligados en estas semanas.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {jugadas_offside.map((j) => (
              <li key={`${j.gameId}-${j.playId}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div className="min-w-0 text-sm">
                  <p className="font-medium text-gray-900">
                    vs. {j.rival} · <span className="tabular-nums">{j.s_snap.toFixed(2)} yd/s</span> en el snap
                  </p>
                  <p className="text-xs text-gray-500">
                    Partido {j.gameId} · jugada {j.playId}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onVerJugada(j.gameId, j.playId)}
                  className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                  Ver en el visor
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function DatoFicha({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs uppercase tracking-wide text-gray-500">{etiqueta}</dt>
      <dd className="break-words text-sm font-semibold text-gray-900">{valor}</dd>
    </div>
  )
}

function TarjetaStat({
  etiqueta,
  valor,
  unidad,
  nota,
}: {
  etiqueta: string
  valor: string
  unidad?: string
  nota?: ReactNode
}) {
  return (
    <div className="rounded-lg bg-white p-3 shadow">
      <p className="text-xs text-gray-500">{etiqueta}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-gray-900">
        {valor}
        {unidad && <span className="ml-1 text-sm font-medium text-gray-500">{unidad}</span>}
      </p>
      {nota && <p className="mt-0.5 text-xs text-gray-600">{nota}</p>}
    </div>
  )
}

function ComparaPresion({
  anticipando,
  sinAnticipar,
  color,
}: {
  anticipando: PresionGrupo
  sinAnticipar: PresionGrupo
  color: string
}) {
  // Escala común desde cero para las dos barras.
  const maximo = Math.max(anticipando.pct_presion ?? 0, sinAnticipar.pct_presion ?? 0)
  const escala = maximo > 0 ? maximo * 1.15 : 1
  const filas = [
    { etiqueta: 'Anticipando', grupo: anticipando },
    { etiqueta: 'Sin anticipar', grupo: sinAnticipar },
  ]

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="titulo-seccion mb-1 !text-base">Presión: anticipando vs. sin anticipar</h3>
      <p className="mb-3 text-sm text-gray-600">% de sus snaps con presión al QB, según si salió a ≥ 1 yd/s en el snap.</p>
      <div className="space-y-3">
        {filas.map(({ etiqueta, grupo }) => (
          <div key={etiqueta}>
            <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
              <span className="font-medium text-gray-800">{etiqueta}</span>
              <span className="tabular-nums text-gray-600">
                <span className="font-semibold text-gray-900">{pct(grupo.pct_presion)}</span> ·{' '}
                {grupo.snaps.toLocaleString('es-MX')} snaps
              </span>
            </div>
            <div className="h-3 w-full rounded bg-gray-100">
              {grupo.pct_presion !== null && (
                <div
                  className="h-3 rounded"
                  style={{ width: `${(grupo.pct_presion / escala) * 100}%`, backgroundColor: color }}
                />
              )}
            </div>
          </div>
        ))}
      </div>
      {anticipando.snaps < 10 && (
        <p className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <span className="font-semibold">Aviso:</span> Muestra chica: solo {anticipando.snaps} snaps anticipando
        </p>
      )}
    </section>
  )
}

function GraficaDistribucion({
  distribucion,
  colorJugador,
}: {
  distribucion: PerfilJugador['distribucion']
  colorJugador: string
}) {
  const datos = ORDEN_RANGOS.map((rango) => {
    const d = distribucion.find((x) => x.rango === rango)
    return { rango, pct_jugador: d?.pct_jugador ?? 0, pct_liga: d?.pct_liga ?? 0 }
  })

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="titulo-seccion mb-1 !text-base">Velocidad en el snap: jugador contra liga</h3>
      <p className="mb-2 text-sm text-gray-600">% de snaps alineados en cada rango de velocidad.</p>
      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos} margin={{ top: 4, right: 8, bottom: 20, left: -12 }} barGap={2}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
            <XAxis
              dataKey="rango"
              tick={{ fontSize: 11 }}
              interval={0}
              label={{ value: 'Velocidad en el snap (yd/s)', position: 'insideBottom', offset: -12, fontSize: 12 }}
            />
            <YAxis unit="%" tick={{ fontSize: 11 }} />
            <Tooltip
              labelFormatter={(v) => `${v} yd/s`}
              formatter={(v) => (v === null || v === undefined ? 's/d' : `${Number(v).toFixed(1)}%`)}
              cursor={{ fill: '#f3f4f6' }}
            />
            <Legend
              verticalAlign="top"
              height={24}
              wrapperStyle={{ fontSize: 12 }}
              formatter={(valor) => <span className="text-gray-700">{valor}</span>}
            />
            <Bar dataKey="pct_jugador" name="Este jugador" fill={colorJugador} radius={[4, 4, 0, 0]} />
            <Bar dataKey="pct_liga" name="Liga" fill={GRIS_LIGA} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
