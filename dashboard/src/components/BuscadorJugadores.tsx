import { useId, useMemo, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { JugadorLista } from '../types'
import AvatarJugador from './AvatarJugador'

interface Props {
  jugadores: JugadorLista[] | null
  onElegir: (nflId: number) => void
}

const MAX_RESULTADOS = 8

/** Minúsculas y sin acentos, para comparar "Núñez" con "nunez". */
function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()
}

export default function BuscadorJugadores({ jugadores, onElegir }: Props) {
  const [consulta, setConsulta] = useState('')
  const [abierto, setAbierto] = useState(false)
  const [activo, setActivo] = useState(0)
  const idBase = useId()
  const idLista = `${idBase}-lista`
  const idOpcion = (i: number) => `${idBase}-op-${i}`

  const resultados = useMemo(() => {
    const q = normalizar(consulta)
    if (!jugadores || q === '') return []
    return jugadores
      .filter((j) => normalizar(j.nombre).includes(q) || normalizar(j.equipo ?? '').includes(q))
      .slice(0, MAX_RESULTADOS)
  }, [jugadores, consulta])

  const cargando = jugadores === null
  const mostrarLista = abierto && consulta.trim() !== '' && !cargando

  function elegir(j: JugadorLista) {
    setConsulta('')
    setAbierto(false)
    setActivo(0)
    onElegir(j.nflId)
  }

  function alTeclear(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setAbierto(true)
      if (resultados.length > 0) setActivo((i) => (i + 1) % resultados.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setAbierto(true)
      if (resultados.length > 0) setActivo((i) => (i - 1 + resultados.length) % resultados.length)
    } else if (e.key === 'Enter') {
      const j = resultados[activo]
      if (mostrarLista && j) {
        e.preventDefault()
        elegir(j)
      }
    } else if (e.key === 'Escape') {
      if (abierto) {
        e.preventDefault()
        setAbierto(false)
      }
    }
  }

  return (
    <div className="relative w-full">
      <label htmlFor={`${idBase}-campo`} className="mb-1 block text-sm font-semibold text-blue-100">
        Busca un rusher por nombre o equipo (siglas)
      </label>
      <input
        id={`${idBase}-campo`}
        type="search"
        autoComplete="off"
        role="combobox"
        aria-expanded={mostrarLista}
        aria-controls={idLista}
        aria-autocomplete="list"
        aria-activedescendant={mostrarLista && resultados[activo] ? idOpcion(activo) : undefined}
        disabled={cargando}
        placeholder={cargando ? 'Cargando jugadores…' : 'Nombre o siglas, p. ej. TB'}
        value={consulta}
        onChange={(e) => {
          setConsulta(e.target.value)
          setAbierto(true)
          setActivo(0)
        }}
        onFocus={() => setAbierto(true)}
        onBlur={() => setAbierto(false)}
        onKeyDown={alTeclear}
        className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200 disabled:cursor-not-allowed disabled:bg-gray-100"
      />
      {!cargando && (
        <p className="mt-1 text-xs text-blue-200">
          {jugadores.length.toLocaleString('es-MX')} rushers con 100+ snaps
        </p>
      )}

      {mostrarLista && (
        <ul
          id={idLista}
          role="listbox"
          aria-label="Resultados de la búsqueda"
          className="absolute left-0 right-0 top-full z-20 mt-1 max-h-80 overflow-y-auto rounded-md border border-gray-200 bg-white py-1 shadow-lg"
        >
          {resultados.length === 0 ? (
            <li className="px-3 py-2 text-sm text-gray-500">Sin resultados</li>
          ) : (
            resultados.map((j, i) => (
              <li
                key={j.nflId}
                id={idOpcion(i)}
                role="option"
                aria-selected={i === activo}
                // mousedown en vez de click para elegir antes de que el input pierda el foco
                onMouseDown={(e) => {
                  e.preventDefault()
                  elegir(j)
                }}
                onMouseEnter={() => setActivo(i)}
                className={`flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm ${
                  i === activo ? 'bg-blue-50' : ''
                }`}
              >
                <AvatarJugador numero={j.numero} equipo={j.equipo} tamano="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-gray-900">{j.nombre}</span>
                  <span className="block truncate text-xs text-gray-500">
                    {[j.equipo, j.posicion].filter(Boolean).join(' · ') || 's/d'}
                  </span>
                </span>
                <span className="shrink-0 text-right text-xs text-gray-600">
                  <span className="font-semibold text-gray-900">{j.pct_anticipa.toFixed(1)}%</span> anticipa
                </span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  )
}
