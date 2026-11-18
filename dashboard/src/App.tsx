import { useCallback, useEffect, useState } from 'react'
import { cargarOffside } from './api'
import { construirFrase } from './frase'
import type { OffsideResponse } from './types'
import GraficaRangos from './components/GraficaRangos'
import TarjetaClave from './components/TarjetaClave'
import TablaScout from './components/TablaScout'

export default function App() {
  const [datos, setDatos] = useState<OffsideResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)

  const cargar = useCallback(() => {
    setCargando(true)
    setError(null)
    cargarOffside()
      .then((respuesta) => setDatos(respuesta))
      .catch(() => {
        setDatos(null)
        setError(
          'No se pudieron cargar los datos de offside. Verifica que el servidor esté en marcha e inténtalo de nuevo.',
        )
      })
      .finally(() => setCargando(false))
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  return (
    <main className="mx-auto max-w-5xl space-y-4 p-6">
      <header>
        <h1 className="text-2xl font-bold">Velocidad en el snap y offsides defensivos</h1>
        <p className="text-gray-600">
          Pass rushers alineados en la línea de golpeo, calculado a partir de los datos de tracking.
        </p>
      </header>

      {cargando && (
        <p role="status" className="rounded-lg bg-white p-4 text-gray-700 shadow">
          Cargando datos…
        </p>
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800">
          <p>{error}</p>
          <button
            type="button"
            onClick={cargar}
            className="mt-2 rounded bg-red-700 px-3 py-1 text-sm text-white hover:bg-red-800"
          >
            Reintentar
          </button>
        </div>
      )}

      {datos && (
        <>
          <p className="rounded-lg bg-green-50 p-4 text-lg font-medium text-green-900">
            {construirFrase(datos)}
          </p>
          <TarjetaClave clave={datos.numero_clave} />
          <GraficaRangos rangos={datos.rangos} />
          <TablaScout top10={datos.top10_scout} />
          <footer className="space-y-1 text-sm text-gray-600">
            <p>{datos.nota_umbrales}</p>
            <p>
              Total: {datos.totales.rusher_snaps} rusher-snaps alineados y {datos.totales.offsides} offsides ligados.
              {datos.totales.juegos_omitidos.length > 0 &&
                ` Juegos omitidos por error de lectura: ${datos.totales.juegos_omitidos.join(', ')}.`}
            </p>
          </footer>
        </>
      )}
    </main>
  )
}
