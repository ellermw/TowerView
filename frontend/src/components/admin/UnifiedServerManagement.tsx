import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import {
  PlusIcon,
  ServerIcon,
  PlayIcon,
  StopIcon,
  ArrowPathIcon,
  PauseIcon,
  TrashIcon,
  PencilIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import api from '../../services/api'
import ServerStatsRealTime from './ServerStatsRealTime'
import ServerModal from './ServerModal'
import { useWebSocketMetrics } from '../../hooks/useWebSocketMetrics'

interface Server {
  id: number
  name: string
  type: 'plex' | 'emby' | 'jellyfin'
  base_url: string
  enabled: boolean
}

interface ContainerInfo {
  mapped: boolean
  running?: boolean
  paused?: boolean
  state?: string
  container_name?: string
}

const SERVER_TYPE_CONFIG = {
  plex: {
    name: 'Plex',
    color: 'orange',
    icon: '🎬',
    bgGradient: 'from-orange-500 to-amber-500'
  },
  emby: {
    name: 'Emby',
    color: 'green',
    icon: '📺',
    bgGradient: 'from-green-500 to-emerald-500'
  },
  jellyfin: {
    name: 'Jellyfin',
    color: 'purple',
    icon: '🎭',
    bgGradient: 'from-purple-500 to-indigo-500'
  }
}

export default function UnifiedServerManagement() {
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingServer, setEditingServer] = useState<Server | null>(null)
  const [selectedServerType, setSelectedServerType] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const queryClient = useQueryClient()

  // Fetch servers
  const { data: servers = [], isLoading: serversLoading } = useQuery<Server[]>(
    'unified-servers',
    () => api.get('/admin/servers').then(res => res.data),
    {
      refetchInterval: 30000
    }
  )

  // Fetch sessions for active counts
  const { data: sessions = [] } = useQuery(
    'unified-sessions',
    () => api.get('/admin/sessions').then(res => res.data),
    {
      refetchInterval: 5000
    }
  )

  // Get all server IDs for WebSocket metrics
  const serverIds = servers.map(s => s.id)

  // Check if WebSocket mode is enabled
  const getWebSocketEnabled = () => {
    const saved = localStorage.getItem('metricsMode')
    return saved === 'websocket'
  }

  // WebSocket metrics for all servers
  const { metrics: wsMetrics, isConnected } = useWebSocketMetrics({
    serverIds,
    enabled: getWebSocketEnabled() && serverIds.length > 0
  })

  // Group servers by type
  const groupedServers = useMemo(() => {
    const groups: Record<string, Server[]> = {
      plex: [],
      emby: [],
      jellyfin: []
    }

    servers.forEach(server => {
      if (groups[server.type]) {
        groups[server.type].push(server)
      }
    })

    return groups
  }, [servers])

  // Calculate session counts
  const sessionCounts = useMemo(() => {
    return sessions.reduce((counts: any, session: any) => {
      const serverId = session.server_id
      if (serverId) {
        counts[serverId] = (counts[serverId] || 0) + 1
      }
      return counts
    }, {})
  }, [sessions])

  // Container info query for each server
  const { data: containerInfoMap = {} } = useQuery(
    ['container-info', servers],
    async () => {
      const infoMap: Record<number, ContainerInfo> = {}
      await Promise.all(
        servers.map(async (server) => {
          try {
            const res = await api.get(`/settings/portainer/container/${server.id}/info`)
            infoMap[server.id] = res.data
          } catch {
            infoMap[server.id] = { mapped: false }
          }
        })
      )
      return infoMap
    },
    {
      enabled: servers.length > 0,
      refetchInterval: 10000
    }
  )

  // Container action mutation
  const containerActionMutation = useMutation(
    ({ serverId, action }: { serverId: number; action: string }) =>
      api.post(`/settings/portainer/container/${serverId}/action?action=${action}`),
    {
      onSuccess: (_, variables) => {
        toast.success(`Container ${variables.action} successful`)
        queryClient.invalidateQueries('container-info')
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Container action failed')
      }
    }
  )

  // Server mutations (add, edit, delete)
  const addServerMutation = useMutation(
    (serverData: any) => api.post('/admin/servers', serverData),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('unified-servers')
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
        queryClient.invalidateQueries('unified-servers')
        setEditingServer(null)
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
        queryClient.invalidateQueries('unified-servers')
        toast.success('Server deleted successfully')
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to delete server')
      }
    }
  )

  const ServerCard = ({ server }: { server: Server }) => {
    const containerInfo = containerInfoMap[server.id] || { mapped: false }
    const metrics = wsMetrics[server.id]
    const sessionCount = sessionCounts[server.id] || 0
    const typeConfig = SERVER_TYPE_CONFIG[server.type]

    return (
      <div className="card hover:shadow-xl transition-all duration-300 overflow-hidden">
        {/* Card Header with gradient */}
        <div className={`h-2 bg-gradient-to-r ${typeConfig.bgGradient}`} />

        <div className="card-body">
          {/* Server Info */}
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-start space-x-3">
              <div className="text-3xl">{typeConfig.icon}</div>
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  {server.name}
                </h3>
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  {typeConfig.name} Server
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-500 mt-1">
                  {server.base_url}
                </p>
              </div>
            </div>

            {/* Status badges */}
            <div className="flex flex-col items-end space-y-1">
              {server.enabled ? (
                <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                  <CheckCircleIcon className="w-3 h-3 mr-1" />
                  Online
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                  <XCircleIcon className="w-3 h-3 mr-1" />
                  Offline
                </span>
              )}

              {sessionCount > 0 && (
                <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                  {sessionCount} active
                </span>
              )}
            </div>
          </div>

          {/* Container Controls */}
          {containerInfo.mapped && (
            <div className="mb-4 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Container: {containerInfo.container_name}
                </span>
                <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded ${
                  containerInfo.running
                    ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                    : containerInfo.paused
                    ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'
                    : 'bg-gray-100 text-gray-700 dark:bg-gray-900 dark:text-gray-300'
                }`}>
                  {containerInfo.state || 'Unknown'}
                </span>
              </div>

              <div className="flex space-x-2">
                <button
                  onClick={() => containerActionMutation.mutate({ serverId: server.id, action: 'start' })}
                  disabled={containerInfo.running}
                  className="btn btn-sm btn-success flex-1"
                >
                  <PlayIcon className="w-4 h-4" />
                  Start
                </button>
                <button
                  onClick={() => containerActionMutation.mutate({ serverId: server.id, action: 'stop' })}
                  disabled={!containerInfo.running}
                  className="btn btn-sm btn-danger flex-1"
                >
                  <StopIcon className="w-4 h-4" />
                  Stop
                </button>
                <button
                  onClick={() => containerActionMutation.mutate({ serverId: server.id, action: 'restart' })}
                  className="btn btn-sm btn-warning flex-1"
                >
                  <ArrowPathIcon className="w-4 h-4" />
                  Restart
                </button>
              </div>
            </div>
          )}

          {/* Real-time Stats */}
          <div className="border-t border-slate-200 dark:border-slate-700 -mx-6 px-6 pt-4">
            <ServerStatsRealTime serverId={server.id} />
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end space-x-2 mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
            <button
              onClick={() => setEditingServer(server)}
              className="btn btn-sm btn-secondary"
            >
              <PencilIcon className="w-4 h-4 mr-1" />
              Edit
            </button>
            <button
              onClick={() => {
                if (confirm(`Delete ${server.name}?`)) {
                  deleteServerMutation.mutate(server.id)
                }
              }}
              className="btn btn-sm btn-danger"
            >
              <TrashIcon className="w-4 h-4 mr-1" />
              Delete
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (serversLoading) {
    return (
      <div className="flex justify-center items-center py-12">
        <ArrowPathIcon className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    )
  }

  return (
    <div className="px-4 py-6 sm:px-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
              Server Management
            </h1>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              Manage and monitor all your media servers in one place
            </p>
          </div>

          <div className="flex space-x-3">
            {/* View Mode Toggle */}
            <div className="btn-group">
              <button
                onClick={() => setViewMode('grid')}
                className={`btn btn-sm ${viewMode === 'grid' ? 'btn-primary' : 'btn-secondary'}`}
              >
                <ChartBarIcon className="w-4 h-4 mr-1" />
                Grid
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`btn btn-sm ${viewMode === 'list' ? 'btn-primary' : 'btn-secondary'}`}
              >
                <ServerIcon className="w-4 h-4 mr-1" />
                List
              </button>
            </div>

            <button
              onClick={() => setShowAddForm(true)}
              className="btn btn-primary"
            >
              <PlusIcon className="w-5 h-5 mr-2" />
              Add Server
            </button>
          </div>
        </div>

        {/* Connection Status */}
        <div className="mt-4 flex items-center text-sm">
          {getWebSocketEnabled() ? (
            isConnected ? (
              <span className="flex items-center text-green-600 dark:text-green-400">
                <CheckCircleIcon className="w-4 h-4 mr-1" />
                WebSocket connected - Real-time metrics active
              </span>
            ) : (
              <span className="flex items-center text-amber-600 dark:text-amber-400">
                <ExclamationTriangleIcon className="w-4 h-4 mr-1" />
                WebSocket connecting...
              </span>
            )
          ) : (
            <span className="flex items-center text-blue-600 dark:text-blue-400">
              <ArrowPathIcon className="w-4 h-4 mr-1" />
              Polling mode (2s intervals)
            </span>
          )}
        </div>
      </div>

      {/* Server Groups */}
      {servers.length === 0 ? (
        <div className="text-center py-12 card">
          <ServerIcon className="h-12 w-12 text-slate-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-900 dark:text-white">
            No servers configured
          </h3>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            Add your first media server to get started
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(groupedServers).map(([type, typeServers]) => {
            if (typeServers.length === 0) return null

            const typeConfig = SERVER_TYPE_CONFIG[type as keyof typeof SERVER_TYPE_CONFIG]

            return (
              <div key={type}>
                {/* Group Header */}
                <div className="flex items-center mb-4">
                  <div className={`h-1 flex-1 bg-gradient-to-r ${typeConfig.bgGradient} rounded-full mr-4`} />
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center">
                    <span className="text-2xl mr-2">{typeConfig.icon}</span>
                    {typeConfig.name} Servers ({typeServers.length})
                  </h2>
                  <div className={`h-1 flex-1 bg-gradient-to-r ${typeConfig.bgGradient} rounded-full ml-4`} />
                </div>

                {/* Server Cards */}
                {viewMode === 'grid' ? (
                  <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                    {typeServers.map(server => (
                      <ServerCard key={server.id} server={server} />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {typeServers.map(server => (
                      <ServerCard key={server.id} server={server} />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Add Server Modal */}
      {showAddForm && (
        <ServerModal
          mode="add"
          onClose={() => {
            setShowAddForm(false)
            setSelectedServerType('')
          }}
          onSubmit={(data) => addServerMutation.mutate(data)}
          isLoading={addServerMutation.isLoading}
          selectedServerType={selectedServerType}
          setSelectedServerType={setSelectedServerType}
        />
      )}

      {/* Edit Server Modal */}
      {editingServer && (
        <ServerModal
          mode="edit"
          server={editingServer}
          onClose={() => setEditingServer(null)}
          onSubmit={(data) => updateServerMutation.mutate({ id: editingServer.id, ...data })}
          isLoading={updateServerMutation.isLoading}
          selectedServerType={editingServer.type}
          setSelectedServerType={() => {}}
        />
      )}
    </div>
  )
}