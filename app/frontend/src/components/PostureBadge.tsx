import type { Posture } from '../api/types'

interface PostureBadgeProps {
  posture: Posture
}

// Fallback caso o backend não envie cor: mapeia label -> hex do design system.
const LABEL_COLORS: Record<string, string> = {
  ACUMULAR: '#16a34a',
  NEUTRO: '#3b82f6',
  CAUTELOSO: '#f59e0b',
  DEFENSIVO: '#ef4444',
}

export function PostureBadge({ posture }: PostureBadgeProps) {
  const color =
    posture.color || LABEL_COLORS[posture.label?.toUpperCase()] || '#3b82f6'

  return (
    <div
      className="inline-flex items-center gap-2 rounded-full border px-4 py-1 text-sm font-semibold"
      style={{
        color,
        borderColor: color,
        backgroundColor: `${color}1A`, // ~10% alpha
      }}
      title={posture.action || posture.label}
    >
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ backgroundColor: color }}
      />
      <span className="uppercase tracking-wide">{posture.label}</span>
      {posture.environment ? (
        <span className="font-mono text-xs font-normal opacity-70">
          · {posture.environment}
        </span>
      ) : null}
    </div>
  )
}
