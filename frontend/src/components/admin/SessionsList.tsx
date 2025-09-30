import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import {
  PlayIcon,
  PauseIcon,
  StopIcon,
  ClockIcon,
  DevicePhoneMobileIcon,
  EyeIcon,
  SignalIcon,
  FilmIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CpuChipIcon,
  ComputerDesktopIcon
} from '@heroicons/react/24/outline'
import { Disclosure, Transition } from '@headlessui/react'
import toast from 'react-hot-toast'
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
  original_resolution?: string
  stream_resolution?: string
  original_bitrate?: string
  stream_bitrate?: string
  session_bandwidth?: string
  session_location?: string
  video_codec?: string
  audio_codec?: string
  audio_channels?: string
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

export default function SessionsList() {
  const [refreshInterval] = useState(5000) // 5 seconds
  const queryClient = useQueryClient()

  const { data: sessions = [], isLoading, error } = useQuery<LiveSession[]>(
    'admin-sessions',
    () => api.get('/admin/sessions').then(res => res.data),
    {
      refetchInterval: refreshInterval,
      refetchIntervalInBackground: true
    }
  )

  const terminateSessionMutation = useMutation(
    ({ serverId, sessionId }: { serverId: number, sessionId: string }) => {
      console.log('SESSIONS LIST - Terminating session:', { serverId, sessionId })
      return api.post(`/admin/servers/${serverId}/sessions/${sessionId}/terminate`)
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries('admin-sessions')
        toast.success('Session terminated successfully')
      },
      onError: (error: any) => {
        console.error('SESSIONS LIST - Termination error:', error)
        toast.error(error.response?.data?.detail || 'Failed to terminate session')
      }
    }
  )

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`
  }

  const formatBitrate = (bitrate?: string) => {
    if (!bitrate) return 'Unknown'
    const kbps = parseInt(bitrate)
    if (kbps >= 1000) {
      return `${(kbps / 1000).toFixed(1)} Mbps`
    }
    return `${kbps} kbps`
  }

  const getStateIcon = (state: string) => {
    switch (state) {
      case 'playing':
        return <PlayIcon className="h-5 w-5 text-green-500" />
      case 'paused':
        return <PauseIcon className="h-5 w-5 text-yellow-500" />
      default:
        return <StopIcon className="h-5 w-5 text-slate-500" />
    }
  }

  const getStateColor = (state: string) => {
    switch (state) {
      case 'playing':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'paused':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
      default:
        return 'bg-slate-100 text-slate-800 dark:bg-slate-900 dark:text-slate-200'
    }
  }

  const getTranscodeInfo = (session: LiveSession) => {
    if (session.video_decision === 'directplay') {
      return {
        text: 'Direct Play',
        color: 'text-green-600 dark:text-green-400',
        icon: null,
        details: null
      }
    } else if (session.video_decision === 'copy') {
      return {
        text: 'Direct Stream',
        color: 'text-blue-600 dark:text-blue-400',
        icon: null,
        details: null
      }
    } else if (session.video_decision === 'transcode') {
      // For Emby and Jellyfin, just show "Transcode" without HW/SW details
      if (session.server_type === 'emby' || session.server_type === 'jellyfin') {
        let details = []

        // Add speed if available
        if (session.transcode_speed) {
          details.push(`${session.transcode_speed.toFixed(1)}x`)
        }

        return {
          text: 'Transcode',
          color: 'text-orange-600 dark:text-orange-400',
          icon: ComputerDesktopIcon,
          details: details.length > 0 ? details : null
        }
      }

      // For Plex, check for hardware transcoding
      const isHwDecode = session.transcode_hw_decode === true || !!session.transcode_hw_decode_title
      const isHwEncode = session.transcode_hw_encode === true || !!session.transcode_hw_encode_title
      const isFullHw = session.transcode_hw_full_pipeline === true

      let transcodeType = 'Software'
      let icon = ComputerDesktopIcon
      let color = 'text-orange-600 dark:text-orange-400'
      let details = []

      if (isFullHw || (isHwDecode && isHwEncode)) {
        transcodeType = 'Hardware'
        icon = CpuChipIcon
        color = 'text-purple-600 dark:text-purple-400'
        details.push('Full HW')
      } else if (isHwDecode || isHwEncode) {
        transcodeType = 'Hybrid'
        icon = CpuChipIcon
        color = 'text-indigo-600 dark:text-indigo-400'
        if (isHwDecode) details.push('HW Decode')
        if (isHwEncode) details.push('HW Encode')
      }

      // Add GPU info if available
      if (session.transcode_hw_decode_title) {
        details.push(session.transcode_hw_decode_title)
      } else if (session.transcode_hw_encode_title) {
        details.push(session.transcode_hw_encode_title)
      }

      // Add speed if available
      if (session.transcode_speed) {
        details.push(`${session.transcode_speed.toFixed(1)}x`)
      }

      return {
        text: `${transcodeType} Transcode`,
        color,
        icon,
        details: details.length > 0 ? details.join(' • ') : null,
        isThrottled: session.transcode_throttled
      }
    }
    return {
      text: 'Unknown',
      color: 'text-slate-600 dark:text-slate-400',
      icon: null,
      details: null
    }
  }

  const getServerTypeColor = (serverType?: string) => {
    switch (serverType?.toLowerCase()) {
      case 'plex':
        return 'text-orange-600 dark:text-orange-400'
      case 'emby':
        return 'text-green-600 dark:text-green-400'
      case 'jellyfin':
        return 'text-blue-600 dark:text-blue-400'
      default:
        return 'text-slate-600 dark:text-slate-400'
    }
  }

  const getServerTypeIcon = (serverType?: string) => {
    // Return appropriate icon image for server type
    switch (serverType?.toLowerCase()) {
      case 'plex':
        return (
          <img
            src="/plex.png"
            alt="Plex"
            className="h-8 w-8"
            style={{ backgroundColor: 'transparent' }}
          />
        )
      case 'emby':
        return (
          <img
            src="/emby.png"
            alt="Emby"
            className="h-8 w-8"
            style={{ backgroundColor: 'transparent' }}
          />
        )
      case 'jellyfin':
        return (
          <img
            src="/jellyfin.png"
            alt="Jellyfin"
            className="h-8 w-8"
            style={{ backgroundColor: 'transparent' }}
          />
        )
      default:
        return <span className="text-2xl">⚪</span> // Unknown = Gray emoji
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

    // Debug: Log all sessions with their server info
    console.log('SESSIONS PAGE - All sessions received:', sessions.length)

    // Group sessions by server for debugging
    const sessionsByServer: Record<string, any[]> = {}
    sessions.forEach((session) => {
      const key = `${session.server_name} (ID: ${session.server_id}, Type: ${session.server_type})`
      if (!sessionsByServer[key]) {
        sessionsByServer[key] = []
      }
      sessionsByServer[key].push({
        username: session.username,
        server_id: session.server_id,
        media_title: session.title || session.full_title
      })
    })

    // Log grouped sessions
    Object.entries(sessionsByServer).forEach(([server, serverSessions]) => {
      console.log(`SESSIONS PAGE - ${server}: ${serverSessions.length} sessions`)
      serverSessions.forEach((s, idx) => {
        console.log(`  ${idx + 1}. User: ${s.username}, Media: ${s.media_title}`)
      })
    })

    // Special logging for The Tower #1
    const towerSessions = sessions.filter(s => s.server_name?.toLowerCase() === 'the tower #1')
    if (towerSessions.length > 0) {
      console.log('=== The Tower #1 Sessions ===')
      towerSessions.forEach(s => {
        console.log(`  Server ID: ${s.server_id}, Type from API: "${s.server_type}", User: ${s.username}`)
      })
    }

    const grouped = sessions.reduce((acc, session) => {
      // Debug: Log first few sessions to understand structure
      if (sessions.indexOf(session) < 3) {
        console.log(`Session ${sessions.indexOf(session)} raw data:`, {
          server_type: session.server_type,
          server_name: session.server_name,
          server_id: session.server_id,
          all_keys: Object.keys(session).filter(k => k.includes('server')).join(', ')
        })
      }

      // Get server type from API field
      let serverType = session.server_type || ''

      if (serverType) {
        // Normalize the server type
        serverType = String(serverType).toLowerCase().trim()
      }

      // If no server type or it's invalid, infer from name
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
          console.warn(`Could not determine type for server: "${session.server_name}" (server_type field: "${session.server_type}")`)
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

  if (isLoading) {
    return (
      <div className="px-4 py-6 sm:px-6">
        <div className="flex justify-center py-8">
          <div className="text-slate-600 dark:text-slate-400">Loading sessions...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 py-6 sm:px-6">
        <div className="text-center py-8">
          <div className="text-red-600 dark:text-red-400">Failed to load sessions</div>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4 py-6 sm:px-6">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Active Sessions
          </h1>
          <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
            Monitor and manage active playback sessions across all servers
          </p>
        </div>
        <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
          <div className="text-sm text-slate-600 dark:text-slate-400">
            Auto-refresh every {refreshInterval / 1000}s
          </div>
        </div>
      </div>

      {sessions.length === 0 ? (
        <div className="mt-8 card">
          <div className="card-body text-center py-12">
            <FilmIcon className="mx-auto h-12 w-12 text-slate-400" />
            <h3 className="mt-2 text-sm font-medium text-slate-900 dark:text-white">No active sessions</h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              No one is currently watching anything on your servers.
            </p>
          </div>
        </div>
      ) : (
        <div className="mt-8 space-y-6">
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
                          <div className="flex items-center space-x-4">
                            <div className="flex items-center">
                              {open ? (
                                <ChevronDownIcon className="h-5 w-5 text-slate-500" />
                              ) : (
                                <ChevronRightIcon className="h-5 w-5 text-slate-500" />
                              )}
                              <div className="ml-2">{getServerTypeIcon(serverType)}</div>
                              <h2 className="ml-2 text-xl font-bold text-slate-900 dark:text-white">
                                {getServerTypeName(serverType)}
                              </h2>
                            </div>
                            <div className="flex items-center space-x-6 text-sm">
                              <div className="flex items-center">
                                <PlayIcon className="h-4 w-4 text-slate-400 mr-1" />
                                <span className="font-medium text-slate-900 dark:text-white">
                                  {serverTypeStats.totalStreams}
                                </span>
                                <span className="text-slate-500 dark:text-slate-400 ml-1">streams</span>
                              </div>
                              <div className="flex items-center">
                                <SignalIcon className="h-4 w-4 text-orange-500 mr-1" />
                                <span className="font-medium text-slate-900 dark:text-white">
                                  {serverTypeStats.transcodes}
                                </span>
                                <span className="text-slate-500 dark:text-slate-400 ml-1">transcoding</span>
                              </div>
                              <div className="flex items-center">
                                <ClockIcon className="h-4 w-4 text-slate-400 mr-1" />
                                <span className="font-medium text-slate-900 dark:text-white">
                                  {formatBitrate(serverTypeStats.totalBandwidth.toString())}
                                </span>
                                <span className="text-slate-500 dark:text-slate-400 ml-1">total</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </Disclosure.Button>

                    <Transition
                      show={open}
                      enter="transition duration-200 ease-out"
                      enterFrom="transform scale-95 opacity-0"
                      enterTo="transform scale-100 opacity-100"
                      leave="transition duration-75 ease-out"
                      leaveFrom="transform scale-100 opacity-100"
                      leaveTo="transform scale-95 opacity-0"
                    >
                      <Disclosure.Panel>
                        <div className="space-y-4 px-6 pb-6">
                          {servers.map(({ serverName, sessions: serverSessions }) => {
                            const serverStats = calculateStats(serverSessions)

                            return (
                              <Disclosure key={`${serverType}-${serverName}`} defaultOpen={true}>
                                {({ open: serverOpen }) => (
                                  <div className="border border-slate-200 dark:border-slate-700 rounded-lg">
                                    <Disclosure.Button className="w-full">
                                      <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-t-lg">
                                        <div className="flex items-center justify-between">
                                          <div className="flex items-center space-x-3">
                                            {serverOpen ? (
                                              <ChevronDownIcon className="h-4 w-4 text-slate-500" />
                                            ) : (
                                              <ChevronRightIcon className="h-4 w-4 text-slate-500" />
                                            )}
                                            <h3 className={`text-lg font-semibold ${getServerTypeColor(serverType)}`}>
                                              {serverName}
                                            </h3>
                                          </div>
                                          <div className="flex items-center space-x-4 text-xs">
                                            <div className="flex items-center">
                                              <PlayIcon className="h-3 w-3 text-slate-400 mr-1" />
                                              <span className="font-medium">{serverStats.totalStreams}</span>
                                            </div>
                                            <div className="flex items-center">
                                              <SignalIcon className="h-3 w-3 text-orange-500 mr-1" />
                                              <span className="font-medium">{serverStats.transcodes}</span>
                                            </div>
                                            <div className="flex items-center">
                                              <span className="font-medium text-green-600 dark:text-green-400">{serverStats.directPlay + serverStats.directStream}</span>
                                              <span className="text-slate-500 ml-1">direct</span>
                                            </div>
                                            <div className="flex items-center">
                                              <span className="font-medium">{formatBitrate(serverStats.totalBandwidth.toString())}</span>
                                            </div>
                                          </div>
                                        </div>
                                      </div>
                                    </Disclosure.Button>

                                    <Transition
                                      show={serverOpen}
                                      enter="transition duration-150 ease-out"
                                      enterFrom="transform scale-95 opacity-0"
                                      enterTo="transform scale-100 opacity-100"
                                      leave="transition duration-75 ease-out"
                                      leaveFrom="transform scale-100 opacity-100"
                                      leaveTo="transform scale-95 opacity-0"
                                    >
                                      <Disclosure.Panel>
                                        <div className="space-y-4 p-4">
                                          {serverSessions.map((session) => {
                                            const transcodeInfo = getTranscodeInfo(session)

                                            return (
                                              <div key={`${session.server_id}-${session.session_id}`} className="border border-slate-100 dark:border-slate-700 rounded-lg p-4">
                                                <div className="flex items-start justify-between">
                                                  <div className="flex-1 min-w-0">
                                                    {/* Media Title and Info */}
                                                    <div className="flex items-center mb-2">
                                                      {getStateIcon(session.state)}
                                                      <h4 className="ml-2 text-lg font-medium text-slate-900 dark:text-white truncate">
                                                        {session.full_title || session.title || 'Unknown Media'}
                                                      </h4>
                                                      <span className={`ml-3 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStateColor(session.state)}`}>
                                                        {session.state}
                                                      </span>
                                                    </div>

                                                    {/* Progress Bar */}
                                                    <div className="mb-4">
                                                      <div className="flex items-center justify-between text-sm text-slate-600 dark:text-slate-400 mb-1">
                                                        <span>{formatDuration(session.progress_seconds)} / {formatDuration(session.duration_seconds)}</span>
                                                        <span>{session.progress_percent.toFixed(1)}%</span>
                                                      </div>
                                                      <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                                                        <div
                                                          className="bg-primary-600 h-2 rounded-full transition-all duration-500"
                                                          style={{ width: `${Math.min(session.progress_percent, 100)}%` }}
                                                        />
                                                      </div>
                                                    </div>

                                                    {/* User and Device Info */}
                                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                                                      <div className="flex items-center">
                                                        <EyeIcon className="h-4 w-4 text-slate-400 mr-2" />
                                                        <div>
                                                          <div className="text-sm font-medium text-slate-900 dark:text-white">
                                                            {session.username || 'Unknown User'}
                                                          </div>
                                                          <div className="text-xs text-slate-500 dark:text-slate-400">User</div>
                                                        </div>
                                                      </div>

                                                      <div className="flex items-center">
                                                        <DevicePhoneMobileIcon className="h-4 w-4 text-slate-400 mr-2" />
                                                        <div>
                                                          <div className="text-sm font-medium text-slate-900 dark:text-white">
                                                            {session.device || 'Unknown Device'}
                                                          </div>
                                                          <div className="text-xs text-slate-500 dark:text-slate-400">
                                                            {session.product} • {session.location}
                                                          </div>
                                                        </div>
                                                      </div>

                                                      <div className="flex items-center">
                                                        {transcodeInfo.icon ? (
                                                          <transcodeInfo.icon className={`h-4 w-4 mr-2 ${transcodeInfo.color}`} />
                                                        ) : (
                                                          <SignalIcon className="h-4 w-4 text-slate-400 mr-2" />
                                                        )}
                                                        <div>
                                                          <div className="flex items-center gap-2">
                                                            <span className={`text-sm font-medium ${transcodeInfo.color}`}>
                                                              {transcodeInfo.text}
                                                            </span>
                                                            {transcodeInfo.isThrottled && (
                                                              <span className="text-xs px-1 py-0.5 bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 rounded">
                                                                Throttled
                                                              </span>
                                                            )}
                                                          </div>
                                                          <div className="text-xs text-slate-500 dark:text-slate-400">
                                                            {transcodeInfo.details || session.quality_profile || 'Unknown Quality'}
                                                          </div>
                                                        </div>
                                                      </div>

                                                      <div className="flex items-center">
                                                        <ClockIcon className="h-4 w-4 text-slate-400 mr-2" />
                                                        <div>
                                                          <div className="text-sm font-medium text-slate-900 dark:text-white">
                                                            {formatBitrate(session.original_bitrate)}
                                                          </div>
                                                          <div className="text-xs text-slate-500 dark:text-slate-400">
                                                            {session.container?.toUpperCase()} • {session.video_codec?.toUpperCase()}
                                                          </div>
                                                        </div>
                                                      </div>
                                                    </div>

                                                    {/* Technical Details */}
                                                    <details className="mb-4">
                                                      <summary className="cursor-pointer text-sm text-primary-600 dark:text-primary-400 hover:text-primary-800 dark:hover:text-primary-200">
                                                        Show technical details
                                                      </summary>
                                                      <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                                        <div>
                                                          <span className="font-medium">Resolution:</span> {
                                                            session.video_decision === 'transcode' && session.stream_resolution
                                                              ? `${session.original_resolution} → ${session.stream_resolution}`
                                                              : session.original_resolution
                                                          }
                                                        </div>
                                                        <div>
                                                          <span className="font-medium">Video:</span> {session.video_codec} {session.video_profile}
                                                        </div>
                                                        <div>
                                                          <span className="font-medium">Audio:</span> {session.audio_codec} {session.audio_channels}ch
                                                        </div>
                                                        <div>
                                                          <span className="font-medium">Bandwidth:</span> {formatBitrate(session.session_bandwidth)}
                                                        </div>
                                                        {session.is_hdr && (
                                                          <div>
                                                            <span className="font-medium">HDR:</span> {session.is_dolby_vision ? 'Dolby Vision' : 'HDR10'}
                                                          </div>
                                                        )}
                                                      </div>
                                                    </details>
                                                  </div>

                                                  {/* Actions */}
                                                  <div className="ml-4 flex-shrink-0">
                                                    <button
                                                      onClick={() => {
                                                        console.log('TERMINATE BUTTON CLICKED - Session data:', {
                                                          server_id: session.server_id,
                                                          session_id: session.session_id,
                                                          server_name: session.server_name,
                                                          server_type: session.server_type,
                                                          username: session.username
                                                        })
                                                        if (confirm(`Terminate ${session.username}'s session?`)) {
                                                          console.log('CONFIRMED - Calling terminate mutation')
                                                          terminateSessionMutation.mutate({
                                                            serverId: session.server_id!,
                                                            sessionId: session.session_id
                                                          })
                                                        } else {
                                                          console.log('CANCELLED - User cancelled termination')
                                                        }
                                                      }}
                                                      disabled={terminateSessionMutation.isLoading}
                                                      className="btn-danger"
                                                    >
                                                      {terminateSessionMutation.isLoading ? 'Terminating...' : 'Terminate'}
                                                    </button>
                                                  </div>
                                                </div>
                                              </div>
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
  )
}