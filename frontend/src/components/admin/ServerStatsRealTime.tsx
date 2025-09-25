import { useEffect, useState } from 'react'
import { useQuery } from 'react-query'
import {
  CpuChipIcon,
  CircleStackIcon,
  ArrowPathIcon,
  ExclamationCircleIcon,
  CubeIcon,
  WifiIcon,
  XMarkIcon,
  BoltIcon,
  ClockIcon
} from '@heroicons/react/24/outline'
import api from '../../services/api'
import { useWebSocketMetrics } from '../../hooks/useWebSocketMetrics'

interface ServerStatsRealTimeProps {
  serverId: number
}

interface ServerMetrics {
  cpu_usage: number
  memory_usage: number
  memory_used_gb: number
  memory_total_gb: number
  container: string | null
  timestamp?: string
  gpu?: {
    available: boolean
    gpu_usage?: number
    render_usage?: number
    video_usage?: number
  }
}

export default function ServerStatsRealTime({ serverId }: ServerStatsRealTimeProps) {
  // Get saved preference from localStorage or default to polling
  const getSavedMode = () => {
    const saved = localStorage.getItem('metricsMode')
    // Check if we're accessing through nginx (required for WebSocket)
    const isNginx = window.location.port === '8080' || window.location.port === '80' || window.location.port === ''
    // Only enable WebSocket if saved AND accessing through proper port
    return saved === 'websocket' && isNginx
  }

  const [useWebSocket, setUseWebSocket] = useState(getSavedMode())
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  // WebSocket connection for real-time metrics
  const { metrics: wsMetrics, isConnected, isConnecting, reconnect } = useWebSocketMetrics({
    serverIds: [serverId],
    enabled: useWebSocket,
    onError: (error) => {
      console.error('WebSocket error:', error)
      // Don't automatically fall back to polling - let user control it
    }
  })

  // Fallback polling when WebSocket is not available
  const { data: pollingMetrics, refetch, isFetching } = useQuery<ServerMetrics>(
    ['server-metrics', serverId],
    () => api.get(`/settings/portainer/metrics/${serverId}`).then(res => res.data),
    {
      refetchInterval: useWebSocket ? false : 2000, // Poll every 2 seconds if WebSocket is disabled
      enabled: !useWebSocket && serverId > 0 // Only poll if WebSocket is disabled and we have a valid serverId
    }
  )

  // Use WebSocket metrics if available, otherwise use polling
  const metrics = useWebSocket && wsMetrics[serverId] ? wsMetrics[serverId] : pollingMetrics

  // Update last update timestamp
  useEffect(() => {
    if (metrics) {
      setLastUpdate(new Date())
    }
  }, [metrics])

  // Track if we're switching modes to prevent rapid toggling
  const [isSwitching, setIsSwitching] = useState(false)

  // Check if we're accessing through nginx (required for WebSocket)
  const isNginx = window.location.port === '8080' || window.location.port === '80' || window.location.port === ''

  // Save mode preference when it changes
  const toggleMode = () => {
    if (isSwitching) return // Prevent rapid toggling

    // Don't allow WebSocket mode if not through nginx
    if (!isNginx && !useWebSocket) {
      alert('WebSocket mode requires accessing the app through port 8080. Currently using port ' + (window.location.port || '80'))
      return
    }

    setIsSwitching(true)
    const newMode = !useWebSocket
    setUseWebSocket(newMode)
    localStorage.setItem('metricsMode', newMode ? 'websocket' : 'polling')

    if (newMode) {
      // If switching to WebSocket, try to connect after a small delay
      setTimeout(() => {
        reconnect()
        setIsSwitching(false)
      }, 500)
    } else {
      setIsSwitching(false)
    }
  }

  if (!metrics) {
    return (
      <div className="flex items-center justify-center p-4 text-slate-500 dark:text-slate-400">
        <ArrowPathIcon className="h-5 w-5 animate-spin mr-2" />
        Loading metrics...
      </div>
    )
  }

  // Check if container is mapped
  if (!metrics.container) {
    return (
      <div className="flex items-center p-4 text-slate-500 dark:text-slate-400">
        <ExclamationCircleIcon className="h-5 w-5 mr-2" />
        <span className="text-sm">No container mapped in Settings</span>
      </div>
    )
  }

  const cpuColor = metrics.cpu_usage > 80 ? 'text-red-500' :
                   metrics.cpu_usage > 60 ? 'text-amber-500' : 'text-green-500'

  const memoryColor = metrics.memory_usage > 80 ? 'text-red-500' :
                      metrics.memory_usage > 60 ? 'text-amber-500' : 'text-green-500'

  const gpuColor = (metrics.gpu?.gpu_usage || 0) > 80 ? 'text-red-500' :
                   (metrics.gpu?.gpu_usage || 0) > 60 ? 'text-amber-500' : 'text-green-500'

  const hasGpu = metrics.gpu?.available

  return (
    <div className={`grid ${hasGpu ? 'grid-cols-3' : 'grid-cols-2'} gap-4 p-4`}>
      {/* CPU Usage */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center text-sm text-slate-600 dark:text-slate-400">
            <CpuChipIcon className="h-4 w-4 mr-1" />
            <span>CPU</span>
          </div>
          <span className={`text-sm font-semibold ${cpuColor}`}>
            {metrics.cpu_usage.toFixed(1)}%
          </span>
        </div>
        <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-300 ${
              metrics.cpu_usage > 80 ? 'bg-red-500' :
              metrics.cpu_usage > 60 ? 'bg-amber-500' : 'bg-green-500'
            }`}
            style={{ width: `${Math.min(metrics.cpu_usage, 100)}%` }}
          />
        </div>
      </div>

      {/* Memory Usage */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center text-sm text-slate-600 dark:text-slate-400">
            <CircleStackIcon className="h-4 w-4 mr-1" />
            <span>Memory</span>
          </div>
          <span className={`text-sm font-semibold ${
            metrics.memory_total_gb === 0 ? 'text-slate-600' : memoryColor
          }`}>
            {metrics.memory_total_gb === 0
              ? `${metrics.memory_used_gb.toFixed(1)} GB`
              : `${metrics.memory_usage.toFixed(1)}%`
            }
          </span>
        </div>
        {metrics.memory_total_gb > 0 ? (
          <>
            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${
                  metrics.memory_usage > 80 ? 'bg-red-500' :
                  metrics.memory_usage > 60 ? 'bg-amber-500' : 'bg-green-500'
                }`}
                style={{ width: `${Math.min(metrics.memory_usage, 100)}%` }}
              />
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              {metrics.memory_used_gb.toFixed(1)} / {metrics.memory_total_gb.toFixed(1)} GB
            </div>
          </>
        ) : (
          <div className="text-xs text-slate-500 dark:text-slate-400">
            No limit ({metrics.memory_used_gb.toFixed(1)} GB used)
          </div>
        )}
      </div>

      {/* GPU Usage (if available) */}
      {hasGpu && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center text-sm text-slate-600 dark:text-slate-400">
              <CubeIcon className="h-4 w-4 mr-1" />
              <span>GPU</span>
            </div>
            <span className={`text-sm font-semibold ${gpuColor}`}>
              {metrics.gpu?.gpu_usage?.toFixed(1) || '0.0'}%
            </span>
          </div>
          <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${
                (metrics.gpu?.gpu_usage || 0) > 80 ? 'bg-red-500' :
                (metrics.gpu?.gpu_usage || 0) > 60 ? 'bg-amber-500' : 'bg-green-500'
              }`}
              style={{ width: `${Math.min(metrics.gpu?.gpu_usage || 0, 100)}%` }}
            />
          </div>
          {metrics.gpu?.video_usage !== undefined && (
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Video: {metrics.gpu.video_usage.toFixed(0)}%
            </div>
          )}
        </div>
      )}

      {/* Container Info & Connection Status */}
      <div className={`${hasGpu ? 'col-span-3' : 'col-span-2'} space-y-2`}>
        {/* Mode Toggle */}
        <div className="flex items-center justify-between p-2 bg-slate-50 dark:bg-slate-800 rounded-lg">
          <div className="flex items-center space-x-3">
            <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
              Update Mode:
            </span>
            <button
              onClick={toggleMode}
              className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium transition-all ${
                useWebSocket
                  ? 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300'
                  : 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
              } ${!isNginx && !useWebSocket ? 'opacity-50' : ''}`}
              title={!isNginx ? 'WebSocket requires accessing through port 8080' : 'Toggle update mode'}
            >
              {useWebSocket ? (
                <>
                  <BoltIcon className="w-3 h-3 mr-1" />
                  WebSocket
                </>
              ) : (
                <>
                  <ClockIcon className="w-3 h-3 mr-1" />
                  Polling
                </>
              )}
            </button>
            {/* Connection status */}
            <span className="flex items-center text-xs">
              {useWebSocket ? (
                isConnected ? (
                  <>
                    <WifiIcon className="h-3 w-3 mr-1 text-green-500" />
                    <span className="text-green-600 dark:text-green-400">Connected</span>
                  </>
                ) : isConnecting ? (
                  <>
                    <ArrowPathIcon className="h-3 w-3 mr-1 animate-spin text-amber-500" />
                    <span className="text-amber-600 dark:text-amber-400">Connecting...</span>
                  </>
                ) : (
                  <>
                    <XMarkIcon className="h-3 w-3 mr-1 text-red-500" />
                    <span className="text-red-600 dark:text-red-400">Failed</span>
                  </>
                )
              ) : (
                <>
                  <ArrowPathIcon className={`h-3 w-3 mr-1 ${isFetching ? 'animate-spin' : ''} text-blue-500`} />
                  <span className="text-blue-600 dark:text-blue-400">Active (2s)</span>
                </>
              )}
            </span>
          </div>

          <div className="flex items-center space-x-3">
            {lastUpdate && (
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {lastUpdate.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={() => {
                if (useWebSocket && !isConnected) {
                  reconnect()
                } else if (!useWebSocket) {
                  refetch()
                }
              }}
              className="text-xs text-slate-600 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
            >
              <ArrowPathIcon className="h-3 w-3" />
            </button>
          </div>
        </div>

        {/* Container Info */}
        <div className="pt-2 border-t border-slate-200 dark:border-slate-700">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Container: {metrics.container}
          </span>
        </div>
      </div>
    </div>
  )
}