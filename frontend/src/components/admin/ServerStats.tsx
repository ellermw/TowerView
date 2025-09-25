import { useQuery } from 'react-query'
import {
  CpuChipIcon,
  CircleStackIcon,
  ArrowPathIcon,
  ExclamationCircleIcon,
  CubeIcon
} from '@heroicons/react/24/outline'
import api from '../../services/api'

interface ServerStatsProps {
  serverId: number
  serverName: string
}

interface GPUStats {
  available: boolean
  gpu_usage?: number
  render_usage?: number
  video_usage?: number
  video_enhance?: number
}

interface ServerMetrics {
  cpu_usage: number
  memory_usage: number
  memory_used_gb: number
  memory_total_gb: number
  container: string | null
  timestamp?: string
  gpu?: GPUStats
}

export default function ServerStats({ serverId, serverName }: ServerStatsProps) {
  const { data: metrics, isLoading, isError, refetch, isFetching } = useQuery<ServerMetrics>(
    ['server-metrics', serverId],
    () => api.get(`/settings/portainer/metrics/${serverId}`).then(res => res.data),
    {
      refetchInterval: 2000, // Refresh every 2 seconds
      enabled: true
    }
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-4 text-slate-500 dark:text-slate-400">
        <ArrowPathIcon className="h-5 w-5 animate-spin mr-2" />
        Loading metrics...
      </div>
    )
  }

  if (isError || !metrics) {
    return (
      <div className="flex items-center p-4 text-amber-600 dark:text-amber-400">
        <ExclamationCircleIcon className="h-5 w-5 mr-2" />
        <span className="text-sm">Unable to fetch metrics</span>
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
            className={`h-2 rounded-full transition-all duration-500 ${
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
                className={`h-2 rounded-full transition-all duration-500 ${
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
            No memory limit set (using {metrics.memory_used_gb.toFixed(1)} GB)
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
              className={`h-2 rounded-full transition-all duration-500 ${
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

      {/* Container Info */}
      <div className={`${hasGpu ? 'col-span-3' : 'col-span-2'} pt-2 border-t border-slate-200 dark:border-slate-700`}>
        <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span className="flex items-center">
            Container: {metrics.container}
            {isFetching && (
              <ArrowPathIcon className="h-3 w-3 ml-2 animate-spin text-primary-500" />
            )}
          </span>
          <button
            onClick={() => refetch()}
            className="flex items-center hover:text-slate-700 dark:hover:text-slate-300"
          >
            <ArrowPathIcon className="h-3 w-3 mr-1" />
            Refresh
          </button>
        </div>
      </div>
    </div>
  )
}