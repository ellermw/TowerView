import { useQuery } from 'react-query'
import { PlayIcon, ClockIcon, FilmIcon } from '@heroicons/react/24/outline'
import api from '../../services/api'

export default function MediaUserHome() {
  const { data: sessions = [] } = useQuery('my-sessions', () =>
    api.get('/me/sessions').then(res => res.data)
  )

  const { data: stats } = useQuery('my-stats', () =>
    api.get('/me/stats').then(res => res.data)
  )

  return (
    <div className="px-4 py-6 sm:px-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          Your media consumption overview
        </p>
      </div>

      {/* Stats Grid */}
      {stats && (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 mb-8">
          <div className="card">
            <div className="card-body">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <ClockIcon className="h-6 w-6 text-blue-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                      Total Watch Time
                    </dt>
                    <dd className="text-lg font-medium text-gray-900 dark:text-white">
                      {stats.total_watch_time_hours}h
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-body">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <PlayIcon className="h-6 w-6 text-green-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                      Total Sessions
                    </dt>
                    <dd className="text-lg font-medium text-gray-900 dark:text-white">
                      {stats.total_sessions}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-body">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <FilmIcon className="h-6 w-6 text-purple-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                      Unique Media
                    </dt>
                    <dd className="text-lg font-medium text-gray-900 dark:text-white">
                      {stats.unique_media_watched}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Current Sessions */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-lg leading-6 font-medium text-gray-900 dark:text-white">
            Current Sessions
          </h3>
        </div>
        <div className="card-body">
          {sessions.length === 0 ? (
            <p className="text-gray-500 dark:text-gray-400 text-center py-8">
              No active sessions
            </p>
          ) : (
            <div className="flow-root">
              <ul className="-my-5 divide-y divide-gray-200 dark:divide-dark-700">
                {sessions.map((session: any) => (
                  <li key={session.id} className="py-4">
                    <div className="flex items-center space-x-4">
                      <div className="flex-shrink-0">
                        <div className="h-8 w-8 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
                          <PlayIcon className="h-4 w-4 text-green-600 dark:text-green-300" />
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                          Currently watching media
                        </p>
                        <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                          Session started {new Date(session.started_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex-shrink-0">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                          Active
                        </span>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}