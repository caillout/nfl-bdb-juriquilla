// Paleta_Equipos (spec equipos): colores primario y secundario por siglas, tal como vienen en los datos.
// Sin logos ni imágenes externas (rules.md prohíbe URLs absolutas).

export interface ColoresEquipo {
  primario: string
  secundario: string
  nombre: string
}

export const PALETA_EQUIPOS: Record<string, ColoresEquipo> = {
  ARI: { primario: '#97233F', secundario: '#FFB612', nombre: 'Arizona' },
  ATL: { primario: '#A71930', secundario: '#000000', nombre: 'Atlanta' },
  BAL: { primario: '#241773', secundario: '#9E7C0C', nombre: 'Baltimore' },
  BUF: { primario: '#00338D', secundario: '#C60C30', nombre: 'Buffalo' },
  CAR: { primario: '#0085CA', secundario: '#101820', nombre: 'Carolina' },
  CHI: { primario: '#0B162A', secundario: '#C83803', nombre: 'Chicago' },
  CIN: { primario: '#FB4F14', secundario: '#000000', nombre: 'Cincinnati' },
  CLE: { primario: '#311D00', secundario: '#FF3C00', nombre: 'Cleveland' },
  DAL: { primario: '#003594', secundario: '#869397', nombre: 'Dallas' },
  DEN: { primario: '#FB4F14', secundario: '#002244', nombre: 'Denver' },
  DET: { primario: '#0076B6', secundario: '#B0B7BC', nombre: 'Detroit' },
  GB: { primario: '#203731', secundario: '#FFB612', nombre: 'Green Bay' },
  HOU: { primario: '#03202F', secundario: '#A71930', nombre: 'Houston' },
  IND: { primario: '#002C5F', secundario: '#A2AAAD', nombre: 'Indianapolis' },
  JAX: { primario: '#006778', secundario: '#D7A22A', nombre: 'Jacksonville' },
  KC: { primario: '#E31837', secundario: '#FFB81C', nombre: 'Kansas City' },
  LA: { primario: '#003594', secundario: '#FFA300', nombre: 'Los Angeles (Rams)' },
  LAC: { primario: '#0080C6', secundario: '#FFC20E', nombre: 'Los Angeles (Chargers)' },
  LV: { primario: '#000000', secundario: '#A5ACAF', nombre: 'Las Vegas' },
  MIA: { primario: '#008E97', secundario: '#FC4C02', nombre: 'Miami' },
  MIN: { primario: '#4F2683', secundario: '#FFC62F', nombre: 'Minnesota' },
  NE: { primario: '#002244', secundario: '#C60C30', nombre: 'New England' },
  NO: { primario: '#D3BC8D', secundario: '#101820', nombre: 'New Orleans' },
  NYG: { primario: '#0B2265', secundario: '#A71930', nombre: 'New York (Giants)' },
  NYJ: { primario: '#125740', secundario: '#000000', nombre: 'New York (Jets)' },
  PHI: { primario: '#004C54', secundario: '#A5ACAF', nombre: 'Philadelphia' },
  PIT: { primario: '#FFB612', secundario: '#101820', nombre: 'Pittsburgh' },
  SEA: { primario: '#002244', secundario: '#69BE28', nombre: 'Seattle' },
  SF: { primario: '#AA0000', secundario: '#B3995D', nombre: 'San Francisco' },
  TB: { primario: '#D50A0A', secundario: '#34302B', nombre: 'Tampa Bay' },
  TEN: { primario: '#0C2340', secundario: '#4B92DB', nombre: 'Tennessee' },
  WAS: { primario: '#5A1414', secundario: '#FFB612', nombre: 'Washington' },
}

const GRIS: ColoresEquipo = { primario: '#6b7280', secundario: '#374151', nombre: '' }

export function coloresEquipo(siglas: string | null | undefined): ColoresEquipo {
  return (siglas && PALETA_EQUIPOS[siglas]) || { ...GRIS, nombre: siglas ?? '' }
}

/** Luminancia relativa (WCAG) de un color #RRGGBB. */
function luminancia(hex: string): number {
  const v = hex.replace('#', '')
  const canal = (i: number) => {
    const c = parseInt(v.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * canal(0) + 0.7152 * canal(2) + 0.0722 * canal(4)
}

/** Texto blanco u oscuro según el fondo, para que siempre se lea. */
export function colorTexto(fondo: string): string {
  return luminancia(fondo) > 0.5 ? '#111827' : '#ffffff'
}
