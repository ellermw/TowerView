import { Navigate } from 'react-router-dom'
import { usePermissions } from '../../hooks/usePermissions'
import { useQuery } from 'react-query'
import api from '../../services/api'
import { useState } from 'react'
import { formatDistanceToNow } from 'date-fns'

interface AuditLog {
  id: number
  actor_id: number | null
  actor_username: string
  actor_type: string
  action: string
  target: string | null
  target_name: string | null
  details: Record<string, any> | null
  ip_address: string | null
  user_agent: string | null
  created_at: string
}

interface AuditLogResponse {
  items: AuditLog[]
  total: number
  page: number
  per_page: number
  pages: number
}

const ACTION_COLORS: Record<string, string> = {
  LOGIN: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  LOGOUT: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
  SESSION_TERMINATED: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  USER_CREATED: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  USER_MODIFIED: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  USER_DELETED: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  SERVER_ADDED: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  SERVER_MODIFIED: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  SERVER_DELETED: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  CONTAINER_START: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  CONTAINER_STOP: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  CONTAINER_RESTART: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  CONTAINER_UPDATE: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
  SETTINGS_CHANGED: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
}

export default function AuditLogs() {
  const { isAdmin } = usePermissions()
  const [page, setPage] = useState(1)
  const [actorType, setActorType] = useState<string>('')
  const [action, setAction] = useState<string>('')
  const [searchTerm, setSearchTerm] = useState<string>('')

  // Only admin users can view audit logs
  if (!isAdmin) {
    return <Navigate to="/admin" replace />
  }

  const { data: logsData, isLoading, error } = useQuery<AuditLogResponse>({
    queryKey: ['audit-logs', page, actorType, action, searchTerm],
    queryFn: async () => {
      const params = new URLSearchParams({
        page: page.toString(),
        per_page: '50',
      })
      if (actorType) params.append('actor_type', actorType)
      if (action) params.append('action', action)
      if (searchTerm) params.append('search', searchTerm)

      const response = await api.get(`/admin/audit-logs?${params.toString()}`)
      return response.data
    },
  })

  const { data: availableActions } = useQuery<string[]>({
    queryKey: ['audit-log-actions'],
    queryFn: async () => {
      const response = await api.get('/admin/audit-logs/actions')
      return response.data
    },
  })

  const getActionDescription = (log: AuditLog): string => {
    switch (log.action) {
      case 'LOGIN':
        return `${log.actor_username} logged in`
      case 'LOGOUT':
        return `${log.actor_username} logged out`
      case 'SESSION_TERMINATED':
        return `${log.actor_username} terminated session for ${log.target_name}`
      case 'USER_CREATED':
        return `${log.actor_username} created user ${log.target_name}`
      case 'USER_MODIFIED':
        return `${log.actor_username} modified user ${log.target_name}`
      case 'USER_DELETED':
        return `${log.actor_username} deleted user ${log.target_name}`
      case 'SERVER_ADDED':
        return `${log.actor_username} added server ${log.target_name}`
      case 'SERVER_MODIFIED':
        return `${log.actor_username} modified server ${log.target_name}`
      case 'SERVER_DELETED':
        return `${log.actor_username} deleted server ${log.target_name}`
      case 'CONTAINER_START':
        return `${log.actor_username} started container on ${log.target_name}`
      case 'CONTAINER_STOP':
        return `${log.actor_username} stopped container on ${log.target_name}`
      case 'CONTAINER_RESTART':
        return `${log.actor_username} restarted container on ${log.target_name}`
      case 'CONTAINER_UPDATE':
        return `${log.actor_username} updated container on ${log.target_name}`
      case 'SETTINGS_CHANGED':
        return `${log.actor_username} changed settings for ${log.target_name}`
      default:
        return `${log.actor_username} performed ${log.action}${log.target_name ? ` on ${log.target_name}` : ''}`
    }
  }

  const getActionColor = (action: string): string => {
    return ACTION_COLORS[action] || 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
  }

  const formatUserAgent = (userAgent: string | null): string => {
    if (!userAgent) return 'Unknown'
    const match = userAgent.match(/^([^/]+)\/[^ ]+ \(([^)]+)\)/)
    if (match) {
      return `${match[1]} (${match[2].split(';')[0].trim()})`
    }
    return userAgent.length > 50 ? userAgent.substring(0, 50) + '...' : userAgent
  }

  return (
    <div className="px-4 py-6 sm:px-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
        Audit Logs
      </h1>

      {/* Filters */}
      <div className="card mb-6">
        <div className="card-body">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Search
              </label>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value)
                  setPage(1)
                }}
                placeholder="Search username or target..."
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Actor Type
              </label>
              <select
                value={actorType}
                onChange={(e) => {
                  setActorType(e.target.value)
                  setPage(1)
                }}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              >
                <option value="">All Types</option>
                <option value="admin">Admin</option>
                <option value="local_user">Local User</option>
                <option value="system">System</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Action
              </label>
              <select
                value={action}
                onChange={(e) => {
                  setAction(e.target.value)
                  setPage(1)
                }}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              >
                <option value="">All Actions</option>
                {availableActions?.map((act: string) => (
                  <option key={act} value={act}>
                    {act.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-end">
              <button
                onClick={() => {
                  setSearchTerm('')
                  setActorType('')
                  setAction('')
                  setPage(1)
                }}
                className="w-full px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600 transition-colors"
              >
                Clear Filters
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Logs Table */}
      <div className="card">
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-8 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
              <p className="mt-2 text-gray-500 dark:text-gray-400">Loading audit logs...</p>
            </div>
          ) : error ? (
            <div className="p-8 text-center text-red-500">
              Error loading audit logs
            </div>
          ) : !logsData?.items.length ? (
            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
              No audit logs found
            </div>
          ) : (
            <>
              <table className="w-full">
                <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Time
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      User
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Action
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Description
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      IP Address
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Browser
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                  {logsData.items.map((log: AuditLog) => (
                    <tr key={log.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                        <div>
                          <div>{new Date(log.created_at).toLocaleString()}</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <div>
                          <div className="text-gray-900 dark:text-gray-100 font-medium">
                            {log.actor_username}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {log.actor_type === 'admin' ? 'Admin' : log.actor_type === 'local_user' ? 'Local User' : 'System'}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getActionColor(log.action)}`}>
                          {log.action.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100">
                        <div>
                          <div>{getActionDescription(log)}</div>
                          {log.details && Object.keys(log.details).length > 0 && (
                            <details className="mt-1">
                              <summary className="text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
                                View details
                              </summary>
                              <pre className="text-xs text-gray-600 dark:text-gray-400 mt-1 p-2 bg-gray-50 dark:bg-gray-900 rounded overflow-x-auto">
                                {JSON.stringify(log.details, null, 2)}
                              </pre>
                            </details>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        {log.ip_address || (log.actor_username === 'System' ? '-' : 'Unknown')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                        <div className="max-w-xs truncate" title={log.user_agent || (log.actor_username === 'System' ? '-' : 'Unknown')}>
                          {log.user_agent ? formatUserAgent(log.user_agent) : (log.actor_username === 'System' ? '-' : 'Unknown')}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              {logsData.pages > 1 && (
                <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-700 dark:text-gray-300">
                      Showing {((page - 1) * logsData.per_page) + 1} to {Math.min(page * logsData.per_page, logsData.total)} of {logsData.total} entries
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => setPage(Math.max(1, page - 1))}
                        disabled={page === 1}
                        className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Previous
                      </button>
                      {[...Array(Math.min(5, logsData.pages))].map((_, i) => {
                        const pageNum = i + 1
                        if (logsData.pages <= 5) {
                          return (
                            <button
                              key={pageNum}
                              onClick={() => setPage(pageNum)}
                              className={`px-3 py-1 border rounded-md text-sm font-medium ${
                                page === pageNum
                                  ? 'bg-blue-500 text-white border-blue-500'
                                  : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
                              }`}
                            >
                              {pageNum}
                            </button>
                          )
                        }
                        // Show smart pagination for many pages
                        let displayPage = pageNum
                        if (page > 3) {
                          if (i === 0) displayPage = 1
                          else if (i === 1 && page > 4) return <span key={i} className="px-2">...</span>
                          else if (i === 1) displayPage = page - 1
                          else if (i === 2) displayPage = page
                          else if (i === 3) displayPage = Math.min(page + 1, logsData.pages)
                          else if (i === 4 && page < logsData.pages - 3) return <span key={i} className="px-2">...</span>
                          else displayPage = logsData.pages
                        }
                        return (
                          <button
                            key={i}
                            onClick={() => setPage(displayPage)}
                            className={`px-3 py-1 border rounded-md text-sm font-medium ${
                              page === displayPage
                                ? 'bg-blue-500 text-white border-blue-500'
                                : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
                            }`}
                          >
                            {displayPage}
                          </button>
                        )
                      })}
                      <button
                        onClick={() => setPage(Math.min(logsData.pages, page + 1))}
                        disabled={page === logsData.pages}
                        className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}