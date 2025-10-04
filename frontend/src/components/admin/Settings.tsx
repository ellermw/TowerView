import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import toast from 'react-hot-toast'
import {
  CogIcon,
  CloudIcon,
  ServerIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  LinkIcon,
  TrashIcon,
  CpuChipIcon,
  ExclamationTriangleIcon,
  CubeIcon,
  WifiIcon,
  ClockIcon
} from '@heroicons/react/24/outline'
import api from '../../services/api'
import SyncSettings from './SyncSettings'

interface DockerContainer {
  id: string
  name: string
  display_name: string
}

interface Server {
  id: number
  name: string
  type: string
  base_url: string
}

interface PortainerContainer {
  id: string
  name: string
  image: string
  state: string
  status: string
}

interface PortainerIntegration {
  connected: boolean
  enabled?: boolean
  url?: string
  endpoint_id?: number
  container_mappings?: Record<string, { container_id: string; container_name: string }>
  containers_count?: number
  updated_at?: string
}

interface TranscodeSettings {
  auto_terminate_4k_enabled: boolean
  auto_terminate_message: string
  selected_server_ids: number[]
}

export default function Settings() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('general')
  const [apiToken, setApiToken] = useState('')
  const [showTokenInput, setShowTokenInput] = useState(false)
  const [selectedMappings, setSelectedMappings] = useState<Record<number, string>>({})
  const [selectedContainers, setSelectedContainers] = useState<Record<number, string>>({})
  const [containersList, setContainersList] = useState<Record<string, DockerContainer[]>>({})

  // Portainer state
  const [portainerUrl, setPortainerUrl] = useState('')
  const [portainerUsername, setPortainerUsername] = useState('')
  const [portainerPassword, setPortainerPassword] = useState('')
  const [showPortainerAuth, setShowPortainerAuth] = useState(false)
  const [portainerContainerMappings, setPortainerContainerMappings] = useState<Record<number, string>>({})

  // Site settings state
  const [siteName, setSiteName] = useState('The Tower - View')

  // Transcode settings state
  const [transcodeAutoTerminateEnabled, setTranscodeAutoTerminateEnabled] = useState(false)
  const [transcodeTerminationMessage, setTranscodeTerminationMessage] = useState(
    '4K transcoding is not allowed. Please use a client that supports direct play or choose a lower quality version.'
  )
  const [selectedTranscodeServers, setSelectedTranscodeServers] = useState<number[]>([])

  // Fetch available servers
  const { data: servers = [], isLoading: isLoadingServers } = useQuery<Server[]>(
    'admin-servers',
    () => api.get('/admin/servers').then(res => res.data)
  )

  // Fetch Portainer integration status
  const { data: portainerStatus, refetch: refetchPortainerStatus } = useQuery<PortainerIntegration>(
    'portainer-status',
    () => api.get('/settings/portainer/status').then(res => res.data),
    {
      refetchInterval: 30000
    }
  )

  // Fetch Portainer containers
  const { data: portainerContainers = [], refetch: refetchPortainerContainers } = useQuery<PortainerContainer[]>(
    'portainer-containers',
    () => api.get('/settings/portainer/containers').then(res => res.data),
    {
      enabled: portainerStatus?.connected ?? false
    }
  )

  // Fetch site settings
  const { data: siteSettings } = useQuery(
    'site-settings',
    () => api.get('/settings/site').then(res => res.data),
    {
      onSuccess: (data) => {
        if (data?.site_name) {
          setSiteName(data.site_name)
        }
      }
    }
  )

  // Fetch transcode settings
  const { data: transcodeSettings } = useQuery<TranscodeSettings>(
    'transcode-settings',
    () => api.get('/settings/transcode/settings').then(res => res.data),
    {
      onSuccess: (data) => {
        setTranscodeAutoTerminateEnabled(data.auto_terminate_4k_enabled)
        setTranscodeTerminationMessage(data.auto_terminate_message)
        setSelectedTranscodeServers(data.selected_server_ids || [])
      }
    }
  )

  // Save site name mutation
  const saveSiteName = useMutation(
    (name: string) => api.post('/settings/site', { site_name: name }),
    {
      onSuccess: () => {
        toast.success('Site name updated successfully')
        queryClient.invalidateQueries('site-settings')
        // Update localStorage for immediate effect
        localStorage.setItem('siteName', siteName)
        // Reload to apply the new name
        setTimeout(() => window.location.reload(), 500)
      },
      onError: () => {
        toast.error('Failed to save site name')
      }
    }
  )

  // Save transcode settings mutation
  const saveTranscodeSettings = useMutation(
    () => {
      return api.put('/settings/transcode/settings', {
        auto_terminate_4k_enabled: transcodeAutoTerminateEnabled,
        auto_terminate_message: transcodeTerminationMessage,
        selected_server_ids: selectedTranscodeServers
      })
    },
    {
      onSuccess: () => {
        toast.success('Transcode settings saved successfully')
        queryClient.invalidateQueries('transcode-settings')
      },
      onError: () => {
        toast.error('Failed to save transcode settings')
      }
    }
  )

  // Portainer mutations
  const authenticatePortainer = useMutation(
    (data: { url: string; username?: string; password?: string; api_token?: string }) =>
      api.post('/settings/portainer/auth', data),
    {
      onSuccess: (res) => {
        toast.success(res.data.message || 'Connected to Portainer successfully')
        queryClient.invalidateQueries('portainer-status')
        queryClient.invalidateQueries('portainer-containers')
        setShowPortainerAuth(false)
        setPortainerUrl('')
        setPortainerUsername('')
        setPortainerPassword('')
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to connect to Portainer')
      }
    }
  )

  const setPortainerContainerMapping = useMutation(
    (data: { server_id: number; container_id: string; container_name: string }) =>
      api.post('/settings/portainer/container-mapping', data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portainer-status')
        toast.success('Container mapping saved')
      },
      onError: () => {
        toast.error('Failed to save container mapping')
      }
    }
  )

  const disconnectPortainer = useMutation(
    () => api.delete('/settings/portainer/disconnect'),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('portainer-status')
        queryClient.invalidateQueries('portainer-containers')
        toast.success('Portainer disconnected successfully')
      },
      onError: () => {
        toast.error('Failed to disconnect Portainer')
      }
    }
  )

  const handlePortainerAuth = () => {
    if (!portainerUrl) {
      toast.error('Please enter Portainer URL')
      return
    }

    if (!portainerUsername || !portainerPassword) {
      toast.error('Please fill in all fields')
      return
    }
    authenticatePortainer.mutate({
      url: portainerUrl,
      username: portainerUsername,
      password: portainerPassword
    })
  }

  const handlePortainerContainerMapping = (serverId: number, containerId: string) => {
    const container = portainerContainers.find(c => c.id === containerId)
    if (container) {
      setPortainerContainerMapping.mutate({
        server_id: serverId,
        container_id: containerId,
        container_name: container.name
      })
    }
  }

  const handleSaveSiteName = () => {
    if (!siteName.trim()) {
      toast.error('Site name cannot be empty')
      return
    }
    saveSiteName.mutate(siteName)
  }

  return (
    <div className="space-y-6">
      {/* Tabs */}
      <div className="flex space-x-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
        <button
          onClick={() => setActiveTab('general')}
          className={`flex-1 flex items-center justify-center space-x-2 px-4 py-2 rounded-md transition-colors ${
            activeTab === 'general'
              ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <CogIcon className="h-5 w-5" />
          <span>General</span>
        </button>
        <button
          onClick={() => setActiveTab('portainer')}
          className={`flex-1 flex items-center justify-center space-x-2 px-4 py-2 rounded-md transition-colors ${
            activeTab === 'portainer'
              ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <CubeIcon className="h-5 w-5" />
          <span>Portainer</span>
        </button>
        <button
          onClick={() => setActiveTab('sync')}
          className={`flex-1 flex items-center justify-center space-x-2 px-4 py-2 rounded-md transition-colors ${
            activeTab === 'sync'
              ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          <ClockIcon className="h-5 w-5" />
          <span>Sync & Cache</span>
        </button>
      </div>

      {/* Portainer Tab Content */}
      {activeTab === 'portainer' && (
        <div className="space-y-6">
          {/* Portainer Connection */}
          <div className="card">
            <div className="card-body">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                  Portainer Integration
                </h2>
                {portainerStatus?.connected && (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                    <CheckCircleIcon className="h-4 w-4 mr-1" />
                    Connected
                  </span>
                )}
              </div>

              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                Connect to your Portainer instance to monitor Docker containers running your media servers.
              </p>

              {portainerStatus?.connected ? (
                <div className="space-y-4">
                  <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-slate-500 dark:text-slate-400">URL</p>
                        <p className="font-medium text-slate-900 dark:text-white">{portainerStatus.url}</p>
                      </div>
                      <div>
                        <p className="text-slate-500 dark:text-slate-400">Containers</p>
                        <p className="font-medium text-slate-900 dark:text-white">
                          {portainerStatus.containers_count || 0} found
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => refetchPortainerContainers()}
                      className="btn btn-secondary"
                    >
                      <ArrowPathIcon className="w-4 h-4 mr-2" />
                      Refresh Containers
                    </button>
                    <button
                      onClick={() => disconnectPortainer.mutate()}
                      className="btn btn-danger"
                    >
                      <TrashIcon className="w-4 h-4 mr-2" />
                      Disconnect
                    </button>
                  </div>
                </div>
              ) : (
                <div>
                  {showPortainerAuth ? (
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                          Portainer URL
                        </label>
                        <input
                          type="text"
                          value={portainerUrl}
                          onChange={(e) => setPortainerUrl(e.target.value)}
                          placeholder="portainer.example.com or https://portainer.example.com"
                          className="input w-full"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                          Username
                        </label>
                        <input
                          type="text"
                          value={portainerUsername}
                          onChange={(e) => setPortainerUsername(e.target.value)}
                          placeholder="admin"
                          className="input w-full"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                          Password
                        </label>
                        <input
                          type="password"
                          value={portainerPassword}
                          onChange={(e) => setPortainerPassword(e.target.value)}
                          placeholder="Enter your password"
                          className="input w-full"
                        />
                      </div>

                      <div className="flex gap-3">
                        <button
                          onClick={handlePortainerAuth}
                          disabled={authenticatePortainer.isLoading}
                          className="btn btn-primary"
                        >
                          {authenticatePortainer.isLoading ? (
                            <>
                              <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
                              Connecting...
                            </>
                          ) : (
                            'Connect'
                          )}
                        </button>
                        <button
                          onClick={() => {
                            setShowPortainerAuth(false)
                            setPortainerUrl('')
                            setPortainerUsername('')
                            setPortainerPassword('')
                          }}
                          className="btn btn-secondary"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => setShowPortainerAuth(true)}
                      className="btn btn-primary"
                    >
                      <LinkIcon className="w-4 h-4 mr-2" />
                      Connect to Portainer
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Container Mappings */}
          {portainerStatus?.connected && portainerContainers.length > 0 && (
            <div className="card">
              <div className="card-body">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                  Container Mappings
                </h3>

                <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                  Map your media servers to their Docker containers to monitor resource usage.
                </p>

                <div className="space-y-4">
                  {servers.map((server) => {
                    const mapping = portainerStatus.container_mappings?.[server.id.toString()]
                    return (
                      <div key={server.id} className="border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center space-x-3">
                            <ServerIcon className="h-5 w-5 text-slate-400" />
                            <div>
                              <p className="font-medium text-slate-900 dark:text-white">
                                {server.name}
                              </p>
                              <p className="text-sm text-slate-600 dark:text-slate-400">
                                {server.type.charAt(0).toUpperCase() + server.type.slice(1)} • {server.base_url}
                              </p>
                            </div>
                          </div>
                        </div>

                        {mapping ? (
                          <div className="flex items-center justify-between bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3">
                            <div className="flex items-center space-x-2">
                              <CpuChipIcon className="h-5 w-5 text-green-600 dark:text-green-400" />
                              <span className="text-sm text-green-900 dark:text-green-100">
                                {mapping.container_name}
                              </span>
                            </div>
                            <button
                              onClick={() => {
                                setPortainerContainerMappings(prev => {
                                  const newMappings = { ...prev }
                                  delete newMappings[server.id]
                                  return newMappings
                                })
                              }}
                              className="text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                            >
                              Remove
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center space-x-2">
                            <select
                              value={portainerContainerMappings[server.id] || ''}
                              onChange={(e) => {
                                const containerId = e.target.value
                                if (containerId) {
                                  handlePortainerContainerMapping(server.id, containerId)
                                }
                              }}
                              className="input flex-1"
                            >
                              <option value="">Select a container...</option>
                              {portainerContainers.map(container => (
                                <option key={container.id} value={container.id}>
                                  {container.name} ({container.state})
                                </option>
                              ))}
                            </select>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* General Tab Content */}
      {activeTab === 'general' && (
        <div className="space-y-6">
          {/* Site Configuration */}
          <div className="card">
            <div className="card-body">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                Site Configuration
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Site Name
                  </label>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                    Customize the name of your application
                  </p>
                  <div className="flex gap-3">
                    <input
                      type="text"
                      value={siteName}
                      onChange={(e) => setSiteName(e.target.value)}
                      placeholder="Enter site name"
                      className="input flex-1"
                    />
                    <button
                      onClick={() => handleSaveSiteName()}
                      className="btn btn-primary"
                    >
                      Save
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 4K Transcode Auto-Termination */}
          <div className="card">
            <div className="card-body">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                4K Transcode Auto-Termination
              </h2>

              <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">
                Automatically terminate streams that are transcoding from 4K to 1080p or lower resolutions after a 5-second grace period.
              </p>

              <div className="space-y-6">
                {/* Enable/Disable Toggle */}
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      Enable Auto-Termination
                    </label>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                      When enabled, 4K transcodes to 1080p or below will be automatically terminated
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setTranscodeAutoTerminateEnabled(!transcodeAutoTerminateEnabled)}
                    className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none ${
                      transcodeAutoTerminateEnabled ? 'bg-blue-600' : 'bg-slate-200 dark:bg-slate-700'
                    }`}
                  >
                    <span
                      className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                        transcodeAutoTerminateEnabled ? 'translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                {/* Server Selection */}
                {transcodeAutoTerminateEnabled && (
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Apply to Servers
                    </label>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                      Select which servers should have 4K transcode auto-termination enabled
                    </p>
                    <div className="space-y-2 max-h-48 overflow-y-auto border border-slate-200 dark:border-slate-700 rounded-lg p-3">
                      {isLoadingServers ? (
                        <p className="text-sm text-slate-500 dark:text-slate-400">Loading servers...</p>
                      ) : servers.length === 0 ? (
                        <p className="text-sm text-slate-500 dark:text-slate-400">No servers configured</p>
                      ) : (
                        servers.map((server) => (
                          <label key={server.id} className="flex items-center space-x-3 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 p-2 rounded">
                            <input
                              type="checkbox"
                              checked={selectedTranscodeServers.includes(server.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedTranscodeServers([...selectedTranscodeServers, server.id])
                                } else {
                                  setSelectedTranscodeServers(selectedTranscodeServers.filter(id => id !== server.id))
                                }
                              }}
                              className="w-4 h-4 text-blue-600 bg-white dark:bg-slate-700 border-slate-300 dark:border-slate-600 rounded focus:ring-blue-500"
                            />
                            <span className="flex-1 text-sm text-slate-900 dark:text-white">
                              {server.name}
                              <span className="text-xs text-slate-500 dark:text-slate-400 ml-2">
                                ({server.type})
                              </span>
                            </span>
                          </label>
                        ))
                      )}
                    </div>
                  </div>
                )}

                {/* Termination Message */}
                {transcodeAutoTerminateEnabled && (
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Termination Message (Plex Only)
                    </label>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                      Message shown to Plex users when their 4K transcode is terminated
                    </p>
                    <textarea
                      value={transcodeTerminationMessage}
                      onChange={(e) => setTranscodeTerminationMessage(e.target.value)}
                      rows={3}
                      className="input w-full"
                      placeholder="Enter the message to display to users..."
                    />
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                      Note: Messages are only sent to Plex users. Jellyfin and Emby sessions are terminated without a message.
                    </p>
                  </div>
                )}

                {/* Save Button */}
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => saveTranscodeSettings.mutate()}
                    disabled={saveTranscodeSettings.isLoading}
                    className="btn btn-primary"
                  >
                    {saveTranscodeSettings.isLoading ? 'Saving...' : 'Save Settings'}
                  </button>
                </div>

                {/* Info Box */}
                {transcodeAutoTerminateEnabled && (
                  <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <ExclamationTriangleIcon className="h-5 w-5 text-blue-400" />
                      </div>
                      <div className="ml-3">
                        <h3 className="text-sm font-medium text-blue-800 dark:text-blue-200">
                          Auto-Termination Active
                        </h3>
                        <div className="mt-2 text-sm text-blue-700 dark:text-blue-300">
                          <p>
                            The system will monitor for 4K transcodes every 2 seconds. Any stream transcoding from 4K to 1080p
                            or lower will be terminated after a 5-second grace period.
                          </p>
                          {selectedTranscodeServers.length > 0 && (
                            <p className="mt-1">
                              Applied to {selectedTranscodeServers.length} server{selectedTranscodeServers.length !== 1 ? 's' : ''}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Metrics Update Settings */}
          <div className="card">
            <div className="card-body">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                Metrics Update Settings
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Default Update Mode
                  </label>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
                    Choose how server metrics are updated across the application
                  </p>

                  <div className="flex space-x-4">
                    <button
                      onClick={() => {
                        localStorage.removeItem('metricsMode') // Clear instead of setting
                        window.location.reload()
                      }}
                      className={`flex-1 p-4 rounded-lg border-2 transition-all ${
                        localStorage.getItem('metricsMode') !== 'websocket'
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                          : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-center mb-2">
                        <ArrowPathIcon className="h-8 w-8 text-blue-500" />
                      </div>
                      <h3 className="font-medium text-slate-900 dark:text-white">Polling Mode</h3>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                        Reliable updates every 2 seconds
                      </p>
                      {localStorage.getItem('metricsMode') !== 'websocket' && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 mt-2">
                          Active
                        </span>
                      )}
                    </button>

                    <button
                      onClick={() => {
                        localStorage.setItem('metricsMode', 'websocket')
                        window.location.reload()
                      }}
                      className={`flex-1 p-4 rounded-lg border-2 transition-all ${
                        localStorage.getItem('metricsMode') === 'websocket'
                          ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                          : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-center mb-2">
                        <WifiIcon className="h-8 w-8 text-purple-500" />
                      </div>
                      <h3 className="font-medium text-slate-900 dark:text-white">WebSocket Mode</h3>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                        Real-time updates (requires configuration)
                      </p>
                      {localStorage.getItem('metricsMode') === 'websocket' && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200 mt-2">
                          Active
                        </span>
                      )}
                    </button>
                  </div>
                </div>

                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                  <div className="flex">
                    <div className="flex-shrink-0">
                      <ExclamationTriangleIcon className="h-5 w-5 text-blue-400" />
                    </div>
                    <div className="ml-3">
                      <h3 className="text-sm font-medium text-blue-800 dark:text-blue-200">
                        Mode Information
                      </h3>
                      <div className="mt-2 text-sm text-blue-700 dark:text-blue-300">
                        <ul className="list-disc list-inside space-y-1">
                          <li><strong>Polling:</strong> Requests metrics every 2 seconds. More reliable, works everywhere.</li>
                          <li><strong>WebSocket:</strong> Real-time streaming updates. Requires proper proxy configuration.</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Other Settings */}
          <div className="card">
            <div className="card-body">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
                Other Settings
              </h2>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Additional settings will be available here in future updates.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Sync & Cache Tab Content */}
      {activeTab === 'sync' && <SyncSettings />}
    </div>
  )
}