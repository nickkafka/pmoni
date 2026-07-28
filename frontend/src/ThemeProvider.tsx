import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { THEME_STORAGE_KEY, ThemeContext, storedTheme } from './themeContext'
import type { Theme } from './themeContext'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(storedTheme)

  useEffect(() => {
    localStorage.setItem(THEME_STORAGE_KEY, theme)
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const toggleTheme = useCallback(
    () => setTheme((current) => (current === 'light' ? 'dark' : 'light')),
    [],
  )

  const control = useMemo(
    () => ({ theme, isLight: theme === 'light', toggleTheme }),
    [theme, toggleTheme],
  )

  return <ThemeContext.Provider value={control}>{children}</ThemeContext.Provider>
}
