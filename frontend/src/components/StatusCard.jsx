import { PANEL_STATE_STYLE } from '../data/constants'

/**
 * One row of the left-hand system column. `state` comes from the backend's
 * status panels, which derive it from live RSP/monitor/signer objects.
 */
export default function StatusCard({ label, state, value, detail }) {
  const tone = PANEL_STATE_STYLE[state] ?? 'text-slate-400'
  return (
    <div className="glass-quiet flex items-start gap-3 px-3.5 py-3">
      <span
        className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${tone.replace('text-', 'bg-')}`}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-[13px] font-medium text-slate-200">{label}</p>
          <p className={`num shrink-0 text-[11px] font-semibold ${tone}`}>{state}</p>
        </div>
        <p className="num mt-0.5 truncate text-[12px] text-slate-400">{value}</p>
        {detail && <p className="mt-0.5 truncate text-[11px] text-slate-500" title={detail}>{detail}</p>}
      </div>
    </div>
  )
}
