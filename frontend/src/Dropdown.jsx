import { useCallback, useEffect, useRef, useState } from 'react'

export default function Dropdown({ value, onChange, options, label }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  const selected = options.find((o) => o.value === value)

  const handleSelect = useCallback(
    (optionValue) => {
      onChange(optionValue)
      setOpen(false)
    },
    [onChange],
  )

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false)
      }
    }
    const handleEscape = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [])

  return (
    <div className="dropdown-wrap" ref={ref}>
      <button
        type="button"
        className={`dropdown-trigger ${open ? 'dropdown-trigger-open' : ''}`}
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={label}
      >
        <span className="dropdown-trigger-text">{selected?.label ?? value}</span>
        <svg
          className={`dropdown-chevron ${open ? 'dropdown-chevron-open' : ''}`}
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            d="M4.5 6.25L8 9.75L11.5 6.25"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <div className="dropdown-panel" role="listbox" aria-label={label}>
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              role="option"
              aria-selected={option.value === value}
              className={`dropdown-option ${option.value === value ? 'dropdown-option-active' : ''}`}
              onClick={() => handleSelect(option.value)}
            >
              {option.value === value && (
                <svg className="dropdown-check" width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M3 7.5L5.5 10L11 4"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
              <span>{option.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
