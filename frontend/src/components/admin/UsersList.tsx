import { useState } from 'react'
import { useQuery } from 'react-query'
import {
  UserIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  EyeSlashIcon,
  ClockIcon,
  ServerIcon
} from '@heroicons/react/24/outline'
import api from '../../services/api'

interface ServerUser {
  user_id: string
  username: string
  email?: string
  thumb?: string
  admin: boolean
  disabled: boolean
  hidden: boolean
  restricted: boolean
  protected: boolean
  guest: boolean
  home: boolean
  last_activity?: string
  last_login?: string
  server_name?: string
  server_id?: number
  server_type?: string
}

export default function UsersList() {
  const [refreshInterval, setRefreshInterval] = useState(30000) // 30 seconds

  const { data: users = [], isLoading, error } = useQuery<ServerUser[]>(
    'admin-users',
    () => api.get('/admin/users').then(res => res.data),
    {
      refetchInterval: refreshInterval,
      refetchIntervalInBackground: true
    }
  )

  const getUserStatusColor = (user: ServerUser) => {
    if (user.disabled) {
      return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
    }
    if (user.admin) {
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
    }
    if (user.guest) {
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
    }
    return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
  }

  const getUserStatusText = (user: ServerUser) => {
    if (user.disabled) return 'Disabled'
    if (user.admin) return 'Administrator'
    if (user.guest) return 'Guest'
    return 'Active User'
  }

  const formatLastActivity = (dateString?: string) => {
    if (!dateString) return 'Never'
    try {
      const date = new Date(dateString)
      const now = new Date()
      const diffInHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60))

      if (diffInHours < 1) return 'Less than 1 hour ago'
      if (diffInHours < 24) return `${diffInHours} hours ago`

      const diffInDays = Math.floor(diffInHours / 24)
      if (diffInDays < 7) return `${diffInDays} days ago`

      const diffInWeeks = Math.floor(diffInDays / 7)
      if (diffInWeeks < 4) return `${diffInWeeks} weeks ago`

      return date.toLocaleDateString()
    } catch {
      return 'Unknown'
    }
  }

  const getServerTypeIcon = (serverType?: string) => {
    return <ServerIcon className="h-4 w-4" />
  }

  if (isLoading) {
    return (
      <div className="px-4 py-6 sm:px-6">
        <div className="flex justify-center py-8">
          <div className="text-slate-600 dark:text-slate-400">Loading users...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 py-6 sm:px-6">
        <div className="text-center py-8">
          <div className="text-red-600 dark:text-red-400">Failed to load users</div>
        </div>
      </div>
    )
  }

  // Group users by server
  const usersByServer = users.reduce((acc, user) => {
    const serverKey = `${user.server_name} (${user.server_type})`
    if (!acc[serverKey]) {
      acc[serverKey] = []
    }
    acc[serverKey].push(user)
    return acc
  }, {} as Record<string, ServerUser[]>)

  return (
    <div className="px-4 py-6 sm:px-6">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Server Users
          </h1>
          <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
            View and manage users across all servers
          </p>
        </div>
        <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
          <div className="text-sm text-slate-600 dark:text-slate-400">
            Auto-refresh every {refreshInterval / 1000}s
          </div>
        </div>
      </div>

      {users.length === 0 ? (
        <div className="mt-8 card">
          <div className="card-body text-center py-12">
            <UserIcon className="mx-auto h-12 w-12 text-slate-400" />
            <h3 className="mt-2 text-sm font-medium text-slate-900 dark:text-white">No users found</h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              No users were found on your servers.
            </p>
          </div>
        </div>
      ) : (
        <div className="mt-8 space-y-8">
          {Object.entries(usersByServer).map(([serverName, serverUsers]) => (
            <div key={serverName} className="space-y-4">
              <div className="flex items-center">
                {getServerTypeIcon(serverUsers[0]?.server_type)}
                <h2 className="ml-2 text-lg font-medium text-slate-900 dark:text-white">
                  {serverName}
                </h2>
                <span className="ml-2 text-sm text-slate-500 dark:text-slate-400">
                  ({serverUsers.length} users)
                </span>
              </div>

              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {serverUsers.map((user) => (
                  <div key={`${user.server_id}-${user.user_id}`} className="card">
                    <div className="card-body">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center">
                          <div className="flex-shrink-0">
                            {user.thumb ? (
                              <img
                                className="h-10 w-10 rounded-full"
                                src={user.thumb}
                                alt={user.username}
                              />
                            ) : (
                              <UserIcon className="h-10 w-10 text-slate-400" />
                            )}
                          </div>
                          <div className="ml-3">
                            <h3 className="text-sm font-medium text-slate-900 dark:text-white">
                              {user.username}
                            </h3>
                            {user.email && (
                              <p className="text-xs text-slate-500 dark:text-slate-400">
                                {user.email}
                              </p>
                            )}
                          </div>
                        </div>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getUserStatusColor(user)}`}>
                          {getUserStatusText(user)}
                        </span>
                      </div>

                      <div className="mt-4 grid grid-cols-2 gap-4 text-xs">
                        <div className="flex items-center">
                          <ClockIcon className="h-4 w-4 text-slate-400 mr-1" />
                          <div>
                            <div className="font-medium text-slate-900 dark:text-white">Last Activity</div>
                            <div className="text-slate-500 dark:text-slate-400">
                              {formatLastActivity(user.last_activity)}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center">
                          <UserIcon className="h-4 w-4 text-slate-400 mr-1" />
                          <div>
                            <div className="font-medium text-slate-900 dark:text-white">User Type</div>
                            <div className="text-slate-500 dark:text-slate-400">
                              {user.home ? 'Home User' : user.guest ? 'Guest' : 'Standard'}
                            </div>
                          </div>
                        </div>
                      </div>

                      {(user.restricted || user.protected || user.hidden) && (
                        <div className="mt-4 flex flex-wrap gap-1">
                          {user.restricted && (
                            <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">
                              <ExclamationTriangleIcon className="h-3 w-3 mr-1" />
                              Restricted
                            </span>
                          )}
                          {user.protected && (
                            <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                              <ShieldCheckIcon className="h-3 w-3 mr-1" />
                              Protected
                            </span>
                          )}
                          {user.hidden && (
                            <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200">
                              <EyeSlashIcon className="h-3 w-3 mr-1" />
                              Hidden
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}