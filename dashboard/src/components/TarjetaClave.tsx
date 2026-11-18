import type { NumeroClave } from '../types'

interface Props {
  clave: NumeroClave
}

function pct(valor: number | null): string {
  return valor === null || valor === undefined ? 's/d' : `${valor.toFixed(1)}%`
}

/** Número clave como marcador de transmisión. */
export default function TarjetaClave({ clave }: Props) {
  return (
    <section className="overflow-hidden rounded-xl bg-nfl-navy text-white shadow-xl shadow-black/40 ring-1 ring-white/10">
      <div className="flex items-center justify-between bg-nfl-red px-4 py-1">
        <h2 className="font-titular text-sm font-black uppercase italic tracking-wider">Número clave</h2>
        <span className="text-xs font-semibold uppercase tracking-wide text-white/90">Umbral: {clave.umbral}</span>
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 p-4 sm:p-6">
        <div className="text-center">
          <p className="marcador font-titular text-5xl font-black italic sm:text-7xl">{pct(clave.x_pct_snaps)}</p>
          <p className="mt-1 text-xs font-semibold uppercase tracking-widest text-blue-200 sm:text-sm">de los snaps</p>
        </div>
        <p className="font-titular text-4xl font-black text-nfl-gold sm:text-6xl" aria-hidden="true">
          →
        </p>
        <div className="text-center">
          <p className="marcador font-titular text-5xl font-black italic text-nfl-gold sm:text-7xl">{pct(clave.y_pct_offsides)}</p>
          <p className="mt-1 text-xs font-semibold uppercase tracking-widest text-blue-200 sm:text-sm">de los offsides</p>
        </div>
      </div>
    </section>
  )
}
