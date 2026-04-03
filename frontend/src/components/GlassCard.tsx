import type { CSSProperties, ReactNode } from 'react'

interface GlassCardProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
  hoverable?: boolean
  onClick?: () => void
}

export default function GlassCard({
  children,
  className = '',
  style,
  hoverable = true,
  onClick,
}: GlassCardProps) {
  return (
    <div
      className={`glass-card ${hoverable ? 'cursor-pointer' : ''} ${className}`}
      style={{ padding: 20, ...style }}
      onClick={onClick}
    >
      {children}
    </div>
  )
}
