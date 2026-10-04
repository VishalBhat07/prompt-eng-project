export type Severity = 'CRITICAL' | 'HIGH' | 'CLEAN';

const META: Record<Severity, { color: string; icon: string; label: string }> = {
  CRITICAL: { color: 'var(--crit)', icon: '⛨', label: 'CRITICAL' },
  HIGH: { color: 'var(--high)', icon: '▲', label: 'HIGH' },
  CLEAN: { color: 'var(--clean)', icon: '●', label: 'CLEAN' },
};

export function SeverityBadge({ level, pulse = false }: { level: Severity; pulse?: boolean }) {
  const m = META[level];
  return (
    <span
      role="status"
      aria-label={`severity ${m.label}`}
      className={pulse ? 'pulse-once' : undefined}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        color: m.color, border: `1px solid ${m.color}`, borderRadius: 999,
        padding: '2px 10px', fontSize: 13, fontWeight: 600,
      }}
    >
      <span aria-hidden>{m.icon}</span> {m.label}
    </span>
  );
}

export function RiskMeter({ score, showNumber = true }: { score: number; showNumber?: boolean }) {
  const pct = Math.round(score * 100);
  const level: Severity = score >= 0.8 ? 'CRITICAL' : score >= 0.6 ? 'HIGH' : 'CLEAN';
  const color = META[level].color;
  const segments = Array.from({ length: 10 }, (_, i) => i < Math.round(score * 10));
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }} role="meter"
      aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`risk ${pct} of 100`}>
      <span style={{ display: 'inline-flex', gap: 2 }}>
        {segments.map((on, i) => (
          <span key={i} style={{
            width: 14, height: 8, borderRadius: 2,
            background: on ? color : 'rgba(255,255,255,0.12)',
            borderLeft: (i === 3 || i === 6 || i === 8) ? '1px solid rgba(255,255,255,0.35)' : undefined,
          }} />
        ))}
      </span>
      {showNumber && <span className="mono" style={{ color, fontSize: 14 }}>{pct}</span>}
    </span>
  );
}
