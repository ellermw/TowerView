import React, { useMemo } from 'react'
import { useQuery, useMutation } from 'react-query'
import toast from 'react-hot-toast'
import {
  ServerIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  UsersIcon,
  DevicePhoneMobileIcon,
  SignalIcon,
  FilmIcon,
  TvIcon,
  FolderIcon,
  ChartBarIcon,
  XMarkIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ArrowDownTrayIcon,
  CpuChipIcon,
  ComputerDesktopIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline'
import { Disclosure, Transition, Dialog } from '@headlessui/react'
import api from '../../services/api'
import { usePermissions } from '../../hooks/usePermissions'
import { useAuthStore } from '../../store/authStore'

interface LiveSession {
  session_id: string
  media_id?: string
  media_type?: string
  state: string
  progress_ms: number
  duration_ms: number
  progress_seconds: number
  duration_seconds: number
  progress_percent: number
  server_name?: string
  server_id?: number
  server_type?: string

  // Media details
  title?: string
  full_title?: string
  grandparent_title?: string
  parent_title?: string
  year?: string
  summary?: string
  content_rating?: string
  library_section?: string

  // User info
  user_id?: string
  username?: string
  user_thumb?: string

  // Player info
  device?: string
  platform?: string
  product?: string
  version?: string
  address?: string
  location?: string

  // Streaming details
  video_decision?: string
  audio_decision?: string
  original_resolution?: string
  stream_resolution?: string
  original_bitrate?: string
  stream_bitrate?: string
  session_bandwidth?: string
  session_location?: string
  video_codec?: string
  audio_codec?: string
  original_audio_codec?: string
  audio_channels?: string
  original_audio_channels?: string
  container?: string
  video_profile?: string
  quality_profile?: string
  is_4k?: boolean
  is_hdr?: boolean
  is_dolby_vision?: boolean

  // Transcode details
  transcode_hw_requested?: boolean
  transcode_hw_decode?: boolean
  transcode_hw_encode?: boolean
  transcode_hw_decode_title?: string
  transcode_hw_encode_title?: string
  transcode_hw_full_pipeline?: boolean
  transcode_throttled?: boolean
  transcode_speed?: number
}

interface AnalyticsFilters {
  server_id?: number
  days_back: number
  start_date?: string
  end_date?: string
}

interface TopUser {
  username: string
  provider_user_id?: string
  server_name?: string
  total_plays: number
  total_watch_time_minutes: number
  completion_rate: number
}

interface TopMedia {
  title: string
  media_type: string
  provider_media_id?: string
  server_name?: string
  total_plays: number
  unique_users: number
  total_watch_time_minutes: number
  grandparent_title?: string
  parent_title?: string
  year?: string
}

interface TopLibrary {
  library_name: string
  server_name?: string
  total_plays: number
  unique_users: number
  total_watch_time_minutes: number
  media_types: string[]
}

interface TopDevice {
  device_name: string
  platform?: string
  product?: string
  total_sessions: number
  unique_users: number
  total_watch_time_minutes: number
  transcode_percentage: number
}

interface DashboardAnalytics {
  filters: AnalyticsFilters
  top_users: TopUser[]
  top_movies: TopMedia[]
  top_tv_shows: TopMedia[]
  top_libraries: TopLibrary[]
  top_devices: TopDevice[]
  total_sessions: number
  total_users: number
  total_watch_time_hours: number
  completion_rate: number
  transcode_rate: number
}

interface BandwidthDataPoint {
  timestamp: string | number  // Can be ISO string from server or number from client
  totalBandwidth: number | undefined
  total_bandwidth?: number  // Server uses snake_case
  serverBandwidths: Record<string, number> | undefined
  server_bandwidths?: Record<string, number>  // Server uses snake_case
}

interface GPUStatus {
  total_hw_transcodes: number
  total_sw_transcodes: number
  total_transcodes: number
  hw_percentage: number
  servers: Array<{
    server_id: number
    server_name: string
    server_type: string
    hw_transcodes: number
    sw_transcodes: number
    hw_sessions: Array<{
      session_id: string
      username: string
      title: string
      decode: string
      encode: string
      speed?: number
      throttled: boolean
    }>
    sw_sessions: Array<{
      session_id: string
      username: string
      title: string
      speed?: number
      throttled: boolean
    }>
  }>
}

export default function AdminHome() {
  const { user: currentUser } = useAuthStore()
  const { hasPermission, isAdmin } = usePermissions()

  // Bandwidth tracking state for the graph
  const [bandwidthHistory, setBandwidthHistory] = React.useState<BandwidthDataPoint[]>([])

  // Analytics filter state
  const [analyticsFilters, setAnalyticsFilters] = React.useState({
    server_id: undefined as number | undefined,
    days_back: 7
  })

  // Fetch bandwidth history from server (90 seconds of cached data at 5-second intervals)
  const { data: serverBandwidthHistory } = useQuery(
    'bandwidth-history',
    () => api.get('/admin/sessions/bandwidth-history').then(res => res.data),
    {
      refetchInterval: 5000, // Refetch every 5 seconds to match server collection interval
      refetchOnWindowFocus: false,
      onSuccess: (data) => {
        // Convert server format to client format
        const history = data.history?.map((point: any) => ({
          timestamp: typeof point.timestamp === 'string' ? new Date(point.timestamp).getTime() : point.timestamp,
          totalBandwidth: point.total_bandwidth || 0,
          serverBandwidths: point.server_bandwidths || {}
        })) || []

        if (history.length > 0) {
          setBandwidthHistory(history)
        }
      }
    }
  )

  // Get active sessions with 1-second refresh for live bandwidth updates
  const { data: sessions = [], isLoading: sessionsLoading, refetch: refetchSessions, error: sessionsError } = useQuery<LiveSession[]>(
    'admin-sessions',
    () => api.get('/admin/sessions').then(res => res.data),
    {
      refetchInterval: 2000, // 2-second refresh for live updates
      refetchOnWindowFocus: false,
      onError: (_error) => {
        // Error handling - silenced in production
      },
      retry: 1
    }
  )

  // Get list of servers for filter dropdown
  const { data: servers = [] } = useQuery(
    'admin-servers',
    () => api.get('/admin/servers').then(res => res.data),
    {
      refetchOnWindowFocus: false,
    }
  )

  // Get analytics data with filters
  const { data: analytics, isLoading: analyticsLoading } = useQuery<DashboardAnalytics>(
    ['dashboard-analytics', analyticsFilters],
    () => api.post('/admin/analytics', analyticsFilters).then(res => res.data),
    {
      refetchInterval: 5000, // Refresh every 5 seconds
      refetchOnWindowFocus: false,
      staleTime: 0, // Always consider data stale to ensure fresh fetch on filter change
      cacheTime: 0, // Don't cache analytics data
      onError: (_error) => {
        // Error handling - silenced in production
      },
      retry: 1
    }
  )

  // Get GPU status (optional - don't fail if endpoint doesn't exist)
  const { data: gpuStatus } = useQuery<GPUStatus>(
    'gpu-status',
    () => api.get('/admin/gpu-status').then(res => res.data).catch(() => null),
    {
      refetchInterval: 5000, // Refresh every 5 seconds
      refetchOnWindowFocus: false,
      retry: false, // Don't retry if it fails
      enabled: false, // Disable for now until backend is updated
    }
  )

  // State for Plex termination message modal
  const [plexTerminateModal, setPlexTerminateModal] = React.useState<{
    open: boolean
    serverId?: number
    sessionId?: string
    serverType?: string
  }>({ open: false })
  const [plexTerminateMessage, setPlexTerminateMessage] = React.useState('')

  // Get default Plex termination message from settings
  const defaultPlexMessage = localStorage.getItem('plexTerminationMessage') || 'Your stream has been terminated by an administrator'

  // Terminate session mutation
  const terminateSessionMutation = useMutation(
    ({ serverId, sessionId, message }: { serverId: number, sessionId: string, message?: string }) => {
      const data = message ? { message } : undefined
      return api.post(`/admin/servers/${serverId}/sessions/${sessionId}/terminate`, data)
    },
    {
      retry: false, // Don't retry on failure (authorization errors won't be fixed by retrying)
      onSuccess: () => {
        toast.success('Session terminated successfully')
        refetchSessions()
        setPlexTerminateModal({ open: false })
        setPlexTerminateMessage('')
      },
      onError: (error: any) => {
        const errorMessage = error.response?.data?.detail || 'Failed to terminate session'
        toast.error(errorMessage)
      }
    }
  )

  // Handle termination click
  const handleTerminateClick = (serverId: number, sessionId: string, serverType?: string) => {
    if (serverType === 'plex') {
      // Show modal for Plex servers
      setPlexTerminateModal({
        open: true,
        serverId,
        sessionId,
        serverType
      })
      setPlexTerminateMessage(defaultPlexMessage)
    } else {
      // Direct termination for non-Plex servers
      terminateSessionMutation.mutate({ serverId, sessionId })
    }
  }

  // Store sessions in a ref to avoid re-running effect on every update
  const sessionsRef = React.useRef(sessions || [])
  React.useEffect(() => {
    sessionsRef.current = sessions || []
  }, [sessions])

  // Client-side bandwidth tracking removed - now using server-side cache
  // Server tracks bandwidth every 5 seconds and keeps 90 seconds of history (18 data points)

  // Generate server colors
  const getServerColors = () => {
    const colors = [
      '#3B82F6', // blue
      '#EF4444', // red
      '#10B981', // green
      '#F59E0B', // yellow
      '#8B5CF6', // purple
      '#F97316', // orange
      '#06B6D4', // cyan
      '#EC4899', // pink
      '#6B7280', // gray
      '#84CC16', // lime
      '#F472B6', // pink-400
      '#14B8A6', // teal
    ]

    const serverNames = new Set<string>()
    bandwidthHistory.forEach(point => {
      const servers = point.serverBandwidths || point.server_bandwidths || {}
      Object.keys(servers).forEach(server => serverNames.add(server))
    })

    // Debug: Log server names found
    if (serverNames.size > 0) {
      console.log('Servers found in bandwidth data:', Array.from(serverNames))
      console.log('Latest bandwidth data:', bandwidthHistory[bandwidthHistory.length - 1]?.serverBandwidths)
    }

    const serverColorMap: Record<string, string> = {}
    Array.from(serverNames).forEach((server, index) => {
      // Never assign white (#FFFFFF) to servers - it's reserved for Total
      serverColorMap[server] = colors[index % colors.length]
    })

    return serverColorMap
  }

  const serverColors = getServerColors()

  // Get server type color for display
  const getServerTypeColor = (serverType: string) => {
    switch (serverType.toLowerCase()) {
      case 'plex':
        return 'text-orange-600 dark:text-orange-400' // Plex = Orange
      case 'emby':
        return 'text-green-600 dark:text-green-400' // Emby = Green
      case 'jellyfin':
        return 'text-blue-600 dark:text-blue-400' // Jellyfin = Blue
      default:
        return 'text-slate-600 dark:text-slate-400' // Unknown = Gray
    }
  }

  // Get server info including type for display
  const getServerInfo = (serverName: string) => {
    // Try to find the server by name
    const server = servers.find((s: any) => s.name === serverName)
    if (server) {
      return {
        name: server.name,
        type: server.type,
        displayName: `${server.name} (${server.type.charAt(0).toUpperCase() + server.type.slice(1)})`,
        color: getServerTypeColor(server.type)
      }
    }
    // Fallback if server not found - try to guess from name
    const name = serverName.toLowerCase()
    let type = 'unknown'
    if (name.includes('plex') || name.includes('tower') || name.includes('mike')) {
      type = 'plex'
    } else if (name.includes('emby')) {
      type = 'emby'
    } else if (name.includes('jellyfin')) {
      type = 'jellyfin'
    }
    return {
      name: serverName,
      type: type,
      displayName: serverName,
      color: getServerTypeColor(type)
    }
  }

  const getServerTypeIcon = (serverType?: string) => {
    switch (serverType?.toLowerCase()) {
      case 'plex':
        return (
          <img
            src="/plex.png"
            alt="Plex"
            className="h-6 w-6 inline-block"
            style={{ backgroundColor: 'transparent' }}
          />
        )
      case 'emby':
        return (
          <img
            src="/emby.png"
            alt="Emby"
            className="h-6 w-6 inline-block"
            style={{ backgroundColor: 'transparent' }}
          />
        )
      case 'jellyfin':
        return (
          <img
            src="/jellyfin.png"
            alt="Jellyfin"
            className="h-6 w-6 inline-block"
            style={{ backgroundColor: 'transparent' }}
          />
        )
      default:
        return <span className="text-lg">⚪</span>
    }
  }

  const getServerTypeName = (serverType?: string) => {
    switch (serverType?.toLowerCase()) {
      case 'plex':
        return 'Plex'
      case 'emby':
        return 'Emby'
      case 'jellyfin':
        return 'Jellyfin'
      default:
        return 'Unknown'
    }
  }

  // Group sessions by server type, then by server name
  const groupedSessions = useMemo(() => {
    const serverTypeOrder = ['plex', 'emby', 'jellyfin']

    // Ensure sessions is an array
    const validSessions = Array.isArray(sessions) ? sessions : []

    const grouped = validSessions.reduce((acc, session) => {
      // Get server type from API field
      let serverType = session.server_type || ''

      if (serverType) {
        // Normalize the server type
        serverType = String(serverType).toLowerCase().trim()
      }

      // If no server type or it's invalid, try to infer from name
      if (!serverType || !['plex', 'emby', 'jellyfin'].includes(serverType)) {
        const serverName = (session.server_name || '').toLowerCase()

        // Try to infer from server name if type is missing
        if (serverName.includes('plex')) {
          serverType = 'plex'
        } else if (serverName.includes('emby')) {
          serverType = 'emby'
        } else if (serverName.includes('jellyfin')) {
          serverType = 'jellyfin'
        } else {
          serverType = 'unknown'
        }
      }

      const serverName = session.server_name || 'Unknown Server'

      if (!acc[serverType]) {
        acc[serverType] = {}
      }

      if (!acc[serverType][serverName]) {
        acc[serverType][serverName] = []
      }

      acc[serverType][serverName].push(session)
      return acc
    }, {} as Record<string, Record<string, LiveSession[]>>)

    // Sort server types by predefined order
    const sortedTypes = Object.keys(grouped).sort((a, b) => {
      const aIndex = serverTypeOrder.indexOf(a.toLowerCase())
      const bIndex = serverTypeOrder.indexOf(b.toLowerCase())
      if (aIndex === -1 && bIndex === -1) return a.localeCompare(b)
      if (aIndex === -1) return 1
      if (bIndex === -1) return -1
      return aIndex - bIndex
    })

    return sortedTypes.map(serverType => ({
      serverType,
      servers: Object.entries(grouped[serverType])
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([serverName, sessions]) => ({
          serverName,
          sessions: sessions.sort((a, b) => a.username?.localeCompare(b.username || '') || 0)
        }))
    }))
  }, [sessions])

  // Calculate aggregated statistics
  const calculateStats = (sessions: LiveSession[]) => {
    if (!Array.isArray(sessions)) {
      return {
        totalStreams: 0,
        transcodes: 0,
        directPlay: 0,
        directStream: 0,
        totalBandwidth: 0
      }
    }
    const totalStreams = sessions.length
    const transcodes = sessions.filter(s => s.video_decision === 'transcode').length
    const directPlay = sessions.filter(s => s.video_decision === 'directplay').length
    const directStream = sessions.filter(s => s.video_decision === 'copy').length
    const totalBandwidth = sessions.reduce((sum, s) => {
      const bandwidth = parseInt(s.session_bandwidth || '0')
      return sum + (isNaN(bandwidth) ? 0 : bandwidth)
    }, 0)

    return {
      totalStreams,
      transcodes,
      directPlay,
      directStream,
      totalBandwidth
    }
  }

  // const formatBytes = (bytes: number) => {
  //   if (!bytes) return '0 B'
  //   const k = 1024
  //   const sizes = ['B', 'KB', 'MB', 'GB']
  //   const i = Math.floor(Math.log(bytes) / Math.log(k))
  //   return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
  // }

  const formatBandwidth = (bandwidth: number) => {
    // Bandwidth is in Kbps
    if (!bandwidth) return '0 Mbps'
    if (bandwidth >= 1000000) {
      return `${(bandwidth / 1000000).toFixed(1)} Gbps`
    } else if (bandwidth >= 1000) {
      return `${(bandwidth / 1000).toFixed(1)} Mbps`
    }
    return `${bandwidth} Kbps`
  }

  const maskUsername = (username: string) => {
    // Only mask usernames for media users
    if (currentUser?.type === 'media_user' && username) {
      return username.charAt(0) + '****'
    }
    return username
  }

  const formatBitrate = (bitrate: string | number) => {
    if (!bitrate) return '0 Kbps'
    const bitrateNum = typeof bitrate === 'string' ? parseInt(bitrate) : bitrate
    if (bitrateNum >= 1000000) {
      return `${(bitrateNum / 1000000).toFixed(1)} Gbps`
    } else if (bitrateNum >= 1000) {
      return `${(bitrateNum / 1000).toFixed(1)} Mbps`
    }
    return `${bitrateNum} Kbps`
  }

  const formatTime = (ms: number) => {
    const hours = Math.floor(ms / 3600000)
    const minutes = Math.floor((ms % 3600000) / 60000)
    const seconds = Math.floor((ms % 60000) / 1000)

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
    }
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  const getProgressBarColor = (state: string) => {
    switch (state) {
      case 'playing': return 'bg-green-500'
      case 'paused': return 'bg-yellow-500'
      case 'buffering': return 'bg-blue-500'
      default: return 'bg-slate-500'
    }
  }

  const getStateIcon = (state: string) => {
    switch (state) {
      case 'playing': return <PlayIcon className="w-4 h-4 text-green-500" />
      case 'paused': return <PauseIcon className="w-4 h-4 text-yellow-500" />
      default: return <StopIcon className="w-4 h-4 text-slate-500" />
    }
  }

  // Bandwidth graph component
  const BandwidthGraph = () => {
    if (bandwidthHistory.length === 0) {
      return (
        <div>
          <div className="h-20 bg-slate-50 dark:bg-slate-800 rounded-lg flex items-center justify-center mb-2">
            <p className="text-sm text-slate-500">Collecting bandwidth data...</p>
          </div>
        </div>
      )
    }

    // Debug: Log the bandwidth history structure
    console.log('BandwidthGraph rendering with history:', {
      historyLength: bandwidthHistory.length,
      latestPoint: bandwidthHistory[bandwidthHistory.length - 1],
      allServerNames: Array.from(new Set(bandwidthHistory.flatMap(p => Object.keys(p.serverBandwidths || {}))))
    })

    // Find the max and min individual server bandwidth across all time points
    const allServerBandwidths: number[] = []

    bandwidthHistory.forEach(point => {
      const servers = point.serverBandwidths || point.server_bandwidths || {}
      Object.entries(servers).forEach(([serverName, bandwidth]) => {
        // Make sure we're not accidentally including a "total" entry
        if (serverName.toLowerCase() !== 'total' && bandwidth > 0) {
          allServerBandwidths.push(bandwidth)
        }
      })
    })

    let actualMaxBandwidth = 100000 // Default 100 Mbps if no data
    let actualMinBandwidth = 0

    if (allServerBandwidths.length > 0) {
      // The Y-axis should show the full range of all server bandwidths
      actualMaxBandwidth = Math.max(...allServerBandwidths)
      actualMinBandwidth = Math.min(...allServerBandwidths)
    }

    // Set Y-axis max to 20% above highest server
    const scaledMaxBandwidth = actualMaxBandwidth * 1.2

    // For minimum, we want to show the full range but not go below 0
    // If the minimum is very small compared to max, just use 0
    let scaledMinBandwidth = 0
    if (actualMinBandwidth > actualMaxBandwidth * 0.05) {
      // Only use a non-zero minimum if it's at least 5% of the maximum
      scaledMinBandwidth = Math.max(0, actualMinBandwidth * 0.8)
    }

    const maxBandwidth = scaledMaxBandwidth
    const minBandwidth = scaledMinBandwidth

    // Ensure we have a reasonable range for the graph
    const bandwidthRange = maxBandwidth - minBandwidth
    // If range is too small, adjust to avoid division issues
    let adjustedMaxBandwidth = bandwidthRange < 1000 ? minBandwidth + 10000 : maxBandwidth
    let adjustedMinBandwidth = minBandwidth

    // If we have no server data, try to estimate from total
    if (allServerBandwidths.length === 0 && bandwidthHistory.length > 0) {
      const latestTotal = bandwidthHistory[bandwidthHistory.length - 1].totalBandwidth || bandwidthHistory[bandwidthHistory.length - 1].total_bandwidth
      if (latestTotal && latestTotal > 0) {
        // No individual server data but have total - estimate max as half of total
        // (assuming at least 2 servers sharing the load)
        const estimatedServerMax = latestTotal / 2
        adjustedMaxBandwidth = estimatedServerMax * 1.2
        adjustedMinBandwidth = 0  // Start from 0 when we have no actual server data
      }
    }

    const formatTimestamp = (timestamp: string | number) => {
      const date = typeof timestamp === 'string' ? new Date(timestamp) : new Date(timestamp)
      return date.toLocaleTimeString('en-US', {
        hour12: false,
        minute: '2-digit',
        second: '2-digit'
      })
    }

    // Create evenly spaced intervals between min and max
    const displayRange = adjustedMaxBandwidth - adjustedMinBandwidth
    const bandwidthIntervals = [
      adjustedMaxBandwidth,
      adjustedMinBandwidth + displayRange * 0.75,
      adjustedMinBandwidth + displayRange * 0.5,
      adjustedMinBandwidth + displayRange * 0.25,
      adjustedMinBandwidth
    ]

    return (
      <div>
        {/* Graph Container with Y-axis labels */}
        <div className="relative h-32 flex mb-2">
          {/* Graph area */}
          <div className="flex-1 bg-slate-50 dark:bg-slate-800 rounded-lg p-2 relative">
            <div className="absolute inset-2">
            <svg className="w-full h-full" viewBox="0 0 800 100" preserveAspectRatio="none">
              {/* Grid lines */}
              <defs>
                <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                  <path d="M 20 0 L 0 0 0 20" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-slate-300 dark:text-slate-600" opacity="0.3"/>
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid)" />

              {/* Horizontal bandwidth interval lines */}
              {bandwidthIntervals.slice(1, -1).map((bandwidth, index) => {
                const y = ((adjustedMaxBandwidth - bandwidth) / (adjustedMaxBandwidth - adjustedMinBandwidth)) * 85 + 5 // 5% top margin, 10% bottom margin
                return (
                  <line
                    key={index}
                    x1="0"
                    y1={y}
                    x2="800"
                    y2={y}
                    stroke="currentColor"
                    strokeWidth="0.5"
                    strokeDasharray="4,4"
                    className="text-slate-400 dark:text-slate-500"
                    opacity="0.5"
                  />
                )
              })}

              {/* Time interval markers - every 5 seconds (18 points total for 90 seconds) */}
              {[...Array(18)].map((_, index) => {
                const x = (index / 17) * 800  // 18 points, 0-17 index, scaled to full 800 width
                const isMajor = index % 3 === 0  // Major marker every 15 seconds (every 3rd point)
                return (
                  <line
                    key={index}
                    x1={x}
                    y1={isMajor ? "88" : "92"}
                    x2={x}
                    y2="95"
                    stroke="currentColor"
                    strokeWidth={isMajor ? "0.8" : "0.4"}
                    className="text-slate-400 dark:text-slate-500"
                    opacity={isMajor ? "0.7" : "0.4"}
                  />
                )
              })}

              {/* Individual server lines - render each as a separate group */}
              {Object.keys(serverColors).map((serverName, serverIndex) => {
                // Build path data for this server
                const pathData = bandwidthHistory.map((point, index) => {
                  // Use proper x scaling for 800-width viewBox (full width)
                  const x = bandwidthHistory.length === 1 ? 400 : (index / (bandwidthHistory.length - 1)) * 800
                  const servers = point.serverBandwidths || point.server_bandwidths || {}
                  const bandwidth = servers[serverName] || 0
                  const range = adjustedMaxBandwidth - adjustedMinBandwidth
                  const y = range > 0 ? 95 - ((bandwidth - adjustedMinBandwidth) / range) * 85 : 50
                  return { x, y, bandwidth }
                })

                // Debug: Log path data for first server only to avoid spam
                if (serverIndex === 0 && pathData.length > 0) {
                  console.log(`Graph data for ${serverName}:`, {
                    latestBandwidth: pathData[pathData.length - 1]?.bandwidth,
                    yPosition: pathData[pathData.length - 1]?.y,
                    adjustedMax: adjustedMaxBandwidth,
                    adjustedMin: adjustedMinBandwidth
                  })
                }

                // Skip if no data
                if (pathData.length === 0) return null

                // Build SVG path string
                const pathString = pathData.map((point, index) => {
                  return `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`
                }).join(' ')

                return (
                  <g key={`server-${serverName}-${serverIndex}`}>
                    <path
                      d={pathString}
                      fill="none"
                      stroke={serverColors[serverName]}
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      opacity="0.9"
                    />
                    {/* Add dots at data points for better visibility */}
                    {pathData.length <= 20 && pathData.map((point, pointIndex) => (
                      point.bandwidth > 0 && (
                        <circle
                          key={`dot-${pointIndex}`}
                          cx={point.x}
                          cy={point.y}
                          r="2"
                          fill={serverColors[serverName]}
                          opacity="1"
                        />
                      )
                    ))}
                  </g>
                )
              })}
            </svg>
            </div>
          </div>

          {/* Y-axis labels column on the right */}
          <div className="w-20 flex flex-col justify-between py-2 pl-1 text-xs text-slate-500 dark:text-slate-400">
            {bandwidthIntervals.map((bandwidth, index) => (
              <span key={index} className="leading-none text-right whitespace-nowrap">
                {formatBitrate(bandwidth)}
              </span>
            ))}
          </div>
        </div>

        {/* Time labels below graph - show time ago */}
        <div className="relative h-4 mb-2 flex">
          <div className="flex-1 px-2 relative text-xs text-slate-500 dark:text-slate-400">
            {/* Fixed time labels every 15 seconds */}
            <span className="absolute transform -translate-x-1/2" style={{ left: '0%' }}>
              1:30
            </span>
            <span className="absolute transform -translate-x-1/2" style={{ left: '16.67%' }}>
              1:15
            </span>
            <span className="absolute transform -translate-x-1/2" style={{ left: '33.33%' }}>
              1:00
            </span>
            <span className="absolute transform -translate-x-1/2" style={{ left: '50%' }}>
              0:45
            </span>
            <span className="absolute transform -translate-x-1/2" style={{ left: '66.67%' }}>
              0:30
            </span>
            <span className="absolute transform -translate-x-1/2" style={{ left: '83.33%' }}>
              0:15
            </span>
            <span className="absolute transform -translate-x-1/2" style={{ left: '100%' }}>
              Current
            </span>
          </div>
          <div className="w-20"></div> {/* Spacer to match Y-axis column */}
        </div>

        {/* Legend below graph */}
        <div className="bg-slate-100 dark:bg-slate-700 rounded-lg p-3">
          <div className="flex flex-wrap gap-4 text-xs">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-white border border-slate-400"></div>
              <span className="text-slate-700 dark:text-slate-300 font-medium">
                Total: {formatBitrate(bandwidthHistory[bandwidthHistory.length - 1]?.totalBandwidth || 0)}
              </span>
            </div>
            {Object.entries(serverColors).map(([serverName, color]) => {
              const serverInfo = getServerInfo(serverName)
              const lastPoint = bandwidthHistory[bandwidthHistory.length - 1]
              const servers = lastPoint ? (lastPoint.serverBandwidths || lastPoint.server_bandwidths || {}) : {}
              const bandwidth = servers[serverName] || 0
              return (
                <div key={serverName} className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: color }}></div>
                  <span className={`${serverInfo.color}`}>
                    {serverInfo.displayName}: {formatBitrate(bandwidth)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4 py-6 sm:px-6 min-h-screen">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Admin Dashboard
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          Monitor active sessions and view analytics across all media servers
        </p>
      </div>

      {/* Active Sessions Section */}
      {(isAdmin || hasPermission('view_sessions')) ? (
        <div className="mb-8">
        <div className="flex items-center gap-2 mb-4">
          <SignalIcon className="w-5 h-5 text-green-500" />
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
            Active Sessions ({sessions.length})
          </h2>
        </div>

        {/* Bandwidth Graph */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <ChartBarIcon className="w-4 h-4 text-blue-500" />
            <h3 className="text-sm font-medium text-slate-900 dark:text-white">
              Bandwidth (Last 5 Minutes)
            </h3>
          </div>
          <BandwidthGraph />
        </div>

        {/* GPU Status */}
        {gpuStatus && gpuStatus.total_transcodes > 0 && (
          <div className="mb-6 min-h-[200px]">
            <div className="flex items-center gap-2 mb-2">
              <CpuChipIcon className="w-4 h-4 text-purple-500" />
              <h3 className="text-sm font-medium text-slate-900 dark:text-white">
                GPU Utilization
              </h3>
            </div>
            <div className="card">
              <div className="card-body">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                      {gpuStatus.total_hw_transcodes}
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">Hardware Transcodes</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                      {gpuStatus.total_sw_transcodes}
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">Software Transcodes</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                      {gpuStatus.hw_percentage}%
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">GPU Utilization</div>
                  </div>
                </div>

                {/* Progress bar showing GPU utilization */}
                <div className="mb-4">
                  <div className="flex justify-between text-xs text-slate-600 dark:text-slate-400 mb-1">
                    <span>GPU Usage</span>
                    <span>{gpuStatus.hw_percentage}% Hardware Accelerated</span>
                  </div>
                  <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-3">
                    <div
                      className="h-3 rounded-full bg-gradient-to-r from-purple-500 to-purple-600"
                      style={{ width: `${Math.min(100, Math.max(0, gpuStatus.hw_percentage))}%` }}
                    />
                  </div>
                </div>

                {/* Server breakdown */}
                {gpuStatus.servers.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-slate-700 dark:text-slate-300">By Server:</div>
                    {gpuStatus.servers.map(server => (
                      <div key={server.server_id} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <ServerIcon className="w-3 h-3 text-slate-400" />
                          <span className="text-slate-900 dark:text-white">{server.server_name}</span>
                        </div>
                        <div className="flex items-center gap-4">
                          {server.hw_transcodes > 0 && (
                            <span className="text-purple-600 dark:text-purple-400">
                              <CpuChipIcon className="w-3 h-3 inline mr-1" />
                              {server.hw_transcodes} HW
                            </span>
                          )}
                          {server.sw_transcodes > 0 && (
                            <span className="text-orange-600 dark:text-orange-400">
                              <ComputerDesktopIcon className="w-3 h-3 inline mr-1" />
                              {server.sw_transcodes} SW
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Warning if too many software transcodes */}
                {gpuStatus.hw_percentage < 50 && gpuStatus.total_transcodes >= 2 && (
                  <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                    <div className="flex items-start gap-2">
                      <ExclamationTriangleIcon className="w-5 h-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
                          Low GPU Utilization
                        </p>
                        <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-1">
                          Most transcodes are using CPU instead of GPU. Consider checking your hardware acceleration settings.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {sessionsError ? (
          <div className="card">
            <div className="card-body">
              <p className="text-red-600 dark:text-red-400">Failed to load sessions. Please check your connection.</p>
            </div>
          </div>
        ) : sessionsLoading ? (
          <div className="card">
            <div className="card-body">
              <p className="text-slate-600 dark:text-slate-400">Loading active sessions...</p>
            </div>
          </div>
        ) : !sessions || sessions.length === 0 ? (
          <div className="card">
            <div className="card-body text-center">
              <DevicePhoneMobileIcon className="w-12 h-12 mx-auto text-slate-400 mb-3" />
              <p className="text-slate-600 dark:text-slate-400">No active playback sessions</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {groupedSessions.map(({ serverType, servers }) => {
              const allServerTypeSessions = servers ? servers.flatMap(server => server.sessions || []) : []
              const serverTypeStats = calculateStats(allServerTypeSessions)

              return (
                <Disclosure key={serverType} defaultOpen={true}>
                  {({ open }) => (
                    <div className="card">
                      <Disclosure.Button className="w-full">
                        <div className="card-body">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                              {open ? (
                                <ChevronDownIcon className="h-4 w-4 text-slate-500" />
                              ) : (
                                <ChevronRightIcon className="h-4 w-4 text-slate-500" />
                              )}
                              <div className="inline-flex items-center">{getServerTypeIcon(serverType)}</div>
                              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                                {getServerTypeName(serverType)}
                              </h3>
                            </div>
                            <div className="flex items-center space-x-4 text-sm">
                              <div className="flex items-center">
                                <PlayIcon className="h-3 w-3 text-slate-400 mr-1" />
                                <span className="font-medium text-slate-900 dark:text-white">
                                  {serverTypeStats.totalStreams}
                                </span>
                              </div>
                              <div className="flex items-center">
                                <SignalIcon className="h-3 w-3 text-orange-500 mr-1" />
                                <span className="font-medium text-slate-900 dark:text-white">
                                  {serverTypeStats.transcodes}
                                </span>
                              </div>
                              <div className="flex items-center">
                                <ArrowDownTrayIcon className="h-3 w-3 text-blue-500 mr-1" />
                                <span className="font-medium text-slate-900 dark:text-white">
                                  {formatBandwidth(serverTypeStats.totalBandwidth)}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </Disclosure.Button>

                      <Transition
                        show={open}
                        enter="transition duration-150 ease-out"
                        enterFrom="transform scale-95 opacity-0"
                        enterTo="transform scale-100 opacity-100"
                        leave="transition duration-75 ease-out"
                        leaveFrom="transform scale-100 opacity-100"
                        leaveTo="transform scale-95 opacity-0"
                      >
                        <Disclosure.Panel>
                          <div className="px-6 pb-6 space-y-3">
                            {servers.map(({ serverName, sessions: serverSessions }) => {
                              const serverStats = calculateStats(serverSessions)

                              return (
                                <Disclosure key={`${serverType}-${serverName}`} defaultOpen={true}>
                                  {({ open: serverOpen }) => (
                                    <div className="border border-slate-200 dark:border-slate-700 rounded-lg">
                                      <Disclosure.Button className="w-full">
                                        <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-t-lg">
                                          <div className="flex items-center justify-between">
                                            <div className="flex items-center space-x-2">
                                              {serverOpen ? (
                                                <ChevronDownIcon className="h-3 w-3 text-slate-500" />
                                              ) : (
                                                <ChevronRightIcon className="h-3 w-3 text-slate-500" />
                                              )}
                                              <h4 className={`text-sm font-semibold ${getServerTypeColor(serverType)}`}>
                                                {serverName}
                                              </h4>
                                            </div>
                                            <div className="flex items-center space-x-3 text-xs">
                                              <span className="font-medium">{serverStats.totalStreams} streams</span>
                                              <span className="font-medium text-orange-500">{serverStats.transcodes} transcoding</span>
                                              <span className="font-medium text-blue-500">{formatBandwidth(serverStats.totalBandwidth)}</span>
                                            </div>
                                          </div>
                                        </div>
                                      </Disclosure.Button>

                                      <Transition
                                        show={serverOpen}
                                        enter="transition duration-100 ease-out"
                                        enterFrom="transform scale-95 opacity-0"
                                        enterTo="transform scale-100 opacity-100"
                                        leave="transition duration-75 ease-out"
                                        leaveFrom="transform scale-100 opacity-100"
                                        leaveTo="transform scale-95 opacity-0"
                                      >
                                        <Disclosure.Panel>
                                          <div className="p-3 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                                            {serverSessions.map((session) => (
              <div key={session.session_id} className="border border-slate-100 dark:border-slate-700 rounded p-3">
                                                <div className="flex items-start justify-between mb-2">
                                                  <div>
                                                    <h5 className="font-medium text-slate-900 dark:text-white text-xs mb-1">
                                                      {session.title || session.full_title || 'Unknown Media'}
                                                    </h5>
                                                    {session.grandparent_title && (
                                                      <p className="text-xs text-slate-600 dark:text-slate-400">
                                                        {session.grandparent_title}
                                                        {session.parent_title && ` - ${session.parent_title}`}
                                                      </p>
                                                    )}
                                                  </div>
                                                  {/* Show terminate button for:
                                                     1. Admins and staff with terminate permission (all sessions)
                                                     2. Media users (only their own sessions) */}
                                                  {(isAdmin || hasPermission('terminate_sessions') ||
                                                    (currentUser?.type === 'media_user' &&
                                                     session.username?.toLowerCase() === currentUser?.username?.toLowerCase())) && (
                                                    <button
                                                      onClick={() => handleTerminateClick(
                                                        session.server_id!,
                                                        session.session_id,
                                                        serverType
                                                      )}
                                                      disabled={terminateSessionMutation.isLoading}
                                                      className="p-1 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                                                      title="Terminate Session"
                                                    >
                                                      <XMarkIcon className="w-3 h-3" />
                                                    </button>
                                                  )}
                                                </div>

                                                <div className="space-y-2 text-xs text-slate-600 dark:text-slate-400">
                                                  <div className="flex justify-between">
                                                    <span>Username:</span>
                                                    <span className="font-medium text-slate-900 dark:text-white">{maskUsername(session.username || 'Unknown')}</span>
                                                  </div>
                                                  <div className="flex justify-between">
                                                    <span>Device:</span>
                                                    <span className="font-medium text-slate-900 dark:text-white">{session.device || 'Unknown'}</span>
                                                  </div>
                                                  <div className="flex justify-between">
                                                    <span>Player:</span>
                                                    <span className="font-medium text-slate-900 dark:text-white">{session.product || session.platform || 'Unknown'}</span>
                                                  </div>
                                                  <div className="flex justify-between">
                                                    <span>State:</span>
                                                    <span className="flex items-center gap-1">
                                                      {getStateIcon(session.state)}
                                                      <span className="capitalize font-medium text-slate-900 dark:text-white">{session.state}</span>
                                                      {session.video_decision === 'transcode' ? (
                                                        <>
                                                          {(session.transcode_hw_full_pipeline || (session.transcode_hw_decode && session.transcode_hw_encode) || (session.transcode_hw_decode_title && session.transcode_hw_encode_title)) ? (
                                                            <span className="flex items-center text-purple-600 dark:text-purple-400 ml-1">
                                                              <CpuChipIcon className="w-3 h-3 mr-0.5" />
                                                              <span className="text-xs">HW Transcode</span>
                                                            </span>
                                                          ) : (session.transcode_hw_decode || session.transcode_hw_encode || session.transcode_hw_decode_title || session.transcode_hw_encode_title) ? (
                                                            <span className="flex items-center text-blue-600 dark:text-blue-400 ml-1">
                                                              <CpuChipIcon className="w-3 h-3 mr-0.5" />
                                                              <span className="text-xs">Partial HW</span>
                                                            </span>
                                                          ) : (
                                                            <span className="flex items-center text-orange-600 dark:text-orange-400 ml-1">
                                                              <ComputerDesktopIcon className="w-3 h-3 mr-0.5" />
                                                              <span className="text-xs">SW Transcode</span>
                                                            </span>
                                                          )}
                                                        </>
                                                      ) : (
                                                        <span className="text-green-500 ml-1">• Direct Play</span>
                                                      )}
                                                    </span>
                                                  </div>
                                                  <div className="flex justify-between">
                                                    <span>Video Codec:</span>
                                                    <span className="font-medium text-slate-900 dark:text-white">{session.video_codec || 'Unknown'}</span>
                                                  </div>
                                                  {/* Resolution - Show transcoding details if video is being transcoded */}
                                                  {session.video_decision === 'transcode' ? (
                                                    <div className="flex justify-between">
                                                      <span>Resolution:</span>
                                                      <span className="font-medium text-slate-900 dark:text-white text-xs">
                                                        <span className="text-slate-600 dark:text-slate-400">From:</span> {session.original_resolution || 'Unknown'}
                                                        {session.is_4k && <span className="text-purple-600 ml-1">• 4K</span>}
                                                        <br />
                                                        <span className="text-slate-600 dark:text-slate-400">To:</span> {session.stream_resolution || session.original_resolution || 'Unknown'}
                                                      </span>
                                                    </div>
                                                  ) : (
                                                    <div className="flex justify-between">
                                                      <span>Resolution:</span>
                                                      <span className="font-medium text-slate-900 dark:text-white">
                                                        {session.original_resolution || 'Unknown'}
                                                        {session.is_4k && <span className="text-purple-600 ml-1">• 4K</span>}
                                                      </span>
                                                    </div>
                                                  )}

                                                  <div className="flex justify-between">
                                                    <span>HDR:</span>
                                                    <span className="font-medium text-slate-900 dark:text-white">
                                                      {session.is_dolby_vision ? (
                                                        <span className="text-purple-600">Dolby Vision</span>
                                                      ) : session.is_hdr ? (
                                                        <span className="text-blue-600">HDR</span>
                                                      ) : (
                                                        <span className="text-slate-500">None</span>
                                                      )}
                                                    </span>
                                                  </div>

                                                  {/* Bitrate - Show transcoding details if video is being transcoded */}
                                                  {session.video_decision === 'transcode' ? (
                                                    <div className="flex justify-between">
                                                      <span>Video Bitrate:</span>
                                                      <span className="font-medium text-slate-900 dark:text-white text-xs">
                                                        <span className="text-slate-600 dark:text-slate-400">Original:</span> {formatBitrate(session.original_bitrate || 0)}
                                                        <br />
                                                        <span className="text-slate-600 dark:text-slate-400">Stream:</span> {formatBitrate(session.stream_bitrate || 0)}
                                                      </span>
                                                    </div>
                                                  ) : (
                                                    <div className="flex justify-between">
                                                      <span>Bitrate:</span>
                                                      <span className="font-medium text-slate-900 dark:text-white">
                                                        {session.stream_bitrate ? formatBitrate(session.stream_bitrate) :
                                                         session.original_bitrate ? formatBitrate(session.original_bitrate) : 'Unknown'}
                                                      </span>
                                                    </div>
                                                  )}

                                                  {/* Audio - Show transcoding details if audio is being transcoded */}
                                                  {session.audio_decision === 'transcode' ? (
                                                    <div className="flex justify-between">
                                                      <span>Audio:</span>
                                                      <span className="font-medium text-slate-900 dark:text-white text-xs">
                                                        <span className="text-slate-600 dark:text-slate-400">Original:</span> {session.original_audio_codec || 'Unknown'}
                                                        {session.original_audio_channels && ` ${session.original_audio_channels}ch`}
                                                        <br />
                                                        <span className="text-slate-600 dark:text-slate-400">Stream:</span> {session.audio_codec || 'Unknown'}
                                                        {session.audio_channels && ` ${session.audio_channels}ch`}
                                                      </span>
                                                    </div>
                                                  ) : null}

                                                  <div className="flex justify-between">
                                                    <span>Bandwidth:</span>
                                                    <span className="font-medium text-blue-600 dark:text-blue-400">
                                                      {session.session_bandwidth ? formatBitrate(session.session_bandwidth) : 'Unknown'}
                                                    </span>
                                                  </div>
                                                </div>

                                                {/* Progress Bar */}
                                                <div className="mt-3">
                                                  <div className="flex justify-between text-xs text-slate-600 dark:text-slate-400 mb-1">
                                                    <span>{formatTime(session.progress_ms)}</span>
                                                    <span className="text-center">
                                                      {session.progress_percent?.toFixed(1) || '0.0'}% / {formatTime((session.duration_ms || 0) - (session.progress_ms || 0))} remaining
                                                    </span>
                                                    <span>{formatTime(session.duration_ms)}</span>
                                                  </div>
                                                  <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                                                    <div
                                                      className={`h-2 rounded-full transition-all duration-300 ${getProgressBarColor(session.state)}`}
                                                      style={{ width: `${Math.min(100, Math.max(0, session.progress_percent || 0))}%` }}
                                                    />
                                                  </div>
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                        </Disclosure.Panel>
                                      </Transition>
                                    </div>
                                  )}
                                </Disclosure>
                              )
                            })}
                          </div>
                        </Disclosure.Panel>
                      </Transition>
                    </div>
                  )}
                </Disclosure>
              )
            })}
          </div>
        )}
      </div>
      ) : null}

      {/* Analytics Section */}
      {(isAdmin || hasPermission('view_analytics')) ? (
        <div>
          <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ChartBarIcon className="w-5 h-5 text-blue-500" />
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
              Analytics
            </h2>
          </div>

          {/* Analytics Filters */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm text-slate-600 dark:text-slate-400">Server:</label>
              <select
                value={analyticsFilters.server_id || ''}
                onChange={(e) => setAnalyticsFilters(prev => ({
                  ...prev,
                  server_id: e.target.value ? parseInt(e.target.value) : undefined
                }))}
                className="text-sm bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded px-2 py-1"
              >
                <option value="">All Servers</option>
                {servers.map((server: any) => (
                  <option key={server.id} value={server.id}>
                    {server.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-sm text-slate-600 dark:text-slate-400">Range:</label>
              <select
                value={analyticsFilters.days_back}
                onChange={(e) => setAnalyticsFilters(prev => ({
                  ...prev,
                  days_back: parseInt(e.target.value)
                }))}
                className="text-sm bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded px-2 py-1"
              >
                <option value={1}>Last 24 Hours</option>
                <option value={7}>Last 7 Days</option>
                <option value={31}>Last 31 Days</option>
                <option value={365}>Last 365 Days</option>
              </select>
            </div>
          </div>
        </div>

        {analyticsLoading ? (
          <div className="card">
            <div className="card-body">
              <p className="text-slate-600 dark:text-slate-400">Loading analytics...</p>
            </div>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {/* Summary Stats */}
            <div className="card md:col-span-2 lg:col-span-3">
              <div className="card-body">
                <h3 className="font-semibold text-slate-900 dark:text-white mb-4">Overview</h3>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                      {analytics?.total_sessions || 0}
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">Total Sessions</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                      {analytics?.total_users || 0}
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">Unique Users</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                      {analytics?.total_watch_time_hours || 0}h
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">Watch Time</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                      {analytics?.completion_rate?.toFixed(1) || 0}%
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">Completion Rate</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                      {analytics?.transcode_rate?.toFixed(1) || 0}%
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">Transcode Rate</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Top Users */}
            <div className="card">
              <div className="card-body">
                <div className="flex items-center gap-2 mb-3">
                  <UsersIcon className="w-4 h-4 text-blue-500" />
                  <h3 className="font-semibold text-slate-900 dark:text-white">Most Active Users</h3>
                </div>
                {analytics?.top_users?.length ? (
                  <div className="space-y-2">
                    {analytics.top_users.slice(0, 5).map((user, index) => (
                      <div key={index} className="flex justify-between items-center text-sm">
                        <span className="text-slate-900 dark:text-white">{maskUsername(user.username)}</span>
                        <div className="text-right">
                          <div className="text-slate-600 dark:text-slate-400">{user.total_plays} plays</div>
                          <div className="text-xs text-slate-500">{Math.round(user.total_watch_time_minutes / 60)}h</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No data available</p>
                )}
              </div>
            </div>

            {/* Top Movies */}
            <div className="card">
              <div className="card-body">
                <div className="flex items-center gap-2 mb-3">
                  <FilmIcon className="w-4 h-4 text-green-500" />
                  <h3 className="font-semibold text-slate-900 dark:text-white">Most Watched Movies</h3>
                </div>
                {analytics?.top_movies?.length ? (
                  <div className="space-y-2">
                    {analytics.top_movies.slice(0, 5).map((movie, index) => (
                      <div key={index} className="text-sm">
                        <div className="text-slate-900 dark:text-white truncate">{movie.title}</div>
                        <div className="text-xs text-slate-500">{movie.total_plays} plays • {movie.unique_users} users</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No data available</p>
                )}
              </div>
            </div>

            {/* Top TV Shows */}
            <div className="card">
              <div className="card-body">
                <div className="flex items-center gap-2 mb-3">
                  <TvIcon className="w-4 h-4 text-purple-500" />
                  <h3 className="font-semibold text-slate-900 dark:text-white">Most Watched TV Shows</h3>
                </div>
                {analytics?.top_tv_shows?.length ? (
                  <div className="space-y-2">
                    {analytics.top_tv_shows.slice(0, 5).map((show, index) => (
                      <div key={index} className="text-sm">
                        <div className="text-slate-900 dark:text-white truncate">{show.title}</div>
                        <div className="text-xs text-slate-500">{show.total_plays} plays • {show.unique_users} users</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No data available</p>
                )}
              </div>
            </div>

            {/* Top Libraries */}
            <div className="card">
              <div className="card-body">
                <div className="flex items-center gap-2 mb-3">
                  <FolderIcon className="w-4 h-4 text-orange-500" />
                  <h3 className="font-semibold text-slate-900 dark:text-white">Most Used Libraries</h3>
                </div>
                {analytics?.top_libraries?.length ? (
                  <div className="space-y-2">
                    {analytics.top_libraries.slice(0, 5).map((library, index) => (
                      <div key={index} className="text-sm">
                        <div className="text-slate-900 dark:text-white truncate">{library.library_name}</div>
                        <div className="text-xs text-slate-500">{library.total_plays} plays • {library.unique_users} users</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No data available</p>
                )}
              </div>
            </div>

            {/* Top Devices */}
            <div className="card">
              <div className="card-body">
                <div className="flex items-center gap-2 mb-3">
                  <DevicePhoneMobileIcon className="w-4 h-4 text-red-500" />
                  <h3 className="font-semibold text-slate-900 dark:text-white">Most Common Devices</h3>
                </div>
                {analytics?.top_devices?.length ? (
                  <div className="space-y-2">
                    {analytics.top_devices.slice(0, 5).map((device, index) => (
                      <div key={index} className="text-sm">
                        <div className="text-slate-900 dark:text-white truncate">{device.device_name}</div>
                        <div className="text-xs text-slate-500">{device.total_sessions} sessions • {device.transcode_percentage?.toFixed(1) || '0.0'}% transcode</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No data available</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
      ) : null}

      {/* Plex Termination Message Modal */}
      <Transition show={plexTerminateModal.open} as={React.Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setPlexTerminateModal({ open: false })}>
          <Transition.Child
            as={React.Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black bg-opacity-25" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4 text-center">
              <Transition.Child
                as={React.Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white dark:bg-slate-800 p-6 text-left align-middle shadow-xl transition-all">
                  <Dialog.Title
                    as="h3"
                    className="text-lg font-medium leading-6 text-slate-900 dark:text-white"
                  >
                    Terminate Plex Stream
                  </Dialog.Title>
                  <div className="mt-2">
                    <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                      Enter a message to display to the user (optional). If left blank, the default message will be used.
                    </p>
                    <textarea
                      value={plexTerminateMessage}
                      onChange={(e) => setPlexTerminateMessage(e.target.value)}
                      placeholder="Enter termination message..."
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 dark:bg-slate-700 dark:text-white"
                      rows={3}
                    />
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                      Default: "{defaultPlexMessage}"
                    </p>
                  </div>

                  <div className="mt-4 flex justify-end space-x-2">
                    <button
                      type="button"
                      className="inline-flex justify-center rounded-md border border-transparent bg-slate-100 px-4 py-2 text-sm font-medium text-slate-900 hover:bg-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600"
                      onClick={() => setPlexTerminateModal({ open: false })}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="inline-flex justify-center rounded-md border border-transparent bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2"
                      onClick={() => {
                        if (plexTerminateModal.serverId && plexTerminateModal.sessionId) {
                          terminateSessionMutation.mutate({
                            serverId: plexTerminateModal.serverId,
                            sessionId: plexTerminateModal.sessionId,
                            message: plexTerminateMessage || defaultPlexMessage
                          })
                        }
                      }}
                      disabled={terminateSessionMutation.isLoading}
                    >
                      {terminateSessionMutation.isLoading ? 'Terminating...' : 'Terminate Stream'}
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  )
}