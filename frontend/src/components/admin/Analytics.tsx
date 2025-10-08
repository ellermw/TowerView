import React from 'react'
import { useQuery } from 'react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../../services/api'

interface DashboardAnalytics {
  total_sessions: number
  total_users: number
  total_watch_time_hours: number
  completion_rate: number
  video_transcode_rate: number
  audio_transcode_rate: number
  top_users: Array<{
    username: string
    provider_user_id: string
    server_name: string
    total_plays: number
    total_watch_time_minutes: number
    completion_rate: number
  }>
  top_movies: Array<{
    title: string
    year: string
    server_name: string
    total_plays: number
    unique_users: number
  }>
  top_tv_shows: Array<{
    title: string
    year: string
    server_name: string
    total_plays: number
    unique_users: number
  }>
  top_libraries: Array<{
    library_name: string
    server_name: string
    total_plays: number
    unique_users: number
  }>
  top_devices: Array<{
    device_name: string
    platform: string
    total_plays: number
  }>
  top_clients: Array<{
    client_name: string
    platform: string
    total_plays: number
  }>
}

export default function Analytics() {
  const navigate = useNavigate()
  const [filters, setFilters] = React.useState({
    server_id: undefined as number | undefined,
    days_back: 7
  })
  const [selectedCategory, setSelectedCategory] = React.useState<string>('users')

  // Get analytics data
  const { data: analytics, isLoading } = useQuery<DashboardAnalytics>(
    ['analytics-page', filters],
    () => api.post('/admin/analytics', filters).then(res => {
      console.log('Analytics data received:', res.data)
      console.log('Top movies count:', res.data.top_movies?.length)
      console.log('First movie:', res.data.top_movies?.[0])
      console.log('Top shows count:', res.data.top_tv_shows?.length)
      console.log('First show:', res.data.top_tv_shows?.[0])
      console.log('Top libraries count:', res.data.top_libraries?.length)
      console.log('First library:', res.data.top_libraries?.[0])
      return res.data
    }),
    {
      staleTime: 30000, // Consider data fresh for 30 seconds
      cacheTime: 300000, // Keep in cache for 5 minutes
    }
  )

  // Get servers for filter dropdown
  const { data: servers = [] } = useQuery(
    'servers',
    () => api.get('/admin/servers').then(res => res.data)
  )

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Analytics</h1>
          <p className="mt-2 text-slate-600 dark:text-slate-400">
            Comprehensive analytics and insights across all media servers
          </p>
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6 mb-6">
          <div className="flex gap-4 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <label htmlFor="server-select" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Server
              </label>
              <select
                id="server-select"
                value={filters.server_id || ''}
                onChange={(e) => setFilters(prev => ({
                  ...prev,
                  server_id: e.target.value ? parseInt(e.target.value) : undefined
                }))}
                className="w-full bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg px-4 py-2 text-slate-900 dark:text-white"
              >
                <option value="">All Servers</option>
                {servers.map((server: any) => (
                  <option key={server.id} value={server.id}>
                    {server.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex-1 min-w-[200px]">
              <label htmlFor="time-period-select" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Time Period
              </label>
              <select
                id="time-period-select"
                value={filters.days_back}
                onChange={(e) => setFilters(prev => ({
                  ...prev,
                  days_back: parseInt(e.target.value)
                }))}
                className="w-full bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg px-4 py-2 text-slate-900 dark:text-white"
              >
                <option value={1}>Last 24 Hours</option>
                <option value={7}>Last 7 Days</option>
                <option value={30}>Last 30 Days</option>
                <option value={180}>Last 180 Days</option>
                <option value={365}>Last 365 Days</option>
              </select>
            </div>

            <div className="flex-1 min-w-[200px]">
              <label htmlFor="category-select" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Category
              </label>
              <select
                id="category-select"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="w-full bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg px-4 py-2 text-slate-900 dark:text-white"
              >
                <option value="users">Top Users</option>
                <option value="movies">Top Movies</option>
                <option value="shows">Top TV Shows</option>
                <option value="libraries">Top Libraries</option>
                <option value="clients">Top Clients</option>
                <option value="devices">Top Devices</option>
              </select>
            </div>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            <p className="mt-4 text-slate-600 dark:text-slate-400">Loading analytics...</p>
          </div>
        )}

        {/* Summary Cards */}
        {!isLoading && analytics && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
              <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Total Sessions</div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {analytics.total_sessions || 0}
                </div>
              </div>

              <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Active Users</div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {analytics.total_users || 0}
                </div>
              </div>

              <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Watch Time</div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {analytics.total_watch_time_hours || 0}h
                </div>
              </div>

              <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Completion Rate</div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {(analytics.completion_rate ?? 0).toFixed(1)}%
                </div>
              </div>

              <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Video Transcode</div>
                <div className="text-xs text-slate-500 dark:text-slate-500 mb-1">HW Transcoding</div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {(analytics.video_transcode_rate ?? 0).toFixed(1)}%
                </div>
              </div>

              <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-1">Audio/Other Transcode</div>
                <div className="text-xs text-slate-500 dark:text-slate-500 mb-1">SW Transcoding</div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {(analytics.audio_transcode_rate ?? 0).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Top Users */}
            {selectedCategory === 'users' && (
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow mb-6">
              <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Most Active Users</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-50 dark:bg-slate-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Rank
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Username
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Server
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Plays
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Watch Time
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Completion
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                    {analytics.top_users?.map((user, index) => (
                      <tr key={`${user.username}-${index}`} className="hover:bg-slate-50 dark:hover:bg-slate-700">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                          #{index + 1}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <button
                            onClick={() => navigate(`/admin/users/${user.provider_user_id}/watch-history`)}
                            className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:underline cursor-pointer"
                          >
                            {user.username}
                          </button>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">
                          {user.server_name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                          {user.total_plays}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                          {Math.floor((user.total_watch_time_minutes ?? 0) / 60)}h {(user.total_watch_time_minutes ?? 0) % 60}m
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                          {(user.completion_rate ?? 0).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            )}

            {/* Top Movies */}
            {selectedCategory === 'movies' && (
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow mb-6">
              <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Top Movies</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-50 dark:bg-slate-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Rank
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Title
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Year
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Servers
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Plays
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Unique Users
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                    {analytics.top_movies?.map((movie, index) => (
                      <tr key={`${movie.title}-${index}`} className="hover:bg-slate-50 dark:hover:bg-slate-700">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                          #{index + 1}
                        </td>
                        <td className="px-6 py-4 text-sm font-medium text-slate-900 dark:text-white">
                          {movie.title}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">
                          {movie.year}
                        </td>
                        <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-400">
                          {movie.server_name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                          {movie.total_plays}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                          {movie.unique_users}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            )}

            {/* Top TV Shows */}
            {selectedCategory === 'shows' && (
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow mb-6">
              <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Top TV Shows</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-50 dark:bg-slate-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Rank
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Title
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Year
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Servers
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Plays
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Unique Users
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                    {analytics.top_tv_shows?.map((show, index) => (
                      <tr key={`${show.title}-${index}`} className="hover:bg-slate-50 dark:hover:bg-slate-700">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                          #{index + 1}
                        </td>
                        <td className="px-6 py-4 text-sm font-medium text-slate-900 dark:text-white">
                          {show.title}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">
                          {show.year}
                        </td>
                        <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-400">
                          {show.server_name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                          {show.total_plays}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white">
                          {show.unique_users}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            )}

            {/* Top Libraries */}
            {selectedCategory === 'libraries' && (
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow mb-6">
                <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                  <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Top Libraries</h2>
                </div>
                <div className="p-6">
                  <div className="space-y-3">
                    {analytics.top_libraries?.map((library, index) => (
                      <div key={index} className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="text-lg font-bold text-slate-400">#{index + 1}</div>
                          <div>
                            <div className="font-medium text-slate-900 dark:text-white">
                              {library.library_name}
                            </div>
                            <div className="text-sm text-slate-600 dark:text-slate-400">
                              {library.unique_users} users
                            </div>
                          </div>
                        </div>
                        <div className="text-lg font-bold text-slate-900 dark:text-white">
                          {library.total_plays} plays
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
            </div>
            )}

            {/* Top Clients */}
            {selectedCategory === 'clients' && (
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow mb-6">
                <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                  <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Top Clients</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Most used media player applications</p>
                </div>
                <div className="p-6">
                  <div className="space-y-3">
                    {analytics.top_clients?.map((client, index) => (
                      <div key={index} className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="text-lg font-bold text-slate-400">#{index + 1}</div>
                          <div>
                            <div className="font-medium text-slate-900 dark:text-white">
                              {client.client_name}
                            </div>
                            <div className="text-sm text-slate-600 dark:text-slate-400">
                              {client.platform}
                            </div>
                          </div>
                        </div>
                        <div className="text-lg font-bold text-slate-900 dark:text-white">
                          {client.total_plays} plays
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
            </div>
            )}

            {/* Top Devices */}
            {selectedCategory === 'devices' && (
            <div className="bg-white dark:bg-slate-800 rounded-lg shadow mb-6">
                <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                  <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Top Devices</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Most used physical devices</p>
                </div>
                <div className="p-6">
                  <div className="space-y-3">
                    {analytics.top_devices?.map((device, index) => (
                      <div key={index} className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="text-lg font-bold text-slate-400">#{index + 1}</div>
                          <div>
                            <div className="font-medium text-slate-900 dark:text-white">
                              {device.device_name}
                            </div>
                            <div className="text-sm text-slate-600 dark:text-slate-400">
                              {device.platform}
                            </div>
                          </div>
                        </div>
                        <div className="text-lg font-bold text-slate-900 dark:text-white">
                          {device.total_plays} plays
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
            </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
