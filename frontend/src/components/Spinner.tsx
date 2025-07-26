import { cn } from '../lib/utils'

interface SpinnerProps {
  className?: string
  size?: 'xs' | 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  xs: 'h-3 w-3 border',
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-8 w-8 border-3'
}

export function Spinner({ className, size = 'sm' }: SpinnerProps) {
  return (
    <div
      className={cn(
        sizeClasses[size],
        'border-current/30 border-t-current rounded-full animate-spin',
        className
      )}
    />
  )
}