import { useState, useEffect } from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'

interface ServerModalProps {
  mode: 'add' | 'edit'
  server?: any
  onClose: () => void
  onSubmit: (data: any) => void
  isLoading: boolean
  selectedServerType: string
  setSelectedServerType: (type: string) => void
}

export default function ServerModal({
  mode,
  server,
  onClose,
  onSubmit,
  isLoading,
  selectedServerType,
  setSelectedServerType
}: ServerModalProps) {
  const [formData, setFormData] = useState({
    name: server?.name || '',
    type: server?.type || '',
    base_url: server?.base_url || '',
    enabled: server?.enabled !== false,
    visible_to_media_users: server?.visible_to_media_users !== false,
    username: '',
    password: '',
    token: '',
    api_key: ''
  })

  useEffect(() => {
    if (server) {
      setFormData({
        name: server.name || '',
        type: server.type || '',
        base_url: server.base_url || '',
        enabled: server.enabled !== false,
        visible_to_media_users: server.visible_to_media_users !== false,
        username: '',
        password: '',
        token: '',
        api_key: ''
      })
    }
  }, [server])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const credentials: any = {}

    if (formData.type === 'plex') {
      if (formData.username && formData.password) {
        credentials.username = formData.username
        credentials.password = formData.password
      }
      if (formData.token) {
        credentials.token = formData.token
      }
    } else {
      if (formData.token) {
        credentials.token = formData.token
        credentials.api_key = formData.token
      }
    }

    const submitData: any = {
      name: formData.name,
      type: formData.type,
      base_url: formData.base_url,
      enabled: formData.enabled,
      visible_to_media_users: formData.visible_to_media_users
    }

    // Only include credentials if they were provided
    if (Object.keys(credentials).length > 0) {
      submitData.credentials = credentials
    }

    onSubmit(submitData)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 overflow-y-auto h-full w-full z-50 flex items-center justify-center">
      <div className="relative bg-white dark:bg-slate-800 rounded-lg shadow-xl max-w-md w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
            {mode === 'add' ? 'Add New Server' : 'Edit Server'}
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-500 dark:hover:text-slate-300"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Server Name */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Server Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              className="input w-full"
              placeholder="My Media Server"
            />
          </div>

          {/* Server Type */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Server Type
            </label>
            <select
              value={formData.type}
              onChange={(e) => {
                setFormData({ ...formData, type: e.target.value })
                setSelectedServerType(e.target.value)
              }}
              required
              className="input w-full"
              disabled={mode === 'edit'}
            >
              <option value="">Select Type</option>
              <option value="plex">Plex</option>
              <option value="emby">Emby</option>
              <option value="jellyfin">Jellyfin</option>
            </select>
          </div>

          {/* Server URL */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Server URL
            </label>
            <input
              type="url"
              value={formData.base_url}
              onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
              required
              className="input w-full"
              placeholder="http://localhost:32400"
            />
          </div>

          {/* Enabled Status (Edit mode only) */}
          {mode === 'edit' && (
            <>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="enabled"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-slate-300 rounded"
                />
                <label htmlFor="enabled" className="ml-2 block text-sm text-slate-700 dark:text-slate-300">
                  Server Enabled
                </label>
              </div>

              <div className="flex items-center mt-3">
                <input
                  type="checkbox"
                  id="visible_to_media_users"
                  checked={formData.visible_to_media_users}
                  onChange={(e) => setFormData({ ...formData, visible_to_media_users: e.target.checked })}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-slate-300 rounded"
                />
                <label htmlFor="visible_to_media_users" className="ml-2 block text-sm text-slate-700 dark:text-slate-300">
                  Visible to Media Users (shows in analytics and sessions)
                </label>
              </div>
            </>
          )}

          {/* Authentication Fields */}
          {(formData.type || selectedServerType) && (
            <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-700">
              <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Authentication {mode === 'edit' && '(Leave blank to keep existing)'}
              </h4>

              {(formData.type === 'plex' || selectedServerType === 'plex') ? (
                <>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Plex.tv Username
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                      className="input w-full"
                      placeholder="Your Plex.tv username"
                      required={mode === 'add'}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Plex.tv Password
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      className="input w-full"
                      placeholder="Your Plex.tv password"
                      required={mode === 'add'}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                      API Token (optional)
                    </label>
                    <input
                      type="text"
                      value={formData.token}
                      onChange={(e) => setFormData({ ...formData, token: e.target.value })}
                      className="input w-full"
                      placeholder="Leave blank to use Plex.tv auth"
                    />
                  </div>
                </>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    API Token
                  </label>
                  <input
                    type="text"
                    value={formData.token}
                    onChange={(e) => setFormData({ ...formData, token: e.target.value })}
                    className="input w-full"
                    placeholder="Your server API token"
                    required={mode === 'add'}
                  />
                </div>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="btn btn-primary"
            >
              {isLoading ? (mode === 'add' ? 'Adding...' : 'Updating...') : (mode === 'add' ? 'Add Server' : 'Update Server')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}