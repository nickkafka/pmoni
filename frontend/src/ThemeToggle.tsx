import { useTheme } from './themeContext'

/** Circular icon button of §6.7, carrying a label so it is not icon-only. */
export function ThemeToggle() {
  const { isLight, toggleTheme } = useTheme()
  return (
    <button
      className="icon-button"
      onClick={toggleTheme}
      title={isLight ? 'Usar tema escuro' : 'Usar tema claro'}
      aria-label={isLight ? 'Usar tema escuro' : 'Usar tema claro'}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        {isLight ? (
          <path
            d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
        ) : (
          <>
            <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="1.8" />
            <path
              d="M12 2.5v2.2M12 19.3v2.2M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
          </>
        )}
      </svg>
    </button>
  )
}
