import { createContext, useContext } from 'react'

export type Theme = 'dark' | 'light'

export type ThemeControl = {
  theme: Theme
  isLight: boolean
  toggleTheme: () => void
}

export const ThemeContext = createContext<ThemeControl>({
  theme: 'dark',
  isLight: false,
  toggleTheme: () => {},
})

export function useTheme(): ThemeControl {
  return useContext(ThemeContext)
}

export const THEME_STORAGE_KEY = 'pmoni-theme'

/** Dark is the default: the booth screen is watched in a dim guardhouse. */
export function storedTheme(): Theme {
  return localStorage.getItem(THEME_STORAGE_KEY) === 'light' ? 'light' : 'dark'
}
