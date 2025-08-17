import React from 'react'
import { Filter } from 'lucide-react'

interface FilterDropdownProps {
  value: string
  onChange: (value: string) => void
}

export const FilterDropdown: React.FC<FilterDropdownProps> = ({ value, onChange }) => {
  return (
    <div className="flex items-center gap-2">
      <Filter className="h-4 w-4 text-muted-foreground" />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 bg-secondary border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
      >
        <option value="all">All Sources</option>
        <option value="has-snippets">Has Snippets</option>
        <option value="0">No Snippets</option>
      </select>
    </div>
  )
}