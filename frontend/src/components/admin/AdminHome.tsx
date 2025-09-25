import React, { useMemo } from 'react'
import { useQuery, useMutation } from 'react-query'
import toast from 'react-hot-toast'
import {
  ServerIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  UsersIcon,
  ClockIcon,
  DevicePhoneMobileIcon,
  SignalIcon,
  TrophyIcon,
  FilmIcon,
  TvIcon,
  FolderIcon,
  ChartBarIcon,
  XMarkIcon,
  ChevronDownIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline'
import { Disclosure, Transition } from '@headlessui/react'
import api from '../../services/api'

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
  timestamp: number
  totalBandwidth: number
  serverBandwidths: Record<string, number>
}

export default function AdminHome() {
  // Bandwidth tracking state for the graph
  const [bandwidthHistory, setBandwidthHistory] = React.useState<BandwidthDataPoint[]>([])

  // Analytics filter state
  const [analyticsFilters, setAnalyticsFilters] = React.useState({
    server_id: undefined as number | undefined,
    days_back: 7
  })

  // Get active sessions with 1-second refresh for live bandwidth updates
  const { data: sessions = [], isLoading: sessionsLoading, refetch: refetchSessions } = useQuery<LiveSession[]>(
    'admin-sessions',
    () => api.get('/admin/sessions').then(res => res.data),
    {
      refetchInterval: 1000, // 1-second refresh for live updates
      refetchOnWindowFocus: false,
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
      refetchInterval: 30000, // Refresh every 30 seconds
      refetchOnWindowFocus: false,
    }
  )

  // Terminate session mutation
  const terminateSessionMutation = useMutation(
    ({ serverId, sessionId }: { serverId: number, sessionId: string }) => {
      console.log(`Attempting to terminate session ${sessionId} on server ${serverId}`)
      return api.post(`/admin/servers/${serverId}/sessions/${sessionId}/terminate`)
    },
    {
      onSuccess: () => {
        console.log('Session terminated successfully')
        toast.success('Session terminated successfully')
        refetchSessions()
      },
      onError: (error: any) => {
        console.error('Termination error:', error)
        const errorMessage = error.response?.data?.detail || 'Failed to terminate session'
        toast.error(errorMessage)
      }
    }
  )

  // Store sessions in a ref to avoid re-running effect on every update
  const sessionsRef = React.useRef(sessions)
  React.useEffect(() => {
    sessionsRef.current = sessions
  }, [sessions])

  // Track bandwidth data every 15 seconds
  React.useEffect(() => {
    const trackBandwidth = () => {
      const now = Date.now()
      const fiveMinutesAgo = now - 5 * 60 * 1000

      // Calculate total bandwidth and per-server bandwidth
      let totalBandwidth = 0
      const serverBandwidths: Record<string, number> = {}

      const currentSessions = sessionsRef.current
      if (currentSessions && currentSessions.length > 0) {
        currentSessions.forEach(session => {
          const bandwidth = session.session_bandwidth ?
            (typeof session.session_bandwidth === 'string' ?
              parseInt(session.session_bandwidth) : session.session_bandwidth) : 0

          totalBandwidth += bandwidth

          const serverKey = session.server_name || `Server ${session.server_id || 'Unknown'}`
          serverBandwidths[serverKey] = (serverBandwidths[serverKey] || 0) + bandwidth

          // Debug logging for Jellyfin sessions
          if (session.server_type === 'jellyfin' || (session.server_name && session.server_name.toLowerCase().includes('jellyfin'))) {
            console.log('Jellyfin session in bandwidth tracking:', {
              serverName: session.server_name,
              serverType: session.server_type,
              bandwidth: bandwidth,
              serverKey: serverKey
            })
          }
        })
      }

      setBandwidthHistory(prev => {
        const newHistory = [...prev, {
          timestamp: now,
          totalBandwidth,
          serverBandwidths
        }]

        // Keep only last 5 minutes of data (20 points at 15-second intervals)
        return newHistory.filter(point => point.timestamp > fiveMinutesAgo).slice(-20)
      })
    }

    // Track immediately, then every 15 seconds
    trackBandwidth()
    const interval = setInterval(trackBandwidth, 15000)

    return () => clearInterval(interval)
  }, []) // Empty dependency array - only run once

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
      Object.keys(point.serverBandwidths).forEach(server => serverNames.add(server))
    })

    const serverColorMap: Record<string, string> = {}
    Array.from(serverNames).forEach((server, index) => {
      // Never assign white (#FFFFFF) to servers - it's reserved for Total
      serverColorMap[server] = colors[index % colors.length]
    })

    console.log('Bandwidth chart server colors:', {
      servers: Array.from(serverNames),
      colorMap: serverColorMap
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
        return '🍊'
      case 'emby':
        return '🟢'
      case 'jellyfin':
        return '🔵'
      default:
        return '⚪'
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

    const grouped = sessions.reduce((acc, session) => {
      // Get server type from API field
      let serverType = session.server_type || session.serverType || session.type || ''

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

  const formatBytes = (bytes: number) => {
    if (!bytes) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
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
    return `${hours}:${minutes.toString().padStart(2, '0')}`
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

    const maxBandwidth = Math.max(
      ...bandwidthHistory.map(point => point.totalBandwidth),
      ...bandwidthHistory.flatMap(point => Object.values(point.serverBandwidths)),
      1 // Ensure we have at least 1 to avoid division by zero
    )

    const formatTime = (timestamp: number) => {
      const date = new Date(timestamp)
      return date.toLocaleTimeString('en-US', {
        hour12: false,
        minute: '2-digit',
        second: '2-digit'
      })
    }

    const bandwidthIntervals = [
      maxBandwidth,
      maxBandwidth * 0.75,
      maxBandwidth * 0.5,
      maxBandwidth * 0.25,
      0
    ]

    return (
      <div>
        {/* Graph Container */}
        <div className="relative h-28 bg-slate-50 dark:bg-slate-800 rounded-lg p-2 mb-2">
          <div className="absolute inset-2 pr-16"> {/* Leave space for Y-axis labels on right */}
            <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
              {/* Grid lines */}
              <defs>
                <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                  <path d="M 20 0 L 0 0 0 20" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-slate-300 dark:text-slate-600" opacity="0.3"/>
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid)" />

              {/* Horizontal bandwidth interval lines */}
              {bandwidthIntervals.slice(1, -1).map((bandwidth, index) => {
                const y = ((maxBandwidth - bandwidth) / maxBandwidth) * 85 + 5 // 5% top margin, 10% bottom margin
                return (
                  <line
                    key={index}
                    x1="0"
                    y1={y}
                    x2="100"
                    y2={y}
                    stroke="currentColor"
                    strokeWidth="0.3"
                    strokeDasharray="2,2"
                    className="text-slate-400 dark:text-slate-500"
                    opacity="0.5"
                  />
                )
              })}

              {/* Time interval markers */}
              {bandwidthHistory.map((point, index) => {
                if (index % 4 === 0 || index === bandwidthHistory.length - 1) { // Show every 4th marker (1 minute intervals)
                  const x = (index / (bandwidthHistory.length - 1)) * 100
                  return (
                    <line
                      key={index}
                      x1={x}
                      y1="90"
                      x2={x}
                      y2="95"
                      stroke="currentColor"
                      strokeWidth="0.5"
                      className="text-slate-400 dark:text-slate-500"
                    />
                  )
                }
                return null
              })}

              {/* Total bandwidth line */}
              <polyline
                fill="none"
                stroke="#FFFFFF"
                strokeWidth="3"
                vectorEffect="non-scaling-stroke"
                points={bandwidthHistory.map((point, index) => {
                  const x = (index / (bandwidthHistory.length - 1)) * 100
                  const y = 95 - (point.totalBandwidth / maxBandwidth) * 85 // Use 85% with margins
                  return `${x},${y}`
                }).join(' ')}
              />

              {/* Individual server lines */}
              {Object.keys(serverColors).map(serverName => (
                <polyline
                  key={serverName}
                  fill="none"
                  stroke={serverColors[serverName]}
                  strokeWidth="1.5"
                  vectorEffect="non-scaling-stroke"
                  opacity="0.7"
                  points={bandwidthHistory.map((point, index) => {
                    const x = (index / (bandwidthHistory.length - 1)) * 100
                    const y = 95 - ((point.serverBandwidths[serverName] || 0) / maxBandwidth) * 85
                    return `${x},${y}`
                  }).join(' ')}
                />
              ))}
            </svg>
          </div>

          {/* Y-axis labels on the right */}
          <div className="absolute right-2 top-2 bottom-2 flex flex-col justify-between text-xs text-slate-500 dark:text-slate-400">
            {bandwidthIntervals.map((bandwidth, index) => (
              <span key={index} className="leading-none">
                {formatBitrate(bandwidth)}
              </span>
            ))}
          </div>
        </div>

        {/* Time labels below graph */}
        <div className="relative h-4 mb-2">
          <div className="absolute inset-x-2 flex justify-between text-xs text-slate-500 dark:text-slate-400">
            {bandwidthHistory.map((point, index) => {
              if (index % 4 === 0 || index === bandwidthHistory.length - 1) { // Show every 4th label
                const position = (index / (bandwidthHistory.length - 1)) * 100
                return (
                  <span
                    key={index}
                    className="absolute transform -translate-x-1/2"
                    style={{ left: `${position}%` }}
                  >
                    {formatTime(point.timestamp)}
                  </span>
                )
              }
              return null
            })}
          </div>
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
              const bandwidth = bandwidthHistory[bandwidthHistory.length - 1]?.serverBandwidths[serverName] || 0
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
    <div className="px-4 py-6 sm:px-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Admin Dashboard
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          Monitor active sessions and view analytics across all media servers
        </p>
      </div>

      {/* Active Sessions Section */}
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

        {sessionsLoading ? (
          <div className="card">
            <div className="card-body">
              <p className="text-slate-600 dark:text-slate-400">Loading active sessions...</p>
            </div>
          </div>
        ) : sessions.length === 0 ? (
          <div className="card">
            <div className="card-body text-center">
              <DevicePhoneMobileIcon className="w-12 h-12 mx-auto text-slate-400 mb-3" />
              <p className="text-slate-600 dark:text-slate-400">No active playback sessions</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {groupedSessions.map(({ serverType, servers }) => {
              const allServerTypeSessions = servers.flatMap(server => server.sessions)
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
                              <span className="text-xl">{getServerTypeIcon(serverType)}</span>
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
                                                  <button
                                                    onClick={() => terminateSessionMutation.mutate({
                                                      serverId: session.server_id!,
                                                      sessionId: session.session_id
                                                    })}
                                                    disabled={terminateSessionMutation.isLoading}
                                                    className="p-1 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                                                    title="Terminate Session"
                                                  >
                                                    <XMarkIcon className="w-3 h-3" />
                                                  </button>
                                                </div>

                                                <div className="space-y-2 text-xs text-slate-600 dark:text-slate-400">
                                                  <div className="flex justify-between">
                                                    <span>Username:</span>
                                                    <span className="font-medium text-slate-900 dark:text-white">{session.username || 'Unknown'}</span>
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
                                                        <span className="text-orange-500 ml-1">• Transcoding</span>
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
                                                    <span>{session.progress_percent.toFixed(1)}%</span>
                                                    <span>{formatTime(session.duration_ms)}</span>
                                                  </div>
                                                  <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                                                    <div
                                                      className={`h-2 rounded-full transition-all duration-300 ${getProgressBarColor(session.state)}`}
                                                      style={{ width: `${Math.min(100, Math.max(0, session.progress_percent))}%` }}
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

      {/* Analytics Section */}
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
                      {analytics?.completion_rate.toFixed(1) || 0}%
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">Completion Rate</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                      {analytics?.transcode_rate.toFixed(1) || 0}%
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
                        <span className="text-slate-900 dark:text-white">{user.username}</span>
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
                        <div className="text-xs text-slate-500">{device.total_sessions} sessions • {device.transcode_percentage.toFixed(1)}% transcode</div>
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
    </div>
  )
}