import { colorTexto, coloresEquipo } from '../equipos'

interface Props {
  equipo: string | null | undefined
  tamano?: 'sm' | 'md' | 'lg'
  conNombre?: boolean
}

const CLASES_TAMANO: Record<NonNullable<Props['tamano']>, string> = {
  sm: 'min-w-[2.5rem] px-1.5 py-0.5 text-xs',
  md: 'min-w-[3rem] px-2 py-0.5 text-sm',
  lg: 'min-w-[4rem] px-3 py-1 text-lg',
}

const CLASES_NOMBRE: Record<NonNullable<Props['tamano']>, string> = {
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-base',
}

/** Insignia_Equipo (spec equipos): siglas sobre el color primario con borde del secundario. Sin logos. */
export default function InsigniaEquipo({ equipo, tamano = 'md', conNombre = false }: Props) {
  const colores = coloresEquipo(equipo)
  const siglas = equipo && equipo.trim() !== '' ? equipo : 's/d'
  const nombre = colores.nombre && colores.nombre !== equipo ? colores.nombre : ''
  const titulo = nombre ? `${nombre} (${siglas})` : siglas === 's/d' ? 'Equipo sin dato' : siglas

  return (
    <span className="inline-flex items-center gap-2 align-middle" title={titulo}>
      <span
        className={`inline-flex shrink-0 items-center justify-center rounded-md border-2 font-bold leading-tight tabular-nums ${CLASES_TAMANO[tamano]}`}
        style={{
          backgroundColor: colores.primario,
          borderColor: colores.secundario,
          color: colorTexto(colores.primario),
        }}
      >
        {siglas}
      </span>
      {conNombre && nombre && (
        <span className={`truncate text-gray-600 ${CLASES_NOMBRE[tamano]}`}>{nombre}</span>
      )}
    </span>
  )
}
