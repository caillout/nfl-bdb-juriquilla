import { colorTexto, coloresEquipo } from '../equipos'

interface Props {
  numero: number | null
  equipo: string | null
  tamano?: 'sm' | 'md' | 'lg'
}

const TAMANOS: Record<NonNullable<Props['tamano']>, { px: number; texto: string }> = {
  sm: { px: 28, texto: 'text-xs' },
  md: { px: 40, texto: 'text-sm' },
  lg: { px: 72, texto: 'text-2xl' },
}

/** Círculo con el número del jersey en los colores del equipo (sin fotos). */
export default function AvatarJugador({ numero, equipo, tamano = 'md' }: Props) {
  const { primario, secundario, nombre } = coloresEquipo(equipo)
  const { px, texto } = TAMANOS[tamano]
  const etiquetaNumero = numero === null ? 'Número desconocido' : `Número ${numero}`
  const etiquetaEquipo = nombre || equipo || 'equipo desconocido'

  return (
    <span
      role="img"
      aria-label={`${etiquetaNumero}, ${etiquetaEquipo}`}
      className={`inline-flex shrink-0 select-none items-center justify-center rounded-full font-bold leading-none ${texto}`}
      style={{
        width: px,
        height: px,
        backgroundColor: primario,
        color: colorTexto(primario),
        boxShadow: `0 0 0 3px ${secundario}`,
        margin: 3,
      }}
    >
      {numero === null ? '?' : numero}
    </span>
  )
}
