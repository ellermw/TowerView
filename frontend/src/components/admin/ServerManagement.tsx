import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { PlusIcon, ServerIcon, ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import api from '../../services/api'
import ServerStatsRealTime from './ServerStatsRealTime'

export default function ServerManagement() {
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingServer, setEditingServer] = useState<any>(null)
  const [selectedServerType, setSelectedServerType] = useState('')
  const [editSelectedServerType, setEditSelectedServerType] = useState('')
  const [expandedServers, setExpandedServers] = useState<Set<number>>(new Set())
  const queryClient = useQueryClient()

  const { data: servers = [], isLoading } = useQuery('servers', () =>
    api.get('/admin/servers').then(res => res.data)
  )


  // Query for active sessions (same as Sessions/Dashboard pages)
  const { data: allSessions = [], isLoading: sessionsLoading } = useQuery(
    'admin-sessions-servers-page',
    () => api.get('/admin/sessions').then(res => res.data),
    {
      refetchInterval: 2000, // Refetch every 2 seconds
      enabled: servers.length > 0,
      staleTime: 0, // Always consider data stale
      cacheTime: 0  // Don't cache
    }
  )

  // Calculate session counts from the same data source as Sessions/Dashboard
  const sessionCounts = allSessions.reduce((counts: any, session: any) => {
    const serverId = session.server_id
    if (serverId) {
      counts[serverId] = (counts[serverId] || 0) + 1
    }
    return counts
  }, {})

  // Debug logging
  console.log('SERVERS PAGE - Total sessions:', allSessions.length)
  console.log('SERVERS PAGE - Session counts by server:', sessionCounts)
  console.log('SERVERS PAGE - Sample sessions:', allSessions.slice(0, 3))
  console.log('SERVERS PAGE - Server list:', servers.map((s: any) => ({ id: s.id, name: s.name, type: s.type })))

  // Additional debug for each server
  servers.forEach((server: any) => {
    const count = sessionCounts[server.id] || 0
    console.log(`Server "${server.name}" (ID: ${server.id}, Type: ${server.type}): ${count} sessions`)
  })

  const addServerMutation = useMutation(
    (serverData: any) => api.post('/admin/servers', serverData),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('servers')
        setShowAddForm(false)
        setSelectedServerType('')
        toast.success('Server added successfully')
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to add server')
      }
    }
  )

  const updateServerMutation = useMutation(
    ({ id, ...serverData }: any) => api.put(`/admin/servers/${id}`, serverData),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('servers')
        setEditingServer(null)
        setEditSelectedServerType('')
        toast.success('Server updated successfully')
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to update server')
      }
    }
  )

  const deleteServerMutation = useMutation(
    (serverId: number) => api.delete(`/admin/servers/${serverId}`),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('servers')
        toast.success('Server deleted successfully')
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to delete server')
      }
    }
  )

  if (isLoading) {
    return <div className="flex justify-center py-8">Loading servers...</div>
  }

  return (
    <div className="px-4 py-6 sm:px-6">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Server Management
          </h1>
          <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
            Manage your Plex, Emby, and Jellyfin servers
          </p>
        </div>
        <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
          <button
            type="button"
            onClick={() => setShowAddForm(true)}
            className="btn-primary"
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Add Server
          </button>
        </div>
      </div>

      <div className="mt-8 flow-root">
        <div className="-mx-4 -my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
          <div className="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
            <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
              <table className="min-w-full divide-y divide-slate-300 dark:divide-slate-700">
                <thead className="bg-slate-50 dark:bg-slate-800">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Server
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Active Streams
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-slate-900 divide-y divide-slate-200 dark:divide-slate-700">
                  {servers.map((server: any) => {
                    const isExpanded = expandedServers.has(server.id)
                    return (
                    <>
                    <tr key={server.id} className="hover:bg-slate-50 dark:hover:bg-slate-800">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <button
                            onClick={() => {
                              const newExpanded = new Set(expandedServers)
                              if (isExpanded) {
                                newExpanded.delete(server.id)
                              } else {
                                newExpanded.add(server.id)
                              }
                              setExpandedServers(newExpanded)
                            }}
                            className="mr-2 p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded"
                          >
                            {isExpanded ? (
                              <ChevronDownIcon className="h-4 w-4 text-slate-500" />
                            ) : (
                              <ChevronRightIcon className="h-4 w-4 text-slate-500" />
                            )}
                          </button>
                          <ServerIcon className="h-5 w-5 text-gray-400 mr-3" />
                          <div>
                            <div className="text-sm font-medium text-gray-900 dark:text-white">
                              {server.name}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">
                              {server.base_url}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                        <span className="capitalize">{server.type}</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          server.enabled
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                        }`}>
                          {server.enabled ? 'Online' : 'Offline'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        <div className="flex items-center">
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                            (sessionCounts[server.id] || 0) > 0
                              ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                              : 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
                          }`}>
                            {sessionCounts[server.id] || 0} streams
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => setEditingServer(server)}
                          className="text-primary-600 hover:text-primary-900 dark:text-primary-400 dark:hover:text-primary-300 mr-4"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            if (confirm('Are you sure you want to delete this server?')) {
                              deleteServerMutation.mutate(server.id)
                            }
                          }}
                          className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${server.id}-stats`}>
                        <td colSpan={5} className="px-6 py-0 bg-slate-50 dark:bg-slate-900">
                          <div className="border-l-4 border-primary-500 ml-8">
                            <ServerStatsRealTime serverId={server.id} />
                          </div>
                        </td>
                      </tr>
                    )}
                    </>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {showAddForm && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white dark:bg-dark-800">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">
              Add New Server
            </h3>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const formData = new FormData(e.currentTarget)
                const serverType = formData.get('type')
                const credentials: any = {}

                if (serverType === 'plex') {
                  // For Plex, use username/password for Plex.tv authentication
                  credentials.username = formData.get('username')
                  credentials.password = formData.get('password')
                  const token = formData.get('token')
                  if (token) credentials.token = token
                } else {
                  // For Emby/Jellyfin, use API key/token
                  credentials.token = formData.get('token')
                  credentials.api_key = formData.get('api_key')
                }

                const data = {
                  name: formData.get('name'),
                  type: serverType,
                  base_url: formData.get('base_url'),
                  credentials
                }
                addServerMutation.mutate(data)
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Server Name
                </label>
                <input
                  type="text"
                  name="name"
                  required
                  className="input mt-1"
                  placeholder="My Media Server"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Server Type
                </label>
                <select
                  name="type"
                  required
                  className="input mt-1"
                  onChange={(e) => setSelectedServerType(e.target.value)}
                >
                  <option value="">Select Type</option>
                  <option value="plex">Plex</option>
                  <option value="emby">Emby</option>
                  <option value="jellyfin">Jellyfin</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Server URL
                </label>
                <input
                  type="url"
                  name="base_url"
                  required
                  className="input mt-1"
                  placeholder="http://localhost:32400"
                />
              </div>

              {selectedServerType === 'plex' ? (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      Plex.tv Username
                    </label>
                    <input
                      type="text"
                      name="username"
                      required
                      className="input mt-1"
                      placeholder="Your Plex.tv username"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      Plex.tv Password
                    </label>
                    <input
                      type="password"
                      name="password"
                      required
                      className="input mt-1"
                      placeholder="Your Plex.tv password"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                      API Token (optional)
                    </label>
                    <input
                      type="text"
                      name="token"
                      className="input mt-1"
                      placeholder="Leave blank to use Plex.tv authentication"
                    />
                  </div>
                </>
              ) : selectedServerType ? (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    API Token
                  </label>
                  <input
                    type="text"
                    name="token"
                    required
                    className="input mt-1"
                    placeholder="Your server API token"
                  />
                </div>
              ) : null}

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddForm(false)
                    setSelectedServerType('')
                  }}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addServerMutation.isLoading}
                  className="btn-primary"
                >
                  {addServerMutation.isLoading ? 'Adding...' : 'Add Server'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editingServer && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white dark:bg-slate-800">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">
              Edit Server
            </h3>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const formData = new FormData(e.currentTarget)
                const serverType = formData.get('type')
                let credentials: any = undefined

                if (serverType === 'plex') {
                  // For Plex, use username/password if provided
                  const username = formData.get('username')
                  const password = formData.get('password')
                  const token = formData.get('token')
                  if (username && password) {
                    credentials = { username, password }
                    if (token) credentials.token = token
                  } else if (token) {
                    credentials = { token }
                  }
                } else {
                  // For Emby/Jellyfin, use API key/token if provided
                  const token = formData.get('token')
                  if (token) {
                    credentials = { token, api_key: token }
                  }
                }

                const data = {
                  id: editingServer.id,
                  name: formData.get('name'),
                  type: serverType,
                  base_url: formData.get('base_url'),
                  enabled: formData.get('enabled') === 'on',
                  credentials
                }
                updateServerMutation.mutate(data)
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Server Name
                </label>
                <input
                  type="text"
                  name="name"
                  defaultValue={editingServer.name}
                  required
                  className="input mt-1"
                  placeholder="My Media Server"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Server Type
                </label>
                <select
                  name="type"
                  defaultValue={editingServer.type}
                  required
                  className="input mt-1"
                  onChange={(e) => setEditSelectedServerType(e.target.value)}
                >
                  <option value="">Select Type</option>
                  <option value="plex">Plex</option>
                  <option value="emby">Emby</option>
                  <option value="jellyfin">Jellyfin</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Server URL
                </label>
                <input
                  type="url"
                  name="base_url"
                  defaultValue={editingServer.base_url}
                  required
                  className="input mt-1"
                  placeholder="http://localhost:32400"
                />
              </div>

              {(editSelectedServerType || editingServer.type) === 'plex' ? (
                <>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      Plex.tv Username (leave blank to keep current)
                    </label>
                    <input
                      type="text"
                      name="username"
                      className="input mt-1"
                      placeholder="Your Plex.tv username"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      Plex.tv Password (leave blank to keep current)
                    </label>
                    <input
                      type="password"
                      name="password"
                      className="input mt-1"
                      placeholder="Your Plex.tv password"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      API Token (optional, leave blank to keep current)
                    </label>
                    <input
                      type="text"
                      name="token"
                      className="input mt-1"
                      placeholder="Leave blank to use Plex.tv authentication"
                    />
                  </div>
                </>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                    API Token (leave blank to keep current)
                  </label>
                  <input
                    type="text"
                    name="token"
                    className="input mt-1"
                    placeholder="Your server API token"
                  />
                </div>
              )}

              <div>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    name="enabled"
                    defaultChecked={editingServer.enabled}
                    className="rounded border-slate-300 text-primary-600 shadow-sm focus:border-primary-300 focus:ring focus:ring-primary-200 focus:ring-opacity-50"
                  />
                  <span className="ml-2 text-sm text-slate-700 dark:text-slate-300">Server Enabled</span>
                </label>
              </div>

              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => {
                    setEditingServer(null)
                    setEditSelectedServerType('')
                  }}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateServerMutation.isLoading}
                  className="btn-primary"
                >
                  {updateServerMutation.isLoading ? 'Updating...' : 'Update Server'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}