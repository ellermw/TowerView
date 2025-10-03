import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import toast from 'react-hot-toast'
import {
  ArrowPathIcon,
  UserGroupIcon,
  FolderIcon,
  ClockIcon,
  CheckIcon,
  XMarkIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
  PlayIcon
} from '@heroicons/react/24/outline'
import IntervalPicker from './IntervalPicker'
import api from '../../services/api'

interface SyncSettingsData {
  // User sync
  user_sync_enabled: boolean
  user_sync_interval_seconds: number
  user_sync_last_run?: string
  user_sync_next_run?: string

  // Library sync
  library_sync_enabled: boolean
  library_sync_interval_seconds: number
  library_passive_discovery: boolean
  library_sync_last_run?: string
  library_sync_next_run?: string

  // Cache intervals
  sessions_cache_interval_seconds: number
  analytics_cache_interval_seconds: number
  server_status_interval_seconds: number
}

export default function SyncSettings() {
  const queryClient = useQueryClient()
  const [settings, setSettings] = useState<SyncSettingsData>({
    user_sync_enabled: false,
    user_sync_interval_seconds: 3600,
    library_sync_enabled: false,
    library_sync_interval_seconds: 86400,
    library_passive_discovery: true,
    sessions_cache_interval_seconds: 30,
    analytics_cache_interval_seconds: 300,
    server_status_interval_seconds: 60
  })

  // Fetch sync settings
  const { data: syncSettings, isLoading } = useQuery<SyncSettingsData>(
    'sync-settings',
    () => api.get('/settings/sync').then(res => res.data),
    {
      onSuccess: (data) => {
        setSettings(data)
      },
      refetchInterval: 30000 // Refresh every 30 seconds to update next run times
    }
  )

  // Save mutation
  const saveMutation = useMutation(
    (data: SyncSettingsData) => api.post('/settings/sync', data),
    {
      onSuccess: () => {
        toast.success('Sync settings saved successfully')
        queryClient.invalidateQueries('sync-settings')
      },
      onError: (error: any) => {
        const message = error?.response?.data?.detail || 'Failed to save sync settings'
        toast.error(message)
      }
    }
  )

  // Manual sync mutations
  const runUserSyncMutation = useMutation(
    () => api.post('/settings/sync/run-user-sync'),
    {
      onSuccess: () => {
        toast.success('User sync started successfully')
        queryClient.invalidateQueries('sync-settings')
      },
      onError: (error: any) => {
        const message = error?.response?.data?.detail || 'Failed to start user sync'
        if (message.includes('API limit')) {
          toast.error('API rate limit reached. Please try again later.')
        } else {
          toast.error(message)
        }
      }
    }
  )

  const runLibrarySyncMutation = useMutation(
    () => api.post('/settings/sync/run-library-sync'),
    {
      onSuccess: () => {
        toast.success('Library sync started successfully')
        queryClient.invalidateQueries('sync-settings')
      },
      onError: (error: any) => {
        const message = error?.response?.data?.detail || 'Failed to start library sync'
        if (message.includes('API limit')) {
          toast.error('API rate limit reached. Please try again later.')
        } else {
          toast.error(message)
        }
      }
    }
  )

  const handleSave = () => {
    saveMutation.mutate(settings)
  }

  const formatDateTime = (dateStr?: string) => {
    if (!dateStr) return 'Never'
    const date = new Date(dateStr)
    return date.toLocaleString()
  }

  const getTimeUntil = (dateStr?: string) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diff = date.getTime() - now.getTime()

    if (diff <= 0) return 'Due now'

    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (days > 0) return `in ${days} day${days > 1 ? 's' : ''}`
    if (hours > 0) return `in ${hours} hour${hours > 1 ? 's' : ''}`
    return `in ${minutes} minute${minutes !== 1 ? 's' : ''}`
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <ArrowPathIcon className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* User Sync Section */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <UserGroupIcon className="w-6 h-6 text-blue-500" />
            <h3 className="text-lg font-semibold">User Synchronization</h3>
          </div>
          <div className="flex items-center space-x-4">
            <button
              onClick={() => runUserSyncMutation.mutate()}
              disabled={runUserSyncMutation.isLoading}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
            >
              {runUserSyncMutation.isLoading ? (
                <>
                  <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  <span>Running...</span>
                </>
              ) : (
                <>
                  <PlayIcon className="w-4 h-4" />
                  <span>Run Now</span>
                </>
              )}
            </button>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={settings.user_sync_enabled}
                onChange={(e) => setSettings({ ...settings, user_sync_enabled: e.target.checked })}
                className="rounded text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm font-medium">Enable Auto Sync</span>
            </label>
          </div>
        </div>

        <div className={`space-y-4 ${!settings.user_sync_enabled ? 'opacity-50' : ''}`}>
          <IntervalPicker
            label="Sync Interval"
            value={settings.user_sync_interval_seconds}
            onChange={(value) => setSettings({ ...settings, user_sync_interval_seconds: value })}
            min={300} // 5 minutes minimum
            max={604800} // 1 week maximum
          />

          {syncSettings && (
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500 dark:text-gray-400">Last Run:</span>
                <p className="font-medium">{formatDateTime(syncSettings.user_sync_last_run)}</p>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Next Run:</span>
                <p className="font-medium">
                  {syncSettings.user_sync_next_run ? (
                    <>
                      {formatDateTime(syncSettings.user_sync_next_run)}
                      <span className="text-xs text-gray-500 ml-1">
                        {getTimeUntil(syncSettings.user_sync_next_run)}
                      </span>
                    </>
                  ) : 'N/A'}
                </p>
              </div>
            </div>
          )}

          <div className="flex items-start space-x-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <InformationCircleIcon className="w-5 h-5 text-blue-600 mt-0.5" />
            <p className="text-sm text-gray-700 dark:text-gray-300">
              When enabled, automatically syncs users from all configured media servers at the specified interval.
            </p>
          </div>
        </div>
      </div>

      {/* Library Sync Section */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <FolderIcon className="w-6 h-6 text-green-500" />
            <h3 className="text-lg font-semibold">Library Discovery</h3>
          </div>
          <div className="flex items-center space-x-4">
            <button
              onClick={() => runLibrarySyncMutation.mutate()}
              disabled={runLibrarySyncMutation.isLoading}
              className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
            >
              {runLibrarySyncMutation.isLoading ? (
                <>
                  <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  <span>Running...</span>
                </>
              ) : (
                <>
                  <PlayIcon className="w-4 h-4" />
                  <span>Run Now</span>
                </>
              )}
            </button>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={settings.library_sync_enabled}
                onChange={(e) => setSettings({ ...settings, library_sync_enabled: e.target.checked })}
                className="rounded text-green-600 focus:ring-green-500"
              />
              <span className="text-sm font-medium">Enable Active Sync</span>
            </label>
          </div>
        </div>

        <div className="space-y-4">
          <div className={`space-y-4 ${!settings.library_sync_enabled ? 'opacity-50' : ''}`}>
            <IntervalPicker
              label="Sync Interval"
              value={settings.library_sync_interval_seconds}
              onChange={(value) => setSettings({ ...settings, library_sync_interval_seconds: value })}
              min={3600} // 1 hour minimum
              max={2592000} // 30 days maximum
            />

            {syncSettings && settings.library_sync_enabled && (
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Last Run:</span>
                  <p className="font-medium">{formatDateTime(syncSettings.library_sync_last_run)}</p>
                </div>
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Next Run:</span>
                  <p className="font-medium">
                    {syncSettings.library_sync_next_run ? (
                      <>
                        {formatDateTime(syncSettings.library_sync_next_run)}
                        <span className="text-xs text-gray-500 ml-1">
                          {getTimeUntil(syncSettings.library_sync_next_run)}
                        </span>
                      </>
                    ) : 'N/A'}
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="border-t pt-4">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={settings.library_passive_discovery}
                onChange={(e) => setSettings({ ...settings, library_passive_discovery: e.target.checked })}
                className="rounded text-green-600 focus:ring-green-500"
              />
              <span className="text-sm font-medium">Enable Passive Discovery</span>
              <span className="text-xs text-gray-500">(Recommended)</span>
            </label>

            <div className="flex items-start space-x-2 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg mt-3">
              <InformationCircleIcon className="w-5 h-5 text-green-600 mt-0.5" />
              <div className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                <p>
                  <strong>Active Sync:</strong> Queries media servers directly for library information.
                </p>
                <p>
                  <strong>Passive Discovery:</strong> Discovers libraries from user playback activity (always enabled).
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Cache Refresh Settings */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
        <div className="flex items-center space-x-3 mb-4">
          <ClockIcon className="w-6 h-6 text-purple-500" />
          <h3 className="text-lg font-semibold">Cache Refresh Intervals</h3>
        </div>

        <div className="space-y-4">
          <IntervalPicker
            label="Sessions Cache"
            value={settings.sessions_cache_interval_seconds}
            onChange={(value) => setSettings({ ...settings, sessions_cache_interval_seconds: value })}
            min={10}
            max={300}
          />

          <IntervalPicker
            label="Analytics Cache"
            value={settings.analytics_cache_interval_seconds}
            onChange={(value) => setSettings({ ...settings, analytics_cache_interval_seconds: value })}
            min={60}
            max={3600}
          />

          <IntervalPicker
            label="Server Status"
            value={settings.server_status_interval_seconds}
            onChange={(value) => setSettings({ ...settings, server_status_interval_seconds: value })}
            min={30}
            max={600}
          />

          <div className="flex items-start space-x-2 p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
            <InformationCircleIcon className="w-5 h-5 text-purple-600 mt-0.5" />
            <p className="text-sm text-gray-700 dark:text-gray-300">
              These settings control how often data is refreshed in the background. Lower values provide more real-time data but may increase server load.
            </p>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end space-x-3">
        <button
          onClick={() => {
            const initial = syncSettings || settings
            setSettings(initial)
          }}
          className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
        >
          Reset
        </button>
        <button
          onClick={handleSave}
          disabled={saveMutation.isLoading}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
        >
          {saveMutation.isLoading ? (
            <>
              <ArrowPathIcon className="w-4 h-4 animate-spin" />
              <span>Saving...</span>
            </>
          ) : (
            <>
              <CheckIcon className="w-4 h-4" />
              <span>Save Settings</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}