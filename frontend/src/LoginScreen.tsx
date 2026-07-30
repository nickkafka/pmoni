import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from './authContext'
import { ThemeToggle } from './ThemeToggle'
import './LoginScreen.css'

export default function LoginScreen() {
  const { signIn } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [signingIn, setSigningIn] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSigningIn(true)
    setError(null)
    try {
      await signIn(username.trim(), password)
    } catch (failure) {
      setError((failure as Error).message)
      setPassword('')
    } finally {
      setSigningIn(false)
    }
  }

  return (
    <main className="login">
      <form className="login__card" onSubmit={submit}>
        <div className="login__heading">
          <span className="login__brand">pMoni</span>
          <ThemeToggle />
        </div>
        <p className="label-caps login__label">Administração</p>
        <p className="login__hint">Entre para alterar equipamentos e moradores.</p>

        <label className="login__field">
          <span className="label-caps">Usuário</span>
          <input
            className="field"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoFocus
            autoComplete="username"
            required
          />
        </label>
        <label className="login__field">
          <span className="label-caps">Senha</span>
          <input
            className="field"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error && (
          <p className="login__error" role="alert">
            {error}
          </p>
        )}

        <button className="button button--primary login__submit" type="submit" disabled={signingIn}>
          {signingIn ? 'Entrando…' : 'Entrar'}
        </button>
        <Link className="login__back" to="/">
          Voltar para a portaria
        </Link>
      </form>
    </main>
  )
}
