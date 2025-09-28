import { useState, useEffect } from 'react'
import { Dialog } from '@headlessui/react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import api from '../services/api'

interface MediaLoginModalProps {
  isOpen: boolean
  onClose: () => void
  provider: 'plex' | 'emby' | 'jellyfin'
  onSuccess: (token: any) => void
}

export default function MediaLoginModal({ isOpen, onClose, provider, onSuccess }: MediaLoginModalProps) {
  const [loading, setLoading] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  // Plex OAuth state
  const [plexPinId, setPlexPinId] = useState('')
  const [plexPinCode, setPlexPinCode] = useState('')
  const [plexAuthUrl, setPlexAuthUrl] = useState('')
  const [plexClientId, setPlexClientId] = useState('')
  const [checkingPlex, setCheckingPlex] = useState(false)
  const [plexAuthOpened, setPlexAuthOpened] = useState(false)

  // Initialize Plex OAuth when modal opens for Plex
  useEffect(() => {
    if (isOpen && provider === 'plex') {
      initiatePlexOAuth()
    } else {
      // Reset state when modal closes
      setPlexPinId('')
      setPlexPinCode('')
      setPlexAuthUrl('')
      setPlexClientId('')
      setCheckingPlex(false)
      setPlexAuthOpened(false)
    }
  }, [isOpen, provider])

  // Poll for Plex OAuth completion
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null

    if (plexPinId && checkingPlex && plexAuthOpened) {
      interval = setInterval(async () => {
        try {
          const response = await api.post('/auth/media/oauth/plex/check', {
            pin_id: plexPinId,
            client_id: plexClientId
          })

          if (response.data.authenticated) {
            // OAuth complete - authenticate with our backend
            const authResponse = await api.post('/auth/media/authenticate', {
              provider: 'plex',
              auth_token: response.data.auth_token
            })

            setCheckingPlex(false)
            toast.success('Successfully logged in with Plex!')
            onSuccess(authResponse.data)
            // Don't close the modal - let onSuccess handle navigation
          }
        } catch (error: any) {
          // Handle specific error cases
          if (error.response?.status === 404 || error.response?.status === 410) {
            // PIN expired or not found
            setCheckingPlex(false)
            setPlexAuthOpened(false)
            toast.error(error.response?.data?.detail || 'Authentication PIN has expired. Please try again.')
            // Reset OAuth state to allow restart
            setPlexPinId('')
            setPlexPinCode('')
            setPlexAuthUrl('')
            setPlexClientId('')
          } else if (error.response?.status === 400) {
            // Other authentication errors
            setCheckingPlex(false)
            setPlexAuthOpened(false)
            toast.error(error.response?.data?.detail || 'Authentication failed. Please try again.')
          }
          // For other errors, continue polling
        }
      }, 2000) // Check every 2 seconds
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [plexPinId, plexClientId, checkingPlex, plexAuthOpened])

  const initiatePlexOAuth = async () => {
    try {
      setLoading(true)
      const response = await api.post('/auth/media/oauth/plex/init')
      setPlexPinId(response.data.pin_id)
      setPlexPinCode(response.data.pin_code)
      setPlexAuthUrl(response.data.auth_url)
      setPlexClientId(response.data.client_id)
      // Don't start checking yet - wait for user to open auth page
      setCheckingPlex(false)
      setPlexAuthOpened(false)
    } catch (error) {
      toast.error('Failed to initiate Plex authentication')
    } finally {
      setLoading(false)
    }
  }

  const openPlexAuth = () => {
    window.open(plexAuthUrl, '_blank')
    setPlexAuthOpened(true)
    setCheckingPlex(true)
  }

  const handleDirectAuth = async () => {
    if (!username || !password) {
      toast.error('Please enter username and password')
      return
    }

    try {
      setLoading(true)
      const response = await api.post('/auth/media/authenticate', {
        provider,
        username,
        password
      })

      toast.success(`Successfully logged in with ${provider}!`)
      onSuccess(response.data)
      // Don't close the modal - let onSuccess handle navigation
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={isOpen} onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/30" aria-hidden="true" />

      <div className="fixed inset-0 flex items-center justify-center p-4">
        <Dialog.Panel className="mx-auto max-w-md w-full rounded-lg bg-white dark:bg-slate-800 p-6">
          <div className="flex justify-between items-start mb-4">
            <Dialog.Title className="text-lg font-medium text-slate-900 dark:text-white">
              Sign in with {provider === 'plex' ? 'Plex' : provider === 'emby' ? 'Emby' : 'Jellyfin'}
            </Dialog.Title>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-500 dark:hover:text-slate-300"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>

          {provider === 'plex' ? (
            <div className="space-y-4">
              {/* Option to use username/password for Plex */}
              <div className="text-center">
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                  Sign in with your Plex account
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Username or Email
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="input"
                  placeholder="Enter your Plex username or email"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input"
                  placeholder="Enter your Plex password"
                />
              </div>

              <button
                onClick={handleDirectAuth}
                disabled={loading || !username || !password}
                className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Signing in...' : 'Sign in'}
              </button>

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-200 dark:border-slate-700" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-white dark:bg-slate-800 px-2 text-slate-500">Or</span>
                </div>
              </div>

              {plexPinCode ? (
                <div className="space-y-2">
                  {checkingPlex && plexAuthOpened ? (
                    <div className="text-center">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto mb-2"></div>
                      <p className="text-sm text-slate-600 dark:text-slate-400">
                        Waiting for Plex authorization...
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-500">
                        Complete the authorization in the Plex tab, then return here
                      </p>
                    </div>
                  ) : (
                    <button
                      onClick={openPlexAuth}
                      className="btn-secondary w-full"
                    >
                      Sign in with Plex OAuth
                    </button>
                  )}
                </div>
              ) : (
                <button
                  onClick={initiatePlexOAuth}
                  disabled={loading}
                  className="btn-secondary w-full disabled:opacity-50"
                >
                  {loading ? 'Initializing...' : 'Use Plex OAuth instead'}
                </button>
              )}
            </div>
          ) : (
            // Emby and Jellyfin use direct authentication
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="input"
                  placeholder="Enter your username"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input"
                  placeholder="Enter your password"
                />
              </div>

              <button
                onClick={handleDirectAuth}
                disabled={loading || !username || !password}
                className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Signing in...' : 'Sign in'}
              </button>

              {provider === 'emby' && (
                <p className="text-xs text-center text-slate-600 dark:text-slate-400">
                  Supports both local accounts and Emby Connect
                </p>
              )}
            </div>
          )}
        </Dialog.Panel>
      </div>
    </Dialog>
  )
}