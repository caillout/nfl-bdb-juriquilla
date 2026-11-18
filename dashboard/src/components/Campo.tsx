import { useId, useMemo } from 'react'
import type { Frame, JugadorFrame, Rol } from '../types'

interface Props {
  frames: Frame[]
  /** Tiempo respecto al snap; se dibuja el cuadro con el t más cercano. */
  t: number
  lineaGolpeo: number
  /** Alto fijo en yardas, para que dos canchas lado a lado midan lo mismo. */
  alto?: number
}

const ANCHO_CANCHA = 53.3
const ALTO_MINIMO = 20

/** Alto en yardas que necesita una jugada para que quepan todos sus jugadores. */
export function altoNecesario(frames: Frame[]): number {
  const ys = frames.flatMap((f) => f.jugadores.map((j) => j.y))
  if (ys.length === 0) return ALTO_MINIMO
  const minY = Math.max(0, Math.min(...ys) - 3)
  const maxY = Math.min(ANCHO_CANCHA, Math.max(...ys) + 3)
  return Math.max(ALTO_MINIMO, maxY - minY)
}

const COLOR: Record<Rol, { relleno: string; borde: string; texto: string }> = {
  infractor: { relleno: '#D50A0A', borde: '#FFB612', texto: '#ffffff' },
  defensa: { relleno: '#013369', borde: '#ffffff', texto: '#ffffff' },
  ofensiva: { relleno: '#f8fafc', borde: '#0f172a', texto: '#0f172a' },
  balon: { relleno: '#7c2d12', borde: '#fde68a', texto: '#ffffff' },
}

const MEDIA_VENTANA_X = 15 // yardas a cada lado de la línea de golpeo

export function indiceMasCercano(frames: Frame[], t: number): number {
  let mejor = 0
  for (let i = 1; i < frames.length; i++) {
    if (Math.abs(frames[i].t - t) < Math.abs(frames[mejor].t - t)) mejor = i
  }
  return mejor
}

export default function Campo({ frames, t, lineaGolpeo, alto: altoFijo }: Props) {
  const idPatron = `franjas-${useId().replace(/:/g, '')}`
  const caja = useMemo(() => {
    const ys = frames.flatMap((f) => f.jugadores.map((j) => j.y))
    const alto = Math.min(ANCHO_CANCHA, Math.max(altoFijo ?? 0, altoNecesario(frames)))
    // Centrado en los jugadores, sin salirse de la cancha
    const centro = ys.length ? (Math.min(...ys) + Math.max(...ys)) / 2 : ANCHO_CANCHA / 2
    const y0 = Math.min(Math.max(0, centro - alto / 2), ANCHO_CANCHA - alto)
    return { x0: lineaGolpeo - MEDIA_VENTANA_X, ancho: 2 * MEDIA_VENTANA_X, y0, alto }
  }, [frames, lineaGolpeo, altoFijo])

  const indice = frames.length ? indiceMasCercano(frames, t) : 0
  const frame = frames[indice]

  // Estela del jugador resaltado hasta el cuadro actual
  const estela = useMemo(
    () =>
      frames
        .slice(0, indice + 1)
        .map((f) => f.jugadores.find((j) => j.rol === 'infractor'))
        .filter((j): j is JugadorFrame => Boolean(j))
        .map((j) => `${j.x},${j.y}`)
        .join(' '),
    [frames, indice],
  )

  const lineasYarda: number[] = []
  for (let x = Math.ceil(caja.x0 / 5) * 5; x <= caja.x0 + caja.ancho; x += 5) lineasYarda.push(x)

  const orden: Rol[] = ['ofensiva', 'defensa', 'infractor', 'balon']
  const jugadores = frame ? [...frame.jugadores].sort((a, b) => orden.indexOf(a.rol) - orden.indexOf(b.rol)) : []

  return (
    <svg
      viewBox={`${caja.x0} ${caja.y0} ${caja.ancho} ${caja.alto}`}
      className="h-auto w-full rounded-lg ring-2 ring-white/10"
      role="img"
      aria-label="Posición de los jugadores en la cancha"
    >
      <defs>
        <pattern id={idPatron} width="10" height={caja.alto} patternUnits="userSpaceOnUse" x={Math.floor(caja.x0 / 10) * 10}>
          <rect width="5" height={caja.alto} fill="#1d5e34" />
          <rect x="5" width="5" height={caja.alto} fill="#1a5530" />
        </pattern>
      </defs>
      <rect x={caja.x0} y={caja.y0} width={caja.ancho} height={caja.alto} fill={`url(#${idPatron})`} />
      {lineasYarda.map((x) => (
        <line key={x} x1={x} x2={x} y1={caja.y0} y2={caja.y0 + caja.alto} stroke="#ffffff" strokeOpacity={0.35} strokeWidth={0.12} />
      ))}
      <line
        x1={lineaGolpeo}
        x2={lineaGolpeo}
        y1={caja.y0}
        y2={caja.y0 + caja.alto}
        stroke="#60a5fa"
        strokeWidth={0.3}
        strokeDasharray="0.8 0.5"
      />
      <text x={lineaGolpeo + 0.4} y={caja.y0 + 1.4} fontSize={1} fill="#bfdbfe">
        línea de golpeo
      </text>
      <text x={caja.x0 + 0.6} y={caja.y0 + caja.alto - 0.8} fontSize={1} fill="#dcfce7">
        la ofensiva ataca hacia la derecha →
      </text>
      {estela && <polyline points={estela} fill="none" stroke="#FFB612" strokeWidth={0.25} strokeOpacity={0.9} />}
      {jugadores.map((j, i) => {
        const c = COLOR[j.rol]
        if (j.rol === 'balon') {
          return <ellipse key={`b${i}`} cx={j.x} cy={j.y} rx={0.55} ry={0.35} fill={c.relleno} stroke={c.borde} strokeWidth={0.1} />
        }
        const r = j.rol === 'infractor' ? 1.05 : 0.85
        return (
          <g key={j.nflId ?? i}>
            {j.rol === 'infractor' && <circle cx={j.x} cy={j.y} r={1.7} fill="none" stroke="#FFB612" strokeWidth={0.22} />}
            <circle cx={j.x} cy={j.y} r={r} fill={c.relleno} stroke={c.borde} strokeWidth={0.12} />
            {j.numero !== null && (
              <text x={j.x} y={j.y + 0.33} fontSize={0.9} textAnchor="middle" fill={c.texto} fontWeight={700}>
                {j.numero}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}
