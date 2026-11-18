import { useState } from 'react'
import { cargarNarracion, type Narracion } from '../api'

interface Props {
  gameId: number
  playId: number
}

/** Narración tipo comentarista de la jugada (IA con Amazon Nova; plantilla si la IA no responde). */
export default function NarradorJugada({ gameId, playId }: Props) {
  const [narracion, setNarracion] = useState<Narracion | null>(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(false)

  const narrar = () => {
    setCargando(true)
    setError(false)
    cargarNarracion(gameId, playId)
      .then(setNarracion)
      .catch(() => setError(true))
      .finally(() => setCargando(false))
  }

  return (
    <div className="mt-4 overflow-hidden rounded-lg bg-nfl-navy text-white shadow-lg">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <button
          type="button"
          onClick={narrar}
          disabled={cargando}
          className="rounded bg-nfl-red px-4 py-2 font-titular text-sm font-black uppercase italic tracking-wide text-white shadow hover:bg-red-700 disabled:opacity-60"
        >
          {cargando ? 'Narrando…' : narracion ? '🎙️ Narrar otra vez' : '🎙️ Narrar la jugada'}
        </button>
        <p className="text-xs text-blue-200">Así la contaría el comentarista del domingo, con los datos de esta jugada.</p>
      </div>
      {error && (
        <p role="alert" className="border-t border-white/10 px-4 py-3 text-sm text-red-200">
          No se pudo generar la narración. Inténtalo de nuevo.
        </p>
      )}
      {narracion && (
        <blockquote className="border-t border-white/10 bg-black/20 px-4 py-3">
          <p className="font-titular text-lg font-bold italic leading-snug">“{narracion.texto}”</p>
          <footer className="mt-2 text-xs text-blue-200">
            {narracion.fuente === 'ia'
              ? 'Generada con IA (Amazon Nova en Bedrock) solo a partir de los datos calculados.'
              : 'Narración automática con plantilla (la IA no estuvo disponible).'}
          </footer>
        </blockquote>
      )}
    </div>
  )
}
