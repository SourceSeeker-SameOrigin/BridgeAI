import { useState } from 'react'
import { StarFilled, StarOutlined } from '@ant-design/icons'

interface RatingStarsProps {
  value: number
  onChange?: (rating: number) => void
}

export default function RatingStars({ value, onChange }: RatingStarsProps) {
  const [hover, setHover] = useState(0)

  return (
    <div
      style={{
        display: 'flex',
        gap: 2,
        marginTop: 6,
        opacity: value > 0 ? 1 : 0.4,
        transition: 'opacity 0.2s',
      }}
      onMouseLeave={() => setHover(0)}
    >
      {[1, 2, 3, 4, 5].map((star) => {
        const filled = star <= (hover || value)
        return (
          <span
            key={star}
            onMouseEnter={() => setHover(star)}
            onClick={() => onChange?.(star)}
            style={{
              cursor: onChange ? 'pointer' : 'default',
              fontSize: 14,
              color: filled ? '#f59e0b' : '#475569',
              transition: 'color 0.15s',
            }}
          >
            {filled ? <StarFilled /> : <StarOutlined />}
          </span>
        )
      })}
    </div>
  )
}
