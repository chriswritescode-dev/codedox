
interface ProgressBarProps {
  current: number
  total: number
  label?: string
  showPercentage?: boolean
  className?: string
  height?: string
}

export default function ProgressBar({ 
  current, 
  total, 
  label, 
  showPercentage = true,
  className = '',
  height = 'h-2'
}: ProgressBarProps) {
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0
  
  return (
    <div className={`w-full ${className}`}>
      {(label || showPercentage) && (
        <div className="flex justify-between text-sm mb-1">
          {label && <span className="text-muted-foreground">{label}</span>}
          {showPercentage && <span className="text-muted-foreground">{percentage}%</span>}
        </div>
      )}
      <div className={`w-full bg-secondary rounded-full overflow-hidden ${height}`}>
        <div 
          className={`bg-primary ${height} rounded-full transition-all duration-300 ease-out`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}