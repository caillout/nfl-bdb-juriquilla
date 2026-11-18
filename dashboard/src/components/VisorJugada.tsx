import { useEffect, useMemo, useRef, useState } from 'react'
import { cargarJugada, cargarJugadas } from '../api'
import type { JugadaControl, JugadaDetalle, JugadaResumen } from '../types'
import Campo, { altoNecesario } from './Campo'
import GraficaVelocidad from './GraficaVelocidad'
import InsigniaEquipo from './InsigniaEquipo'

const VELOCIDADES = [0.25, 0.5, 1] as const

const ordinal = (n: number) => ({ 1: '1er', 2: '2do', 3: '3er', 4: '4to' } as Record<number, string>)[n] ?? `${n}`
export const claveJugada = (j: { gameId: number; playId: number }) => `${j.gameId}-${j.playId}`

/** Pedido externo para mostrar una jugada (el contador permite repetir la misma). */
export interface PedidoJugada {
  clave: string
  n: number
}

interface Props {
  pedido: PedidoJugada | null
  elegibles: Set<number>
  onElegirJugador: (nflId: number) => void
}

function Encabezado({ titulo, j, acento }: { titulo: string; j: JugadaResumen; acento: string }) {
  return (
    <div className="mb-2 flex flex-wrap items-center gap-2">
      <span className={`rounded px-2 py-0.5 font-titular text-xs font-black uppercase italic tracking-wide text-white ${acento}`}>
        {titulo}
      </span>
      <InsigniaEquipo equipo={j.equipo_defensa} tamano="sm" />
      <span className="text-xs text-gray-500">vs</span>
      <InsigniaEquipo equipo={j.equipo_ofensiva} tamano="sm" />
      <span className="ml-auto text-xs text-gray-600">
        Q{j.quarter} · {j.gameClock} · {ordinal(j.down)} y {j.yardsToGo}
      </span>
    </div>
  )
}

