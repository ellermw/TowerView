import React, { useState, useEffect, Fragment } from 'react'
import { useQuery, useMutation } from 'react-query'
import { Dialog, Transition } from '@headlessui/react'
import toast from 'react-hot-toast'
import {
  ArrowDownTrayIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  XMarkIcon
} from '@heroicons/react/24/outline'
import api from '../../services/api'

interface Server {
  id: number
  name: string
  type: string
}

interface ImportProgress {
  status: string
  current: number
  total: number
  stats: {
    imported: number
    skipped: number
    errors: number
  }
}

export default function TautulliImport() {
  const [selectedServerId, setSelectedServerId] = useState<number | null>(null)
  const [tautulliUrl, setTautulliUrl] = useState('http://localhost:8181')
  const [tautulliApiKey, setTautulliApiKey] = useState('')
  const [afterDate, setAfterDate] = useState('')
  const [beforeDate, setBeforeDate] = useState('')
  const [importing, setImporting] = useState(false)
  const [importId, setImportId] = useState<string | null>(null)
  const [progress, setProgress] = useState<ImportProgress | null>(null)
  const [showProgressModal, setShowProgressModal] = useState(false)

  // Fetch servers
  const { data: servers = [], isLoading: isLoadingServers } = useQuery<Server[]>(
    'servers',
    () => api.get('/admin/servers').then(res => res.data)
  )

  // Filter to only show Plex servers
  const plexServers = servers.filter(s => s.type === 'plex')

  // Test connection mutation
  const testConnection = useMutation(
    async () => {
      const response = await api.post('/settings/tautulli/test', {
        tautulli_url: tautulliUrl,
        tautulli_api_key: tautulliApiKey
      })
      return response.data
    },
    {
      onSuccess: () => {
        toast.success('Successfully connected to Tautulli!')
      },
      onError: (error: any) => {
        toast.error(error.response?.data?.detail || 'Failed to connect to Tautulli')
      }
    }
  )

  // Start import mutation
  const startImport = useMutation(
    async () => {
      const response = await api.post('/settings/tautulli/import', {
        server_id: selectedServerId,
        tautulli_url: tautulliUrl,
        tautulli_api_key: tautulliApiKey,
        after_date: afterDate || null,
        before_date: beforeDate || null
      })
      return response.data
    },
    {
      onSuccess: (data) => {
        setImportId(data.import_id)
        setImporting(true)
        setShowProgressModal(true)
        toast.success('Import started!')
      },
      onError: (error: any) => {
        const errorMsg = error.response?.data?.detail || error.message || 'Failed to start import'
        console.error('Import error:', error.response?.data || error)
        toast.error(errorMsg)
      }
    }
  )

  // Poll for import progress
  useEffect(() => {
    if (!importId || !importing) return

    const interval = setInterval(async () => {
      try {
        const response = await api.get(`/settings/tautulli/import/${importId}/progress`)
        const data = response.data as ImportProgress

        setProgress(data)

        if (data.status === 'completed') {
          setImporting(false)
          clearInterval(interval)
        } else if (data.status === 'failed') {
          setImporting(false)
          clearInterval(interval)
        }
      } catch (error) {
        console.error('Error fetching progress:', error)
      }
    }, 2000) // Poll every 2 seconds

    return () => clearInterval(interval)
  }, [importId, importing])

  const handleStartImport = () => {
    if (!selectedServerId) {
      toast.error('Please select a server')
      return
    }
    if (!tautulliApiKey) {
      toast.error('Please enter Tautulli API key')
      return
    }
    startImport.mutate()
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">Tautulli Import</h2>
        <p className="text-slate-600 dark:text-slate-400">
          Import historical playback data from Tautulli into TowerView for comprehensive analytics.
        </p>
      </div>

      {/* Configuration */}
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6 space-y-4">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Configuration</h3>

        {/* Server Selection */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Plex Server
          </label>
          <select
            value={selectedServerId || ''}
            onChange={(e) => setSelectedServerId(e.target.value ? parseInt(e.target.value) : null)}
            className="w-full px-4 py-2 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white"
            disabled={importing || isLoadingServers}
          >
            <option value="">{isLoadingServers ? 'Loading servers...' : 'Select a Plex server...'}</option>
            {plexServers.map((server) => (
              <option key={server.id} value={server.id}>
                {server.name}
              </option>
            ))}
          </select>
          {!isLoadingServers && plexServers.length === 0 && servers.length > 0 && (
            <p className="mt-2 text-sm text-amber-600 dark:text-amber-400">
              No Plex servers configured. Only Plex servers are supported. (Found {servers.length} non-Plex server(s))
            </p>
          )}
          {!isLoadingServers && servers.length === 0 && (
            <p className="mt-2 text-sm text-amber-600 dark:text-amber-400">
              No servers configured. Add a Plex server first.
            </p>
          )}
        </div>

        {/* Tautulli URL */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Tautulli URL
          </label>
          <input
            type="text"
            value={tautulliUrl}
            onChange={(e) => setTautulliUrl(e.target.value)}
            placeholder="http://localhost:8181"
            className="w-full px-4 py-2 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white"
            disabled={importing}
          />
        </div>

        {/* Tautulli API Key */}
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Tautulli API Key
          </label>
          <input
            type="password"
            value={tautulliApiKey}
            onChange={(e) => setTautulliApiKey(e.target.value)}
            placeholder="Your Tautulli API key"
            className="w-full px-4 py-2 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white"
            disabled={importing}
          />
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Find this in Tautulli Settings → Web Interface → API
          </p>
        </div>

        {/* Test Connection Button */}
        <div>
          <button
            onClick={() => testConnection.mutate()}
            disabled={!tautulliApiKey || testConnection.isLoading || importing}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {testConnection.isLoading ? (
              <ArrowPathIcon className="h-5 w-5 mr-2 animate-spin" />
            ) : (
              <CheckCircleIcon className="h-5 w-5 mr-2" />
            )}
            Test Connection
          </button>
        </div>

        {/* Date Range (Optional) */}
        <div className="border-t border-slate-200 dark:border-slate-700 pt-4">
          <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
            Date Range (Optional)
          </h4>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-600 dark:text-slate-400 mb-1">
                After Date
              </label>
              <input
                type="date"
                value={afterDate}
                onChange={(e) => setAfterDate(e.target.value)}
                className="w-full px-4 py-2 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white"
                disabled={importing}
              />
            </div>
            <div>
              <label className="block text-sm text-slate-600 dark:text-slate-400 mb-1">
                Before Date
              </label>
              <input
                type="date"
                value={beforeDate}
                onChange={(e) => setBeforeDate(e.target.value)}
                className="w-full px-4 py-2 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-900 dark:text-white"
                disabled={importing}
              />
            </div>
          </div>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            Leave empty to import all available history
          </p>
        </div>
      </div>

      {/* Import Button */}
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow p-6">
        <button
          onClick={handleStartImport}
          disabled={!selectedServerId || !tautulliApiKey || importing || startImport.isLoading}
          className="inline-flex items-center px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          {importing ? (
            <>
              <ArrowPathIcon className="h-5 w-5 mr-2 animate-spin" />
              Importing...
            </>
          ) : (
            <>
              <ArrowDownTrayIcon className="h-5 w-5 mr-2" />
              Start Import
            </>
          )}
        </button>
      </div>

      {/* Progress Modal */}
      <Transition appear show={showProgressModal} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => {}}>
          <Transition.Child
            as={Fragment}
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
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-2xl transform overflow-hidden rounded-2xl bg-white dark:bg-slate-800 p-6 text-left align-middle shadow-xl transition-all">
                  <div className="flex justify-between items-center mb-4">
                    <Dialog.Title
                      as="h3"
                      className="text-lg font-medium leading-6 text-slate-900 dark:text-white"
                    >
                      {progress?.status === 'completed' ? 'Import Complete!' : 'Importing Tautulli History'}
                    </Dialog.Title>
                    {progress?.status === 'completed' && (
                      <button
                        onClick={() => setShowProgressModal(false)}
                        className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                      >
                        <XMarkIcon className="h-6 w-6" />
                      </button>
                    )}
                  </div>

                  {progress && (
                    <div className="space-y-4">
                      {/* Progress Bar */}
                      <div>
                        <div className="flex justify-between text-sm mb-2">
                          <span className="text-slate-600 dark:text-slate-400">Progress</span>
                          <span className="font-medium text-slate-900 dark:text-white">
                            {progress.current.toLocaleString()} / {progress.total.toLocaleString()} records
                          </span>
                        </div>
                        <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-6 overflow-hidden">
                          <div
                            className={`h-6 rounded-full transition-all duration-300 flex items-center justify-center text-xs font-medium text-white ${
                              progress.status === 'completed' ? 'bg-green-600' : 'bg-blue-600'
                            }`}
                            style={{ width: `${progress.total > 0 ? (progress.current / progress.total) * 100 : 0}%` }}
                          >
                            {progress.total > 0 && `${Math.round((progress.current / progress.total) * 100)}%`}
                          </div>
                        </div>
                      </div>

                      {/* Stats */}
                      <div className="grid grid-cols-3 gap-4">
                        <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4 text-center">
                          <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                            {progress.stats.imported.toLocaleString()}
                          </div>
                          <div className="text-sm text-green-700 dark:text-green-300 mt-1">Imported</div>
                        </div>
                        <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 text-center">
                          <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                            {progress.stats.skipped.toLocaleString()}
                          </div>
                          <div className="text-sm text-blue-700 dark:text-blue-300 mt-1">Skipped</div>
                        </div>
                        <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4 text-center">
                          <div className="text-3xl font-bold text-red-600 dark:text-red-400">
                            {progress.stats.errors.toLocaleString()}
                          </div>
                          <div className="text-sm text-red-700 dark:text-red-300 mt-1">Errors</div>
                        </div>
                      </div>

                      {/* Status */}
                      <div className="flex items-center justify-center pt-2">
                        {progress.status === 'running' && (
                          <div className="flex items-center text-blue-600 dark:text-blue-400">
                            <ArrowPathIcon className="h-5 w-5 mr-2 animate-spin" />
                            <span className="font-medium">Importing...</span>
                          </div>
                        )}
                        {progress.status === 'completed' && (
                          <div className="flex items-center text-green-600 dark:text-green-400">
                            <CheckCircleIcon className="h-5 w-5 mr-2" />
                            <span className="font-medium">Import Complete!</span>
                          </div>
                        )}
                        {progress.status === 'failed' && (
                          <div className="flex items-center text-red-600 dark:text-red-400">
                            <XCircleIcon className="h-5 w-5 mr-2" />
                            <span className="font-medium">Import Failed</span>
                          </div>
                        )}
                      </div>

                      {/* Close button when complete */}
                      {progress.status === 'completed' && (
                        <div className="flex justify-end mt-4">
                          <button
                            onClick={() => setShowProgressModal(false)}
                            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                          >
                            Close
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  )
}
