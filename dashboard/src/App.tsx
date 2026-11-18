import { useCallback, useEffect, useMemo, useState } from 'react'
import { cargarJugadores, cargarOffside } from './api'
import { construirFrase } from './frase'
import type { JugadorLista, OffsideResponse } from './types'
import BuscadorJugadores from './components/BuscadorJugadores'
import DueloDomingo from './components/DueloDomingo'
import GraficaDown from './components/GraficaDown'
import GraficaRangos from './components/GraficaRangos'
import PanelPerfil from './components/PanelPerfil'
import SeccionEquipos from './components/SeccionEquipos'
import TablaScout from './components/TablaScout'
import TarjetaClave from './components/TarjetaClave'
import VisorJugada, { type PedidoJugada } from './components/VisorJugada'

export default function App() {
  const [datos, setDatos] = useState<OffsideResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [calculando, setCalculando] = useState(false)
  const [jugadores, setJugadores] = useState<JugadorLista[] | null>(null)
  const [perfilId, setPerfilId] = useState<number | null>(null)
  const [pedido, setPedido] = useState<PedidoJugada | null>(null)

  const cargar = useCallback(() => {
    setCargando(true)
    setCalculando(false)
    setError(null)
    cargarOffside(() => setCalculando(true))
      .then((respuesta) => {
        setDatos(respuesta)
        // Cuando /api/offside ya respondió, el resto de los datos también está listo
        cargarJugadores()
          .then(setJugadores)
          .catch(() => setJugadores([]))
      })
      .catch(() => {
        setDatos(null)
        setError(
          'No se pudieron cargar los datos de offside. Verifica que el servidor esté en marcha e inténtalo de nuevo.',
        )
      })
      .finally(() => {
        setCargando(false)
        setCalculando(false)
      })
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  const elegibles = useMemo(() => new Set((jugadores ?? []).map((j) => j.nflId)), [jugadores])
  const equipoPorJugador = useMemo(() => new Map((jugadores ?? []).map((j) => [j.nflId, j.equipo])), [jugadores])
  const cerrarPerfil = useCallback(() => setPerfilId(null), [])
  const verJugada = useCallback((gameId: number, playId: number) => {
    setPedido((p) => ({ clave: `${gameId}-${playId}`, n: (p?.n ?? 0) + 1 }))
  }, [])

  const rapidos = datos?.rangos.filter((r) => r.rango === '1-2' || r.rango === '>2') ?? []
  const snapsRapidos = rapidos.reduce((a, r) => a + r.rusher_snaps, 0)
  const offsidesRapidos = rapidos.reduce((a, r) => a + r.offsides, 0)

  return (
    <main className="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-6">
      {/* Encabezado estilo scorebug de transmisión */}
      <header className="overflow-hidden rounded-xl shadow-2xl shadow-black/50 ring-1 ring-white/10">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 bg-nfl-red px-4 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-white">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 animate-pulse rounded-full bg-white" aria-hidden="true" /> Big Data Bowl
          </span>
          <span className="text-white/80">Tracking · Semanas 1–8 · 2021</span>
        </div>
        <div className="bg-gradient-to-r from-nfl-navy via-[#0a2a5e] to-nfl-navy px-4 py-5 text-white sm:px-6 sm:py-7">
          <h1 className="font-titular text-3xl font-black uppercase italic leading-none tracking-tight sm:text-5xl">
            ¿Vale la pena <span className="text-nfl-gold">adivinar el snap?</span>
          </h1>
          <p className="mt-3 max-w-3xl text-sm text-blue-100 sm:text-base">
            Medimos la velocidad de cada pass rusher alineado en la línea en el instante exacto del snap, y qué tan
            seguido eso termina en un offside defensivo. Para el entrenador: a quién vigilar y cuándo.
          </p>
          <div className="mt-4 max-w-md">
            <BuscadorJugadores jugadores={jugadores} onElegir={setPerfilId} />
          </div>
        </div>
      </header>

      {cargando && (
        <p role="status" className="tarjeta text-gray-700">
          {calculando ? 'Calculando las métricas a partir del tracking (tarda unos segundos al arrancar)…' : 'Cargando datos…'}
        </p>
      )}

      {error && (
        <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-800">
          <p>{error}</p>
          <button
            type="button"
            onClick={cargar}
            className="mt-2 rounded bg-nfl-red px-3 py-1 text-sm font-semibold text-white hover:bg-red-800"
          >
            Reintentar
          </button>
        </div>
      )}

      {datos && (
        <>
          <TarjetaClave clave={datos.numero_clave} />
          <p className="rounded-r-xl border-l-8 border-nfl-red bg-white/95 p-4 font-titular text-lg font-bold italic text-nfl-navy shadow-lg sm:text-xl">
            {construirFrase(datos)}
          </p>
          <VisorJugada pedido={pedido} elegibles={elegibles} onElegirJugador={setPerfilId} />
          <GraficaRangos rangos={datos.rangos} />
          <div className="grid gap-5 lg:grid-cols-2">
            <GraficaDown porDown={datos.por_down} sinDown={datos.totales.sin_down_valido} />
            <TablaScout
              top10={datos.top10_scout}
              equipoDe={(id) => equipoPorJugador.get(id) ?? null}
              onElegirJugador={setPerfilId}
            />
          </div>
          <DueloDomingo local="MIN" visita="SF" jugadores={jugadores} onAbrirPerfil={setPerfilId} />
          <SeccionEquipos jugadores={jugadores} onAbrirPerfil={setPerfilId} />
          <footer className="space-y-1 pb-6 text-sm text-blue-100/80">
            <p>{datos.nota_umbrales}</p>
            <p>
              Cautela con los rangos altos: de 1 yd/s en adelante hay {snapsRapidos.toLocaleString('es-MX')} snaps y{' '}
              {offsidesRapidos} offsides. Es correlación, no causa: los que más se anticipan también son los mejores
              rushers.
            </p>
            <p>
              Total: {datos.totales.rusher_snaps.toLocaleString('es-MX')} rusher-snaps alineados y {datos.totales.offsides}{' '}
              offsides ligados.
              {datos.totales.juegos_omitidos.length > 0 &&
                ` Juegos omitidos por error de lectura: ${datos.totales.juegos_omitidos.join(', ')}.`}
            </p>
          </footer>
        </>
      )}

      <PanelPerfil nflId={perfilId} onCerrar={cerrarPerfil} onVerJugada={verJugada} />
    </main>
  )
}
