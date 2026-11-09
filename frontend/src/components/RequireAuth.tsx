import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Navigate, Outlet } from 'react-router-dom'

import { authApi } from '../api/client'
import { useAuthStore } from '../store/auth'
import { AuthSplash } from './AppShell'

export function RequireAuth() {
  const user = useAuthStore((state) => state.user)
  const setUser = useAuthStore((state) => state.setUser)
  const session = useQuery({
    queryKey: ['session'],
    queryFn: authApi.me,
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (session.data) setUser(session.data)
  }, [session.data, setUser])

  if (session.isPending || (session.data && !user)) {
    return <AuthSplash />
  }

  if (session.isError || !session.data) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
