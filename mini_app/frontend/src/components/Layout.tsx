import { ReactNode, useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import BottomNav from './BottomNav'
import { useTelegram } from '../hooks/useTelegram'
import { useAuthStore } from '../store'
import { authAPI } from '../lib/api'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { initData, backButton } = useTelegram()
  const { isAuthenticated, setAuth, logout } = useAuthStore()
  const [authError, setAuthError] = useState<string | null>(null)

  // Listen for 401 events from axios interceptor
  useEffect(() => {
    const handler = () => {
      logout()
      setAuthError('Sessiya tugadi. Qayta kiring.')
    }
    window.addEventListener('auth:unauthorized', handler)
    return () => window.removeEventListener('auth:unauthorized', handler)
  }, [logout])

  // Authenticate on mount
  useEffect(() => {
    async function authenticate() {
      if (initData && !isAuthenticated) {
        try {
          setAuthError(null)
          const response = await authAPI.authenticate(initData)
          if (response.success && response.user) {
            setAuth('telegram-session', {
              user_id: response.user.user_id,
              username: response.user.username || '',
              full_name: response.user.full_name || '',
              balance: response.user.balance || 0,
              referral_count: response.user.referral_count || 0,
              referral_earnings: response.user.referral_earnings || 0,
              is_banned: response.user.is_banned || false
            })
          }
        } catch (error: any) {
          console.error('Auth error:', error)
          const msg = error?.response?.data?.detail || 'Autentifikatsiya xatosi'
          setAuthError(msg)
        }
      }
    }
    authenticate()
  }, [initData, isAuthenticated, setAuth])

  // Handle back button
  useEffect(() => {
    if (location.pathname !== '/') {
      backButton.show(() => {
        navigate(-1)
      })
    } else {
      backButton.hide()
    }

    return () => {
      backButton.hide()
    }
  }, [location.pathname, backButton, navigate])

  return (
    <div className="min-h-screen bg-tg-bg pb-20">
      {authError && (
        <div className="mx-4 mt-2 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {authError}
        </div>
      )}
      <AnimatePresence mode="wait">
        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
          className="px-4 py-4"
        >
          {children}
        </motion.main>
      </AnimatePresence>
      <BottomNav />
    </div>
  )
}
