import React, { useState } from 'react'
import { useQuery } from 'react-query'
import { useParams, useNavigate } from 'react-router-dom'
import {
  MagnifyingGlassIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowLeftIcon,
  PlayIcon,
  DevicePhoneMobileIcon,
  FilmIcon,
  TvIcon
} from '@heroicons/react/24/outline'
import { api } from '../../services/api'

interface WatchHistoryItem {
  id: number
  server_name: string
  media_title: string
  media_type: string
  grandparent_title?: string
  parent_title?: string
  season_number?: number
  episode_number?: number
  year?: string
  device?: string
  platform?: string
  product?: string
  video_decision?: string
  original_resolution?: string
  original_bitrate?: string
  video_codec?: string
  is_4k: boolean
  is_hdr: boolean
  is_dolby_vision: boolean
  progress_percent: number
  duration_ms: number
  progress_ms: number
  started_at: string
  ended_at?: string
}

interface WatchHistorySummary {
  total_streams: number
  total_watch_time_ms: number
  completion_rate: number
  transcode_rate: number
}

interface WatchHistoryResponse {
  items: WatchHistoryItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
  summary: WatchHistorySummary
}

export default function WatchHistory() {
  const { userId } = useParams<{ userId: string }>()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [serverId, setServerId] = useState<number | undefined>()
  const [daysBack, setDaysBack] = useState(365)
  const pageSize = 50

  // Get watch history
  const { data: history, isLoading } = useQuery<WatchHistoryResponse>(
    ['watch-history', userId, page, search, serverId, daysBack],
    () => {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
        days_back: daysBack.toString()
      })
      if (search) params.append('search', search)
      if (serverId) params.append('server_id', serverId.toString())

      return api.get(`/admin/users/${userId}/watch-history?${params}`).then(res => res.data)
    },
    {
      enabled: !!userId,
      keepPreviousData: true
    }
  )

  // Get servers for filter dropdown
  const { data: servers = [] } = useQuery(
    'servers',
    () => api.get('/admin/servers').then(res => res.data)
  )

  const formatTitle = (item: WatchHistoryItem) => {
    if (item.media_type === 'episode' && item.grandparent_title) {
      return (
        <div>
          <div className="font-medium text-slate-900 dark:text-white">
            {item.media_title}
          </div>
          <div className="text-sm text-slate-600 dark:text-slate-400">
            {item.grandparent_title}
            {item.parent_title && ` - ${item.parent_title}`}
            {item.episode_number && ` - Episode ${item.episode_number}`}
          </div>
        </div>
      )
    }
    return (
      <div>
        <div className="font-medium text-slate-900 dark:text-white">{item.media_title}</div>
        {item.year && <div className="text-sm text-slate-600 dark:text-slate-400">{item.year}</div>}
      </div>
    )
  }

  const formatResolution = (item: WatchHistoryItem) => {
    const badges = []
    if (item.is_4k) badges.push('4K')
    if (item.is_dolby_vision) badges.push('DV')
    else if (item.is_hdr) badges.push('HDR')

    return (
      <div className="space-y-1">
        <div className="text-slate-900 dark:text-white">{item.original_resolution || 'Unknown'}</div>
        <div className="flex gap-1 flex-wrap">
          {badges.map(badge => (
            <span
              key={badge}
              className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200"
            >
              {badge}
            </span>
          ))}
        </div>
      </div>
    )
  }

  const formatBitrate = (bitrate?: string) => {
    if (!bitrate) return 'Unknown'
    const kbps = parseInt(bitrate)
    if (kbps >= 1000) {
      return `${(kbps / 1000).toFixed(1)} Mbps`
    }
    return `${kbps} Kbps`
  }

  const formatPlayState = (decision?: string) => {
    const stateMap: Record<string, { label: string; color: string }> = {
      'directplay': { label: 'Direct Play', color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' },
      'copy': { label: 'Direct Stream', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' },
      'transcode': { label: 'Transcode', color: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200' },
      'unknown': { label: 'Unknown', color: 'bg-slate-100 text-slate-800 dark:bg-slate-900 dark:text-slate-200' }
    }
    const state = stateMap[decision || 'unknown'] || stateMap.unknown
    return (
      <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${state.color}`}>
        {state.label}
      </span>
    )
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const options: Intl.DateTimeFormatOptions = {
      timeZone: 'America/Chicago',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    }
    const formatted = date.toLocaleString('en-US', options)
    return `${formatted} GMT-6`
  }

  const formatStartTime = (dateString: string) => {
    const date = new Date(dateString)
    // Format in CST (America/Chicago timezone)
    const options: Intl.DateTimeFormatOptions = {
      timeZone: 'America/Chicago',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    }
    const formatted = date.toLocaleString('en-US', options)
    return `${formatted} GMT-6`
  }

  const formatWatchTime = (ms: number) => {
    const totalMinutes = Math.floor(ms / 60000)
    const totalHours = Math.floor(totalMinutes / 60)
    const totalDays = Math.floor(totalHours / 24)
    const totalMonths = Math.floor(totalDays / 30)
    const totalYears = Math.floor(totalDays / 365)

    const parts = []

    if (totalYears > 0) {
      const remainingDays = totalDays % 365
      const remainingMonths = Math.floor(remainingDays / 30)
      const remainingDaysInMonth = remainingDays % 30
      const remainingHours = totalHours % 24

      parts.push(`${totalYears}y`)
      if (remainingMonths > 0) parts.push(`${remainingMonths}mo`)
      if (remainingDaysInMonth > 0) parts.push(`${remainingDaysInMonth}d`)
      if (remainingHours > 0) parts.push(`${remainingHours}h`)
    } else if (totalMonths > 0) {
      const remainingDays = totalDays % 30
      const remainingHours = totalHours % 24

      parts.push(`${totalMonths}mo`)
      if (remainingDays > 0) parts.push(`${remainingDays}d`)
      if (remainingHours > 0) parts.push(`${remainingHours}h`)
    } else if (totalDays > 0) {
      const remainingHours = totalHours % 24

      parts.push(`${totalDays}d`)
      if (remainingHours > 0) parts.push(`${remainingHours}h`)
    } else if (totalHours > 0) {
      const remainingMinutes = totalMinutes % 60

      parts.push(`${totalHours}h`)
      if (remainingMinutes > 0) parts.push(`${remainingMinutes}m`)
    } else {
      parts.push(`${totalMinutes}m`)
    }

    return parts.join(' ')
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 -mx-6 -my-6 px-6 py-6">
      <div className="w-full px-4">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/admin/management')}
            className="mb-4 inline-flex items-center text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          >
            <ArrowLeftIcon className="h-4 w-4 mr-2" />
            Back to Users
          </button>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Watch History</h1>
          <p className="mt-2 text-slate-600 dark:text-slate-400">
            Viewing history for user {userId}
          </p>
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label htmlFor="search" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Search
              </label>
              <div className="relative">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-slate-400" />
                <input
                  id="search"
                  type="text"
                  placeholder="Search by title, device, etc."
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value)
                    setPage(1)
                  }}
                  className="w-full pl-10 pr-4 py-2 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white placeholder-slate-400"
                />
              </div>
            </div>

            <div>
              <label htmlFor="server" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Server
              </label>
              <select
                id="server"
                value={serverId || ''}
                onChange={(e) => {
                  setServerId(e.target.value ? parseInt(e.target.value) : undefined)
                  setPage(1)
                }}
                className="w-full px-4 py-2 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white"
              >
                <option value="">All Servers</option>
                {servers.map((server: any) => (
                  <option key={server.id} value={server.id}>
                    {server.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="days" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Time Period
              </label>
              <select
                id="days"
                value={daysBack}
                onChange={(e) => {
                  setDaysBack(parseInt(e.target.value))
                  setPage(1)
                }}
                className="w-full px-4 py-2 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white"
              >
                <option value={7}>Last 7 Days</option>
                <option value={30}>Last 30 Days</option>
                <option value={90}>Last 90 Days</option>
                <option value={180}>Last 180 Days</option>
                <option value={365}>Last 365 Days</option>
              </select>
            </div>
          </div>
        </div>

        {/* Overview Section */}
        {!isLoading && history && (
          <div className="mb-6 grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-600 dark:text-slate-400">Total Streams</p>
                  <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">
                    {history.summary.total_streams.toLocaleString()}
                  </p>
                </div>
                <PlayIcon className="h-12 w-12 text-blue-500" />
              </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-600 dark:text-slate-400">Watch Time</p>
                  <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">
                    {formatWatchTime(history.summary.total_watch_time_ms)}
                  </p>
                </div>
                <PlayIcon className="h-12 w-12 text-green-500" />
              </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-600 dark:text-slate-400">Completion Rate</p>
                  <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">
                    {history.summary.completion_rate.toFixed(1)}%
                  </p>
                </div>
                <PlayIcon className="h-12 w-12 text-purple-500" />
              </div>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-600 dark:text-slate-400">Transcode Rate</p>
                  <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">
                    {history.summary.transcode_rate.toFixed(1)}%
                  </p>
                </div>
                <PlayIcon className="h-12 w-12 text-orange-500" />
              </div>
            </div>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            <p className="mt-4 text-slate-600 dark:text-slate-400">Loading watch history...</p>
          </div>
        )}

        {/* Results */}
        {!isLoading && history && (
          <>
            {/* Results Info */}
            <div className="mb-4 text-sm text-slate-600 dark:text-slate-400">
              Showing {history.items.length > 0 ? ((page - 1) * pageSize + 1) : 0} - {Math.min(page * pageSize, history.total)} of {history.total} results
            </div>

            {/* Table */}
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow">
              <div className="overflow-x-auto">
                <table className="w-full divide-y divide-slate-200 dark:divide-slate-700" style={{ tableLayout: 'auto', minWidth: '100%' }}>
                  <thead className="bg-slate-50 dark:bg-slate-900">
                    <tr>
                      <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">
                        Title
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">
                        Server
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">
                        Resolution
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">
                        Bitrate
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">
                        Play State
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">
                        Completion
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">
                        Device
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">
                        Started At
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-slate-800 divide-y divide-slate-200 dark:divide-slate-700">
                    {history.items.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="px-6 py-12 text-center text-slate-500 dark:text-slate-400">
                          No watch history found
                        </td>
                      </tr>
                    ) : (
                      history.items.map((item) => (
                        <tr key={item.id} className="hover:bg-slate-50 dark:hover:bg-slate-700">
                          <td className="px-3 py-4 whitespace-nowrap">
                            <div className="flex items-center">
                              {item.media_type === 'episode' ? (
                                <TvIcon className="h-5 w-5 text-slate-400 mr-2 flex-shrink-0" />
                              ) : (
                                <FilmIcon className="h-5 w-5 text-slate-400 mr-2 flex-shrink-0" />
                              )}
                              <div>
                                {formatTitle(item)}
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-4 text-sm text-slate-900 dark:text-white whitespace-nowrap">
                            {item.server_name}
                          </td>
                          <td className="px-3 py-4 text-sm whitespace-nowrap">
                            {formatResolution(item)}
                          </td>
                          <td className="px-3 py-4 text-sm text-slate-900 dark:text-white whitespace-nowrap">
                            {formatBitrate(item.original_bitrate)}
                          </td>
                          <td className="px-3 py-4 text-sm whitespace-nowrap">
                            {formatPlayState(item.video_decision)}
                          </td>
                          <td className="px-3 py-4 whitespace-nowrap">
                            <div className="flex items-center">
                              <div className="w-20 bg-slate-200 dark:bg-slate-700 rounded-full h-2 mr-2">
                                <div
                                  className="bg-blue-500 h-2 rounded-full"
                                  style={{ width: `${Math.min(100, item.progress_percent)}%` }}
                                />
                              </div>
                              <span className="text-sm text-slate-900 dark:text-white whitespace-nowrap">
                                {Math.round(item.progress_percent)}%
                              </span>
                            </div>
                          </td>
                          <td className="px-3 py-4 whitespace-nowrap">
                            <div className="flex items-start text-sm text-slate-900 dark:text-white">
                              <DevicePhoneMobileIcon className="h-4 w-4 text-slate-400 mr-2 mt-0.5 flex-shrink-0" />
                              <div>
                                <div>{item.device || 'Unknown'}</div>
                                {item.platform && (
                                  <div className="text-xs text-slate-500 dark:text-slate-400">{item.platform}</div>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-4 text-sm text-slate-900 dark:text-white whitespace-nowrap">
                            {formatDate(item.started_at)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Pagination */}
            {history.total_pages > 1 && (
              <div className="mt-6 flex items-center justify-between">
                <div className="text-sm text-slate-600 dark:text-slate-400">
                  Page {page} of {history.total_pages}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="inline-flex items-center px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeftIcon className="h-4 w-4 mr-1" />
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(p => Math.min(history.total_pages, p + 1))}
                    disabled={page === history.total_pages}
                    className="inline-flex items-center px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                    <ChevronRightIcon className="h-4 w-4 ml-1" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
