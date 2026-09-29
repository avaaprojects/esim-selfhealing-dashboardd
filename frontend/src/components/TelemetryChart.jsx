import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const AXIS = { stroke: 'rgba(148,163,184,0.35)', fontSize: 10, fontFamily: 'JetBrains Mono, monospace' }

function ChartTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null
  return (
    <div className="glass px-3 py-2 text-[11px]">
      <p className="num text-slate-400">sample {label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="num mt-0.5 text-slate-100">
          <span className="mr-2 inline-block h-1.5 w-1.5 rounded-full align-middle" style={{ background: p.color }} />
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(3) : p.value}
          {unit ? ` ${unit}` : ''}
        </p>
      ))}
    </div>
  )
}

/**
 * The anomaly-score trace: g_t against the chi-square threshold.
 *
 * This is the single most informative telemetry view in the system, because the
 * threshold line is exactly the decision boundary MONITOR uses to open an
 * incident — crossings are visible rather than inferred. `markerIndex` draws a
 * vertical line at the sample that opened a specific incident.
 */
export function AnomalyChart({ samples = [], height = 190, markerIndex = null }) {
  const data = samples.map((s, i) => ({
    i,
    score: s.score,
    threshold: s.threshold,
    triggered: s.triggered,
  }))
  const threshold = samples.at(-1)?.threshold ?? null

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: -18 }}>
        <defs>
          <linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22D3EE" stopOpacity={0.45} />
            <stop offset="100%" stopColor="#22D3EE" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(148,163,184,0.09)" vertical={false} />
        <XAxis dataKey="i" tick={AXIS} tickLine={false} axisLine={false} minTickGap={36} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={44} />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'rgba(148,163,184,0.3)' }} />
        {threshold !== null && (
          <ReferenceLine
            y={threshold}
            stroke="#FB7185"
            strokeDasharray="4 4"
            label={{
              value: `chi2 = ${threshold.toFixed(1)}`,
              fill: '#FB7185',
              fontSize: 10,
              position: 'insideTopRight',
              fontFamily: 'JetBrains Mono, monospace',
            }}
          />
        )}
        {markerIndex !== null && markerIndex !== undefined && (
          <ReferenceLine
            x={markerIndex}
            stroke="#FBBF24"
            strokeDasharray="2 3"
            label={{
              value: 'incident opened',
              fill: '#FBBF24',
              fontSize: 10,
              position: 'insideTopLeft',
              fontFamily: 'JetBrains Mono, monospace',
            }}
          />
        )}
        <Area
          type="monotone"
          dataKey="score"
          name="g_t"
          stroke="#22D3EE"
          strokeWidth={1.6}
          fill="url(#scoreFill)"
          isAnimationActive={false}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

/** One telemetry channel over time — the five real features, never CPU/RAM. */
export function FeatureChart({ samples = [], featureKey, color = '#22D3EE', height = 120, unit }) {
  const data = samples.map((s, i) => ({ i, v: s.features?.[featureKey] }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -20 }}>
        <CartesianGrid stroke="rgba(148,163,184,0.07)" vertical={false} />
        <XAxis dataKey="i" tick={AXIS} tickLine={false} axisLine={false} minTickGap={40} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={46} domain={['auto', 'auto']} />
        <Tooltip content={<ChartTooltip unit={unit} />} cursor={{ stroke: 'rgba(148,163,184,0.25)' }} />
        <Line
          type="monotone"
          dataKey="v"
          name={featureKey}
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

/** Compact sparkline for the Overview column. */
export function MiniTelemetry({ samples = [], featureKey = 'score', height = 54, color = '#22D3EE' }) {
  const data = samples.map((s, i) => ({
    i,
    v: featureKey === 'score' ? s.score : s.features?.[featureKey],
  }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`mini-${featureKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.5} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.3}
          fill={`url(#mini-${featureKey})`}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
