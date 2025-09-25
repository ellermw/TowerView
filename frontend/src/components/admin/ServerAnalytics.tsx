import { useQuery } from 'react-query'
import {
  ServerIcon,
  ArrowPathIcon,
  CpuChipIcon,
  CircleStackIcon,
  CubeIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline'
import api from '../../services/api'
import ServerStats from './ServerStats'

interface Server {
  id: number
  name: string
  type: string
  base_url: string
  enabled: boolean
}

export default function ServerAnalytics() {
  const { data: servers = [], isLoading, refetch } = useQuery<Server[]>(
    'servers-analytics',
    () => api.get('/admin/servers').then(res => res.data),
    {
      refetchInterval: 10000 // Refresh server list every 10 seconds
    }
  )

  const { data: sessions = [] } = useQuery(
    'sessions-analytics',
    () => api.get('/admin/sessions').then(res => res.data),
    {
      refetchInterval: 2000 // Refresh every 2 seconds
    }
  )

  // Calculate active sessions per server
  const sessionCounts = sessions.reduce((counts: any, session: any) => {
    const serverId = session.server_id
    if (serverId) {
      counts[serverId] = (counts[serverId] || 0) + 1
    }
    return counts
  }, {})

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-12">
        <ArrowPathIcon className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    )
  }

  if (servers.length === 0) {
    return (
      <div className="text-center py-12">
        <ServerIcon className="h-12 w-12 text-slate-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-slate-900 dark:text-white">No servers configured</h3>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          Add servers in the Server Management section to see analytics
        </p>
      </div>
    )
  }

  return (
    <div className="px-4 py-6 sm:px-6">
      {/* Header */}
      <div className="mb-6 flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Server Analytics</h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Real-time resource usage for all media servers
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="btn btn-secondary"
        >
          <ArrowPathIcon className="h-4 w-4 mr-2" />
          Refresh All
        </button>
      </div>

      {/* Server Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {servers.map(server => (
          <div
            key={server.id}
            className="card hover:shadow-lg transition-shadow"
          >
            {/* Card Header */}
            <div className="card-body border-b border-slate-200 dark:border-slate-700">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <ServerIcon className="h-8 w-8 text-primary-500" />
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                      {server.name}
                    </h3>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      {server.type.charAt(0).toUpperCase() + server.type.slice(1)}
                    </p>
                  </div>
                </div>
                <div className="flex flex-col items-end space-y-1">
                  <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                    server.enabled
                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                      : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                  }`}>
                    {server.enabled ? 'Online' : 'Offline'}
                  </span>
                  {sessionCounts[server.id] > 0 && (
                    <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                      {sessionCounts[server.id]} active
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Server Stats */}
            <ServerStats serverId={server.id} serverName={server.name} />
          </div>
        ))}
      </div>

      {/* Info Box */}
      <div className="mt-8 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <ExclamationCircleIcon className="h-5 w-5 text-blue-400" />
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800 dark:text-blue-200">
              Container Mapping Required
            </h3>
            <p className="mt-1 text-sm text-blue-700 dark:text-blue-300">
              To see resource usage, map each server to its Docker container in Settings → Portainer.
              GPU metrics require intel_gpu_top installed in the container.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}