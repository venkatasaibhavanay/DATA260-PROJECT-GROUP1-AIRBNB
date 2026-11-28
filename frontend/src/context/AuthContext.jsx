// Signed-in user for the whole app. Any page can use:
//   const { user, loading, signIn, signOut, setSession } = useAuth()
// user = { id, role: 'guest'|'host'|'admin', name, email } or null.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { clearToken, getToken, setToken } from '../services/api.js'
import { authApi } from '../services/users.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getToken()))

  useEffect(() => {
    if (!getToken()) return
    authApi.me()
      .then((res) => setUser(res.data))
      .catch(() => { clearToken(); setUser(null) })
      .finally(() => setLoading(false))
  }, [])

  const setSession = useCallback((accessToken, nextUser) => {
    setToken(accessToken)
    setUser(nextUser)
  }, [])

  const signIn = useCallback(async (email, password, role) => {
    const res = await authApi.login(email, password, role)
    setSession(res.data.access_token, res.data.user)
    return res.data.user
  }, [setSession])

  const signOut = useCallback(async () => {
    try { await authApi.logout() } catch { /* token may already be invalid */ }
    clearToken()
    setUser(null)
  }, [])

  const forget = useCallback(() => { clearToken(); setUser(null) }, [])

  const value = useMemo(() => ({ user, loading, signIn, signOut, setSession, forget }),
    [user, loading, signIn, signOut, setSession, forget])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
