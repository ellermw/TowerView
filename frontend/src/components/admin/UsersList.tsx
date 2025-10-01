import { useState } from 'react'
import { useQuery } from 'react-query'
import {
  UserIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  EyeSlashIcon,
  ClockIcon,
  ServerIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  KeyIcon,
  FolderIcon
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

interface Library {
  id: string
  name: string
  title?: string
  type?: string
}

export default function UsersList() {
  const [refreshInterval] = useState(30000) // 30 seconds
  const [collapsedServers, setCollapsedServers] = useState<Set<string>>(new Set())
  const [selectedUser, setSelectedUser] = useState<ServerUser | null>(null)
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false)
  const [isLibraryModalOpen, setIsLibraryModalOpen] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [libraries, setLibraries] = useState<Library[]>([])
  const [selectedLibraries, setSelectedLibraries] = useState<string[]>([])
  const [librariesLoading, setLibrariesLoading] = useState(false)
  const [librariesSaving, setLibrariesSaving] = useState(false)

  const { data: users = [], isLoading, error } = useQuery<ServerUser[]>(
    'admin-users',
    () => api.get('/admin/users').then(res => res.data),
    {
      refetchInterval: refreshInterval,
      refetchIntervalInBackground: true,
      onError: (error: any) => {
        console.error('Failed to fetch users:', error)
        console.error('Error details:', error.response?.data)
      }
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

  const getServerTypeIcon = (_serverType?: string) => {
    return <ServerIcon className="h-4 w-4" />
  }

  const toggleServerCollapse = (serverKey: string) => {
    setCollapsedServers(prev => {
      const newSet = new Set(prev)
      if (newSet.has(serverKey)) {
        newSet.delete(serverKey)
      } else {
        newSet.add(serverKey)
      }
      return newSet
    })
  }

  const openPasswordModal = (user: ServerUser) => {
    setSelectedUser(user)
    setNewPassword('')
    setConfirmPassword('')
    setPasswordError('')
    setIsPasswordModalOpen(true)
  }

  const openLibraryModal = async (user: ServerUser) => {
    setSelectedUser(user)
    setIsLibraryModalOpen(true)

    // Only load libraries for Emby/Jellyfin
    if (user.server_type?.toLowerCase() !== 'plex' && user.server_id) {
      setLibrariesLoading(true)
      try {
        // Fetch available libraries
        const response = await api.get(`/admin/servers/${user.server_id}/libraries`)
        setLibraries(response.data)

        // Fetch user's current library access
        console.log('Fetching library access for user:', user.user_id, 'on server:', user.server_id)
        const accessResponse = await api.get(`/admin/servers/${user.server_id}/users/${user.user_id}/libraries`)
        console.log('Library access response:', accessResponse.data)
        if (accessResponse.data) {
          const accessData = accessResponse.data
          // Pre-select the libraries the user already has access to
          if (accessData.all_libraries && response.data) {
            // If user has access to all libraries, select all
            console.log('User has access to all libraries')
            setSelectedLibraries(response.data.map((lib: Library) => lib.id))
          } else {
            // Otherwise, select only the enabled libraries
            console.log('User has access to specific libraries:', accessData.library_ids)
            setSelectedLibraries(accessData.library_ids || [])
          }
        }
      } catch (error) {
        console.error('Failed to load libraries:', error)
        setSelectedLibraries([])
      } finally {
        setLibrariesLoading(false)
      }
    } else {
      // For Plex or if no server_id, clear the selection
      setSelectedLibraries([])
    }
  }

  const handlePasswordChange = async () => {
    if (!selectedUser || !selectedUser.server_id) return

    // Validate passwords
    if (!newPassword) {
      setPasswordError('Password is required')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match')
      return
    }
    if (newPassword.length < 8) {
      setPasswordError('Password must be at least 8 characters')
      return
    }

    setPasswordLoading(true)
    setPasswordError('')

    try {
      await api.post(
        `/admin/servers/${selectedUser.server_id}/users/${selectedUser.user_id}/password`,
        { new_password: newPassword }
      )

      setIsPasswordModalOpen(false)
      setSelectedUser(null)
      // Show success message (you could add a toast notification here)
    } catch (error: any) {
      setPasswordError(error.response?.data?.detail || 'Failed to change password')
    } finally {
      setPasswordLoading(false)
    }
  }

  const handleLibraryAccessSave = async () => {
    if (!selectedUser || !selectedUser.server_id) return

    setLibrariesSaving(true)

    try {
      await api.post(
        `/admin/servers/${selectedUser.server_id}/users/${selectedUser.user_id}/libraries`,
        selectedLibraries
      )

      setIsLibraryModalOpen(false)
      setSelectedUser(null)
      // Show success message
    } catch (error: any) {
      console.error('Failed to save library access:', error)
    } finally {
      setLibrariesSaving(false)
    }
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
    const errorMessage = (error as any)?.response?.data?.detail || 'Failed to load users'
    return (
      <div className="px-4 py-6 sm:px-6">
        <div className="text-center py-8">
          <div className="text-red-600 dark:text-red-400">{errorMessage}</div>
          <div className="text-sm text-slate-500 mt-2">Check console for details</div>
        </div>
      </div>
    )
  }

  // Group users first by server type, then by server name
  const usersByServerType = users.reduce((acc, user) => {
    const serverType = user.server_type || 'unknown'
    if (!acc[serverType]) {
      acc[serverType] = {}
    }
    const serverName = user.server_name || 'Unknown Server'
    if (!acc[serverType][serverName]) {
      acc[serverType][serverName] = []
    }
    acc[serverType][serverName].push(user)
    return acc
  }, {} as Record<string, Record<string, ServerUser[]>>)

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
        <div className="mt-8 space-y-12">
          {Object.entries(usersByServerType).sort(([a], [b]) => a.localeCompare(b)).map(([serverType, serversByName]) => (
            <div key={serverType} className="space-y-8">
              {/* Server Type Header */}
              <div className="border-b border-slate-200 dark:border-slate-700 pb-2">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white capitalize">
                  {serverType} Servers
                </h2>
              </div>

              {/* Servers within this type */}
              {Object.entries(serversByName).map(([serverName, serverUsers]) => {
                const serverKey = `${serverType}-${serverName}`
                const isCollapsed = collapsedServers.has(serverKey)

                return (
                  <div key={serverKey} className="space-y-4">
                    <div
                      className="flex items-center cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 p-2 rounded-lg transition-colors"
                      onClick={() => toggleServerCollapse(serverKey)}
                    >
                      {isCollapsed ?
                        <ChevronRightIcon className="h-5 w-5 text-slate-500" /> :
                        <ChevronDownIcon className="h-5 w-5 text-slate-500" />
                      }
                      {getServerTypeIcon(serverType)}
                      <h3 className="ml-2 text-lg font-medium text-slate-900 dark:text-white">
                        {serverName}
                      </h3>
                      <span className="ml-2 text-sm text-slate-500 dark:text-slate-400">
                        ({serverUsers.length} users)
                      </span>
                    </div>

                    {!isCollapsed && (
                      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 pl-7">
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

                      {/* Action buttons */}
                      <div className="mt-4 flex gap-2">
                        {(() => {
                          console.log(`User ${user.username} - server_type: "${user.server_type}", lowercase: "${user.server_type?.toLowerCase()}", isPlex: ${user.server_type?.toLowerCase() === 'plex'}`)
                          return user.server_type?.toLowerCase() !== 'plex'
                        })() && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              openPasswordModal(user)
                            }}
                            className="flex-1 px-2 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 dark:text-indigo-400 dark:bg-indigo-900 dark:hover:bg-indigo-800 rounded-md transition-colors"
                          >
                            <KeyIcon className="h-3 w-3 inline mr-1" />
                            Password
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            openLibraryModal(user)
                          }}
                          className={user.server_type?.toLowerCase() === 'plex' ? "w-full px-2 py-1 text-xs font-medium text-green-600 bg-green-50 hover:bg-green-100 dark:text-green-400 dark:bg-green-900 dark:hover:bg-green-800 rounded-md transition-colors" : "flex-1 px-2 py-1 text-xs font-medium text-green-600 bg-green-50 hover:bg-green-100 dark:text-green-400 dark:bg-green-900 dark:hover:bg-green-800 rounded-md transition-colors"}
                        >
                          <FolderIcon className="h-3 w-3 inline mr-1" />
                          Libraries
                        </button>
                      </div>
                    </div>
                  </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      )}

      {/* Password Change Modal */}
      {isPasswordModalOpen && selectedUser && (
        <div className="fixed inset-0 bg-slate-500 bg-opacity-75 dark:bg-slate-900 dark:bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 w-full max-w-md">
            <h2 className="text-lg font-medium text-slate-900 dark:text-white mb-4">
              Change Password: {selectedUser.username}
            </h2>
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-4">
              Server: {selectedUser.server_name} ({selectedUser.server_type})
            </div>

            {passwordError && (
              <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-sm text-red-600 dark:text-red-400">
                {passwordError}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  New Password
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-1 block w-full border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-700 dark:text-white"
                  placeholder="Enter new password (min 8 characters)"
                  disabled={passwordLoading}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Confirm Password
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="mt-1 block w-full border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-700 dark:text-white"
                  placeholder="Confirm new password"
                  disabled={passwordLoading}
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => {
                  setIsPasswordModalOpen(false)
                  setSelectedUser(null)
                }}
                className="btn btn-secondary"
                disabled={passwordLoading}
              >
                Cancel
              </button>
              <button
                onClick={handlePasswordChange}
                className="btn btn-primary"
                disabled={passwordLoading || !newPassword || !confirmPassword}
              >
                {passwordLoading ? 'Changing...' : 'Change Password'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Library Access Modal */}
      {isLibraryModalOpen && selectedUser && (
        <div className="fixed inset-0 bg-slate-500 bg-opacity-75 dark:bg-slate-900 dark:bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-medium text-slate-900 dark:text-white mb-4">
              Manage Library Access: {selectedUser.username}
            </h2>
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-4">
              Server: {selectedUser.server_name} ({selectedUser.server_type})
            </div>

            {selectedUser.server_type?.toLowerCase() === 'plex' ? (
              <div className="space-y-2">
                <div className="text-center text-slate-500 dark:text-slate-400 py-8">
                  <FolderIcon className="h-12 w-12 mx-auto mb-2 text-slate-400" />
                  <p>Library access management is not available for Plex servers</p>
                  <p className="text-sm mt-2">Plex library sharing must be managed through the Plex web interface</p>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {librariesLoading ? (
                  <div className="text-center py-8">
                    <div className="text-slate-600 dark:text-slate-400">Loading libraries...</div>
                  </div>
                ) : libraries.length === 0 ? (
                  <div className="text-center text-slate-500 dark:text-slate-400 py-8">
                    <FolderIcon className="h-12 w-12 mx-auto mb-2 text-slate-400" />
                    <p>No libraries found on this server</p>
                  </div>
                ) : (
                  <>
                    <div className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                      Select which libraries this user can access:
                    </div>
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {libraries.map((library) => (
                        <label
                          key={library.id}
                          className="flex items-center p-3 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded"
                            checked={selectedLibraries.includes(library.id)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedLibraries([...selectedLibraries, library.id])
                              } else {
                                setSelectedLibraries(selectedLibraries.filter(id => id !== library.id))
                              }
                            }}
                          />
                          <div className="ml-3 flex-1">
                            <div className="text-sm font-medium text-slate-900 dark:text-white">
                              {library.name}
                            </div>
                            {library.type && (
                              <div className="text-xs text-slate-500 dark:text-slate-400">
                                Type: {library.type}
                              </div>
                            )}
                          </div>
                        </label>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => {
                  setIsLibraryModalOpen(false)
                  setSelectedUser(null)
                }}
                className="btn btn-secondary"
                disabled={librariesSaving}
              >
                Cancel
              </button>
              {selectedUser.server_type?.toLowerCase() !== 'plex' && libraries.length > 0 && (
                <button
                  onClick={handleLibraryAccessSave}
                  className="btn btn-primary"
                  disabled={librariesSaving || librariesLoading}
                >
                  {librariesSaving ? 'Saving...' : 'Save Changes'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}