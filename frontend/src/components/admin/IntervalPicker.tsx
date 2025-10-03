import { useState, useEffect } from 'react'

interface IntervalPickerProps {
  value: number // Value in seconds
  onChange: (seconds: number) => void
  label?: string
  min?: number // Minimum value in seconds
  max?: number // Maximum value in seconds
}

export default function IntervalPicker({
  value,
  onChange,
  label,
  min = 1,
  max = 604800 // 1 week
}: IntervalPickerProps) {
  // Convert seconds to unit and value
  const getUnitAndValue = (seconds: number) => {
    if (seconds % 86400 === 0 && seconds >= 86400) {
      return { value: seconds / 86400, unit: 'days' }
    } else if (seconds % 3600 === 0 && seconds >= 3600) {
      return { value: seconds / 3600, unit: 'hours' }
    } else if (seconds % 60 === 0 && seconds >= 60) {
      return { value: seconds / 60, unit: 'minutes' }
    } else {
      return { value: seconds, unit: 'seconds' }
    }
  }

  const initial = getUnitAndValue(value)
  const [inputValue, setInputValue] = useState(initial.value)
  const [unit, setUnit] = useState(initial.unit)

  useEffect(() => {
    const updated = getUnitAndValue(value)
    setInputValue(updated.value)
    setUnit(updated.unit)
  }, [value])

  const handleChange = (newValue: number, newUnit: string) => {
    let seconds = newValue

    switch(newUnit) {
      case 'minutes':
        seconds = newValue * 60
        break
      case 'hours':
        seconds = newValue * 3600
        break
      case 'days':
        seconds = newValue * 86400
        break
    }

    // Enforce min/max limits
    if (seconds < min) seconds = min
    if (seconds > max) seconds = max

    onChange(seconds)
  }

  const handleValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = parseFloat(e.target.value) || 0
    setInputValue(newValue)
    handleChange(newValue, unit)
  }

  const handleUnitChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newUnit = e.target.value
    setUnit(newUnit)
    handleChange(inputValue, newUnit)
  }

  // Format display text
  const formatInterval = (seconds: number) => {
    const { value: displayValue, unit: displayUnit } = getUnitAndValue(seconds)
    const unitLabel = displayValue === 1 ? displayUnit.slice(0, -1) : displayUnit
    return `${displayValue} ${unitLabel}`
  }

  return (
    <div className="flex items-center space-x-2">
      {label && <label className="text-sm text-gray-600 dark:text-gray-400 min-w-[100px]">{label}</label>}
      <div className="flex items-center space-x-2">
        <input
          type="number"
          min="1"
          step="1"
          value={inputValue}
          onChange={handleValueChange}
          className="w-20 px-2 py-1 text-sm border border-gray-300 rounded dark:border-gray-600 dark:bg-gray-700"
        />
        <select
          value={unit}
          onChange={handleUnitChange}
          className="px-2 py-1 text-sm border border-gray-300 rounded dark:border-gray-600 dark:bg-gray-700"
        >
          <option value="seconds">Seconds</option>
          <option value="minutes">Minutes</option>
          <option value="hours">Hours</option>
          <option value="days">Days</option>
        </select>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          ({formatInterval(value)})
        </span>
      </div>
    </div>
  )
}