export default function VisorJugada({ pedido, elegibles, onElegirJugador }: Props) {
  const seccion = useRef<HTMLElement>(null)
  const [lista, setLista] = useState<JugadaResumen[] | null>(null)
  const [seleccion, setSeleccion] = useState<string>('')
  const [detalle, setDetalle] = useState<JugadaDetalle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [indice, setIndice] = useState(0)
  const [reproduciendo, setReproduciendo] = useState(false)
  const [ritmo, setRitmo] = useState<(typeof VELOCIDADES)[number]>(0.5)

  useEffect(() => {
    cargarJugadas()
      .then((l) => {
        setLista(l)
        setSeleccion((s) => s || (l.length > 0 ? claveJugada(l[0]) : ''))
      })
      .catch(() => setError('No se pudo cargar la lista de jugadas con offside.'))
  }, [])

  // Pedido desde el perfil del jugador: cambiar de jugada y llevar la vista al visor
  useEffect(() => {
    if (!pedido) return
    setSeleccion(pedido.clave)
    seccion.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [pedido])

  useEffect(() => {
    if (!seleccion) return
    const [g, p] = seleccion.split('-').map(Number)
    setDetalle(null)
    setReproduciendo(false)
    cargarJugada(g, p)
      .then((d) => {
        setDetalle(d)
        setError(null)
        setIndice(0)
        setReproduciendo(true)
      })
      .catch(() => setError('No se pudo cargar el detalle de la jugada.'))
  }, [seleccion])

  const control: JugadaControl | null = detalle?.control ?? null

  // Línea de tiempo común: todos los t de ambas jugadas
  const linea = useMemo(() => {
    if (!detalle) return [] as number[]
    const ts = new Set<number>(detalle.frames.map((f) => f.t))
    control?.frames.forEach((f) => ts.add(f.t))
    return [...ts].sort((a, b) => a - b)
  }, [detalle, control])

  const indiceSnap = linea.indexOf(0)

  // Mismo alto para las dos canchas, para que se vean parejas lado a lado
  const altoComun = useMemo(() => {
    if (!detalle) return undefined
    return Math.max(altoNecesario(detalle.frames), control ? altoNecesario(control.frames) : 0)
  }, [detalle, control])

  useEffect(() => {
    if (!reproduciendo || linea.length === 0) return
    const id = setInterval(() => {
      setIndice((i) => {
        if (i >= linea.length - 1) {
          setReproduciendo(false)
          return i
        }
        return i + 1
      })
    }, 100 / ritmo)
    return () => clearInterval(id)
  }, [reproduciendo, linea, ritmo])

  const t = linea[Math.min(indice, Math.max(0, linea.length - 1))] ?? 0
  const nombre = detalle?.infractor.nombre ?? ''
  const puedeAbrir = detalle ? elegibles.has(detalle.infractor.nflId) : false

  return (
    <section ref={seccion} className="tarjeta scroll-mt-4">
      <h2 className="titulo-seccion mb-1">La evidencia: el mismo jugador, con y sin offside</h2>
      <p className="mb-3 text-sm text-gray-600">
        Izquierda: la jugada en la que lo marcaron. Derecha: el mismo jugador en una jugada parecida sin falta. El jugador
        va en rojo con aro dorado; la defensa en azul y la ofensiva en blanco. Las dos avanzan juntas desde el snap.
      </p>

      {error && (
        <p role="alert" className="mb-3 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      )}

      {lista && lista.length > 0 && (
        <label className="mb-3 block text-sm">
          <span className="mb-1 block font-medium text-gray-700">
            Jugada ({lista.length} con offside, de mayor a menor velocidad en el snap)
          </span>
          <select
            className="w-full rounded border border-gray-300 bg-white p-2"
            value={seleccion}
            onChange={(e) => setSeleccion(e.target.value)}
          >
            {lista.map((j) => (
              <option key={claveJugada(j)} value={claveJugada(j)}>
                {j.infractor.nombre} ({j.equipo_defensa}) vs {j.equipo_ofensiva} · Q{j.quarter} {ordinal(j.down)} y {j.yardsToGo} ·{' '}
                {j.s_snap.toFixed(2)} yd/s en el snap{j.alineado ? '' : ' · no alineado'}
              </option>
            ))}
          </select>
        </label>
      )}

      {!detalle && !error && <p className="text-sm text-gray-600">Cargando jugada…</p>}

      {detalle && (
        <>
          <div className={`grid gap-4 ${control ? 'lg:grid-cols-2' : ''}`}>
            <div>
              <Encabezado titulo="Con offside" j={detalle} acento="bg-nfl-red" />
              <Campo frames={detalle.frames} t={t} lineaGolpeo={detalle.linea_golpeo_x} alto={altoComun} />
              <p className="mt-1 text-sm">
                En el snap: <span className="marcador font-bold text-nfl-red">{detalle.s_snap.toFixed(2)} yd/s</span>
              </p>
            </div>
            {control ? (
              <div>
                <Encabezado titulo="Control: sin offside" j={control} acento="bg-nfl-navy" />
                <Campo frames={control.frames} t={t} lineaGolpeo={control.linea_golpeo_x} alto={altoComun} />
                <p className="mt-1 text-sm">
                  En el snap: <span className="marcador font-bold text-nfl-navy">{control.s_snap.toFixed(2)} yd/s</span>
                  <span className="text-gray-500"> · {control.criterio}</span>
                </p>
              </div>
            ) : (
              <p className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                Este jugador no tiene una jugada control (alineado, sin offside y quieto en el snap).
              </p>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <button
              type="button"
              onClick={() => {
                if (indice >= linea.length - 1) setIndice(0)
                setReproduciendo((r) => !r)
              }}
              className="rounded bg-nfl-navy px-3 py-1 font-semibold text-white hover:bg-blue-900"
            >
              {reproduciendo ? 'Pausa' : 'Reproducir'}
            </button>
            <button
              type="button"
              onClick={() => {
                setReproduciendo(false)
                if (indiceSnap >= 0) setIndice(indiceSnap)
              }}
              className="rounded border border-nfl-red px-3 py-1 font-semibold text-nfl-red hover:bg-red-50"
            >
              Ir al snap
            </button>
            {VELOCIDADES.map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setRitmo(v)}
                className={`rounded px-2 py-1 ${ritmo === v ? 'bg-slate-200 font-semibold' : 'hover:bg-slate-100'}`}
              >
                {v}x
              </button>
            ))}
            <span
              className={`marcador ml-auto rounded px-2 py-0.5 font-mono ${
                t === 0 ? 'bg-nfl-red font-bold text-white' : 'bg-slate-100 text-gray-800'
              }`}
            >
              t = {t >= 0 ? '+' : ''}
              {t.toFixed(1)} s{t === 0 ? ' · SNAP' : ''}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={Math.max(0, linea.length - 1)}
            value={indice}
            onChange={(e) => {
              setReproduciendo(false)
              setIndice(Number(e.target.value))
            }}
            className="mt-2 w-full accent-nfl-red"
            aria-label="Momento de la jugada"
          />

          <div className="mt-4 grid gap-4 lg:grid-cols-5">
            <div className="space-y-2 text-sm lg:col-span-2">
              <p>
                <span className="text-gray-500">Jugador: </span>
                {puedeAbrir ? (
                  <button
                    type="button"
                    onClick={() => onElegirJugador(detalle.infractor.nflId)}
                    className="font-bold text-nfl-navy underline decoration-nfl-red decoration-2 underline-offset-2 hover:text-nfl-red"
                  >
                    {nombre} · ver perfil
                  </button>
                ) : (
                  <span className="font-bold">{nombre}</span>
                )}
              </p>
              <p className="text-xs leading-relaxed text-gray-600">
                <span className="font-semibold text-nfl-red">Con offside: </span>
                {detalle.descripcion}
              </p>
              {control && (
                <p className="text-xs leading-relaxed text-gray-600">
                  <span className="font-semibold text-nfl-navy">Control: </span>
                  {control.descripcion}
                </p>
              )}
            </div>
            <div className="lg:col-span-3">
              <GraficaVelocidad
                velocidad={detalle.velocidad}
                velocidadControl={control?.velocidad ?? null}
                tActual={t}
                nombreInfractor={nombre}
              />
            </div>
          </div>
        </>
      )}
    </section>
  )
}
