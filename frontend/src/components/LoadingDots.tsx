export default function LoadingDots() {
  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', padding: '4px 0' }}>
      <span className="bounce-dot" />
      <span className="bounce-dot" />
      <span className="bounce-dot" />
    </span>
  )
}
