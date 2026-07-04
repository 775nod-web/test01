interface StatTileProps {
  label: string
  value: string
  note?: string
  status?: 'warning'
}

export function StatTile({ label, value, note, status }: StatTileProps) {
  return (
    <div className={`stat-tile${status ? ` status-${status}` : ''}`}>
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {note && <p className="stat-note">{note}</p>}
    </div>
  )
}
