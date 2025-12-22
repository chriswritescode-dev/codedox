import { memo } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface FilterDropdownProps {
  value: string
  onChange: (value: string) => void
}

export const FilterDropdown = memo(({ value, onChange }: FilterDropdownProps) => {
  return (
    <div className="flex items-center gap-2">
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-[140px]">
          <SelectValue placeholder="All Sources" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Sources</SelectItem>
          <SelectItem value="has-snippets">Has Snippets</SelectItem>
          <SelectItem value="0">No Snippets</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
})

FilterDropdown.displayName = "FilterDropdown"
