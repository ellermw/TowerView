import { useState } from 'react'
import { useMutation } from 'react-query'
import toast from 'react-hot-toast'
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline'
import api from '../services/api'
import { useAuthStore } from '../store/authStore'
import ChangePasswordModal from '../components/ChangePasswordModal'

interface LoginRequest {
  admin_login?: {
    username: string
    password: string
  }
  media_login?: {
    server_id: number
    provider: string
    username: string
    password: string
  }
  local_login?: {
    username: string
    password: string
  }
}

export default function LoginPage() {
  const [loginType, setLoginType] = useState<'admin' | 'local'>('admin')
  const [showPassword, setShowPassword] = useState(false)

  const [showChangePassword, setShowChangePassword] = useState(false)
  const [tempAuthData, setTempAuthData] = useState<any>(null)
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    server_id: '',
    provider: 'plex',
  })

  const { setAuth } = useAuthStore()

  const loginMutation = useMutation(
    async (data: LoginRequest) => {
      const response = await api.post('/auth/login', data)
      return response.data
    },
    {
      onSuccess: (data) => {
        // Check if password change is required
        if (data.must_change_password) {
          // Store auth data temporarily
          setTempAuthData({
            user: {
              id: 1, // This would come from the token or separate API call
              username: formData.username,
              type: loginType,
            },
            access_token: data.access_token,
            refresh_token: data.refresh_token,
          })
          // Set auth temporarily so the API calls work
          api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`
          // Show password change modal
          setShowChangePassword(true)
          toast('You must change your password before continuing', { icon: '⚠️' })
        } else {
          // Normal login flow
          const user = {
            id: 1, // This would come from the token or separate API call
            username: formData.username,
            type: loginType === 'media' ? 'media_user' as const :
                  loginType === 'local' ? 'local_user' as const : 'admin' as const,
          }
          setAuth(user, data.access_token, data.refresh_token)
          toast.success('Login successful!')
        }
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || error.message || 'Login failed')
      },
    }
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (loginType === 'admin') {
      loginMutation.mutate({
        admin_login: {
          username: formData.username,
          password: formData.password,
        },
      })
    } else if (loginType === 'local') {
      loginMutation.mutate({
        local_login: {
          username: formData.username,
          password: formData.password,
        },
      })
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900 dark:text-white">
            Welcome to Towerview
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
            Multi-server media monitoring platform
          </p>
        </div>

        <div className="bg-white dark:bg-slate-800 shadow rounded-lg p-6">
          {/* Login Type Toggle */}
          <div className="flex rounded-lg bg-slate-100 dark:bg-slate-700 p-1 mb-6">
            <button
              type="button"
              className={`flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors ${
                loginType === 'admin'
                  ? 'bg-white dark:bg-slate-600 text-slate-900 dark:text-white shadow'
                  : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
              }`}
              onClick={() => setLoginType('admin')}
            >
              Admin
            </button>
            <button
              type="button"
              className={`flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors ${
                loginType === 'local'
                  ? 'bg-white dark:bg-slate-600 text-slate-900 dark:text-white shadow'
                  : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
              }`}
              onClick={() => setLoginType('local')}
            >
              Local User
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">

            <div>
              <label htmlFor="username" className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Username
              </label>
              <input
                id="username"
                type="text"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="input mt-1"
                placeholder="Enter your username"
                required
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Password
              </label>
              <div className="relative mt-1">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="input pr-10"
                  placeholder="Enter your password"
                  required
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeSlashIcon className="h-5 w-5 text-slate-400" />
                  ) : (
                    <EyeIcon className="h-5 w-5 text-slate-400" />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loginMutation.isLoading}
              className="w-full btn-primary py-3"
            >
              {loginMutation.isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>

      <ChangePasswordModal
        isOpen={showChangePassword}
        onClose={() => setShowChangePassword(false)}
        forcedChange={true}
        onSuccess={() => {
          // Complete login after password change
          if (tempAuthData) {
            setAuth(tempAuthData.user, tempAuthData.access_token, tempAuthData.refresh_token)
            setShowChangePassword(false)
            toast.success('Password changed! Logging you in...')
          }
        }}
      />
    </div>
  )
}