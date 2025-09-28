import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import {
  UserIcon,
  PlusIcon,
  PencilIcon,
  TrashIcon,
  ShieldCheckIcon
} from '@heroicons/react/24/outline'
import api from '../../services/api'

interface LocalUser {
  id: number
  username: string
  email?: string
  type: string
  must_change_password: boolean
  created_at: string
  updated_at: string
  permissions: UserPermission[]
}

interface UserRole {
  value: string
  label: string
  description: string
}

const USER_ROLES: UserRole[] = [
  { value: 'admin', label: 'Admin', description: 'Full access to all servers and can create any user type' },
  { value: 'staff', label: 'Staff', description: 'Can create Support accounts and manage assigned servers' },
  { value: 'support', label: 'Support', description: 'View-only access to assigned servers' }
]

interface UserPermission {
  server_id: number
  can_view_sessions: boolean
  can_view_users: boolean
  can_view_analytics: boolean
  can_terminate_sessions: boolean
  can_manage_server: boolean
}

interface Server {
  id: number
  name: string
  type: string
  enabled: boolean
}

export default function LocalUsersManagement() {
  const queryClient = useQueryClient()
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [isPermissionsModalOpen, setIsPermissionsModalOpen] = useState(false)
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState<LocalUser | null>(null)
  const [selectedRole, setSelectedRole] = useState<string>('')
  const [localPermissions, setLocalPermissions] = useState<UserPermission[]>([])
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    must_change_password: false,
    role: 'support' as string
  })

  // Get current user to determine permissions
  const { data: currentUser } = useQuery(
    'current-user',
    () => api.get('/users/me').then(res => res.data)
  )

  const { data: users = [], isLoading } = useQuery<LocalUser[]>(
    'local-users',
    () => api.get('/admin/local-users').then(res => res.data)
  )

  const { data: servers = [] } = useQuery<Server[]>(
    'servers',
    () => api.get('/admin/servers').then(res => res.data)
  )

  const updateRoleMutation = useMutation(
    ({ id, role }: { id: number; role: string }) =>
      api.patch(`/admin/local-users/${id}/role`, { role }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('local-users')
        setIsRoleModalOpen(false)
        setSelectedUser(null)
        setSelectedRole('')
      },
      onError: (error: any) => {
        alert(error.response?.data?.detail || 'Failed to update role')
      }
    }
  )

  const createUserMutation = useMutation(
    (data: any) => api.post('/admin/local-users', data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('local-users')
        setIsCreateModalOpen(false)
        resetForm()
      },
      onError: (error: any) => {
        console.error('Error creating user:', error.response?.data)
        let errorMessage = 'Failed to create user'

        if (error.response?.data) {
          const data = error.response.data

          // Check for validation errors (422 responses)
          if (Array.isArray(data)) {
            // FastAPI validation errors come as an array
            errorMessage = data.map((err: any) =>
              `${err.loc ? err.loc.join(' > ') : ''}: ${err.msg}`
            ).join('\n')
          } else if (typeof data === 'object') {
            // Check common error fields
            if (data.detail) {
              if (typeof data.detail === 'string') {
                errorMessage = data.detail
              } else if (Array.isArray(data.detail)) {
                errorMessage = data.detail.map((err: any) =>
                  typeof err === 'string' ? err :
                  `${err.loc ? err.loc.join(' > ') : ''}: ${err.msg || err.type || JSON.stringify(err)}`
                ).join('\n')
              } else {
                errorMessage = JSON.stringify(data.detail)
              }
            } else if (data.message) {
              errorMessage = data.message
            } else if (data.error) {
              errorMessage = data.error
            } else {
              // Last resort - stringify the whole object
              errorMessage = JSON.stringify(data)
            }
          } else if (typeof data === 'string') {
            errorMessage = data
          }
        }

        alert(errorMessage)
      }
    }
  )

  const updateUserMutation = useMutation(
    ({ id, data }: { id: number; data: any }) =>
      api.patch(`/admin/local-users/${id}`, data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('local-users')
        setIsEditModalOpen(false)
        resetForm()
      }
    }
  )

  const deleteUserMutation = useMutation(
    (id: number) => api.delete(`/admin/local-users/${id}`),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('local-users')
        alert('User deleted successfully')
      },
      onError: (error: any) => {
        console.error('Delete user error:', error)
        const errorMessage = error.response?.data?.detail || error.message || 'Failed to delete user'
        alert(`Error deleting user: ${errorMessage}`)
      }
    }
  )

  const updatePermissionMutation = useMutation(
    ({ userId, serverId, data }: { userId: number; serverId: number; data: any }) =>
      api.patch(`/admin/local-users/${userId}/permissions/${serverId}`, data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('local-users')
      }
    }
  )

  const grantPermissionMutation = useMutation(
    ({ userId, data }: { userId: number; data: any }) =>
      api.post(`/admin/local-users/${userId}/permissions`, data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('local-users')
      }
    }
  )

  const revokePermissionMutation = useMutation(
    ({ userId, serverId }: { userId: number; serverId: number }) =>
      api.delete(`/admin/local-users/${userId}/permissions/${serverId}`),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('local-users')
      }
    }
  )

  const resetForm = () => {
    setFormData({
      username: '',
      email: '',
      password: '',
      confirmPassword: '',
      must_change_password: false,
      role: 'support'
    })
    setSelectedUser(null)
  }

  const handleCreateUser = () => {
    if (formData.password !== formData.confirmPassword) {
      alert('Passwords do not match')
      return
    }

    createUserMutation.mutate({
      username: formData.username,
      email: formData.email || null,
      password: formData.password,
      must_change_password: formData.must_change_password,
      role: formData.role
    })
  }

  const handleUpdateUser = () => {
    if (!selectedUser) return

    const updateData: any = {}
    if (formData.email !== selectedUser.email) {
      updateData.email = formData.email || null
    }
    if (formData.password) {
      if (formData.password !== formData.confirmPassword) {
        alert('Passwords do not match')
        return
      }
      updateData.password = formData.password
    }
    if (formData.must_change_password !== selectedUser.must_change_password) {
      updateData.must_change_password = formData.must_change_password
    }

    updateUserMutation.mutate({ id: selectedUser.id, data: updateData })
  }

  const handleDeleteUser = (user: LocalUser) => {
    if (confirm(`Are you sure you want to delete user ${user.username}?`)) {
      deleteUserMutation.mutate(user.id)
    }
  }

  const openEditModal = (user: LocalUser) => {
    setSelectedUser(user)
    setFormData({
      username: user.username,
      email: user.email || '',
      password: '',
      confirmPassword: '',
      must_change_password: user.must_change_password,
      role: user.type
    })
    setIsEditModalOpen(true)
  }

  const openPermissionsModal = (user: LocalUser) => {
    setSelectedUser(user)
    setLocalPermissions([...user.permissions])
    setIsPermissionsModalOpen(true)
  }

  const openRoleModal = (user: LocalUser) => {
    setSelectedUser(user)
    setSelectedRole(user.type)
    setIsRoleModalOpen(true)
  }

  const handleUpdateRole = () => {
    if (!selectedUser || !selectedRole) return
    updateRoleMutation.mutate({ id: selectedUser.id, role: selectedRole })
  }

  const getRoleBadge = (type: string) => {
    switch (type) {
      case 'admin':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      case 'staff':
      case 'local_user': // Handle legacy type
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'support':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  const getRoleLabel = (type: string) => {
    if (type === 'local_user') return 'Staff' // Handle legacy type
    return USER_ROLES.find(r => r.value === type)?.label || type
  }

  const canCreateUser = currentUser?.type === 'admin' || currentUser?.type === 'staff' || currentUser?.type === 'local_user'
  const canDeleteUser = currentUser?.type === 'admin'
  const canChangeRole = currentUser?.type === 'admin'

  const hasPermissionForServer = (serverId: number) => {
    return localPermissions.some(p => p.server_id === serverId)
  }

  const getPermissionForServer = (serverId: number) => {
    return localPermissions.find(p => p.server_id === serverId)
  }

  const toggleServerPermission = (user: LocalUser, server: Server) => {
    const existingPermission = getPermissionForServer(server.id)

    if (existingPermission) {
      // Remove from local state immediately
      setLocalPermissions(prev => prev.filter(p => p.server_id !== server.id))
      // Then update backend
      revokePermissionMutation.mutate({ userId: user.id, serverId: server.id })
    } else {
      // Add to local state immediately
      const newPermission: UserPermission = {
        server_id: server.id,
        can_view_sessions: true,
        can_view_users: true,
        can_view_analytics: true,
        can_terminate_sessions: false,
        can_manage_server: false
      }
      setLocalPermissions(prev => [...prev, newPermission])
      // Then update backend
      grantPermissionMutation.mutate({
        userId: user.id,
        data: newPermission
      })
    }
  }

  const updatePermissionDetail = (
    user: LocalUser,
    server: Server,
    field: keyof UserPermission,
    value: boolean
  ) => {
    // Update local state immediately
    setLocalPermissions(prev =>
      prev.map(p =>
        p.server_id === server.id
          ? { ...p, [field]: value }
          : p
      )
    )

    // Then update backend
    updatePermissionMutation.mutate({
      userId: user.id,
      serverId: server.id,
      data: { [field]: value }
    })
  }

  if (isLoading) {
    return (
      <div className="px-4 py-6 sm:px-6">
        <div className="flex justify-center py-8">
          <div className="text-slate-600 dark:text-slate-400">Loading local users...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4 py-6 sm:px-6">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            System Users
          </h1>
          <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
            Manage all system users including administrators, staff, and support accounts
          </p>
        </div>
        <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
          {canCreateUser && (
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="btn btn-primary"
            >
              <PlusIcon className="h-5 w-5 mr-2" />
              Create User
            </button>
          )}
        </div>
      </div>

      <div className="mt-8">
        {users.length === 0 ? (
          <div className="card">
            <div className="card-body text-center py-12">
              <UserIcon className="mx-auto h-12 w-12 text-slate-400" />
              <h3 className="mt-2 text-sm font-medium text-slate-900 dark:text-white">
                No users found
              </h3>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {canCreateUser ? 'Get started by creating a new user.' : 'No users have been created yet.'}
              </p>
            </div>
          </div>
        ) : (
          <div className="card">
            <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5">
              <table className="min-w-full divide-y divide-slate-300 dark:divide-slate-700">
                <thead className="bg-slate-50 dark:bg-slate-800">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      User
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Role
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Email
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Permissions
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="relative px-6 py-3">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-slate-900 divide-y divide-slate-200 dark:divide-slate-700">
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <UserIcon className="h-8 w-8 text-slate-400" />
                          <div className="ml-4">
                            <div className="text-sm font-medium text-slate-900 dark:text-white">
                              {user.username}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <button
                          onClick={() => (canChangeRole && user.id !== currentUser?.id) ? openRoleModal(user) : null}
                          className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getRoleBadge(user.type)} ${
                            (canChangeRole && user.id !== currentUser?.id) ? 'cursor-pointer hover:opacity-80' : 'cursor-default'
                          }`}
                          title={(canChangeRole && user.id !== currentUser?.id) ? 'Click to change role' : (user.id === currentUser?.id ? 'Cannot change your own role' : '')}
                        >
                          {getRoleLabel(user.type)}
                        </button>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-slate-900 dark:text-white">
                          {user.email || '-'}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-slate-900 dark:text-white">
                          {user.type === 'admin' ? 'All servers' : `${user.permissions.length} server${user.permissions.length !== 1 ? 's' : ''}`}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {user.must_change_password ? (
                          <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                            Must Change Password
                          </span>
                        ) : (
                          <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                            Active
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500 dark:text-slate-400">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => user.type !== 'admin' ? openPermissionsModal(user) : null}
                          className={`mr-4 ${user.type !== 'admin' ? 'text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300' : 'text-gray-400 cursor-not-allowed'}`}
                          title={user.type === 'admin' ? 'Admins have all permissions' : 'Manage permissions'}
                          disabled={user.type === 'admin'}
                        >
                          <ShieldCheckIcon className="h-5 w-5" />
                        </button>
                        <button
                          onClick={() => openEditModal(user)}
                          className="text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300 mr-4"
                        >
                          <PencilIcon className="h-5 w-5" />
                        </button>
                        {(canDeleteUser && user.id !== currentUser?.id) && (
                          <button
                            onClick={() => handleDeleteUser(user)}
                            className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                            title="Delete user"
                          >
                            <TrashIcon className="h-5 w-5" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Create User Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-slate-500 bg-opacity-75 dark:bg-slate-900 dark:bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 w-full max-w-md">
            <h2 className="text-lg font-medium text-slate-900 dark:text-white mb-4">
              Create User
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Username
                </label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  className="mt-1 block w-full border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-700 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Email (Optional)
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="mt-1 block w-full border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-700 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Password
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="mt-1 block w-full border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-700 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Confirm Password
                </label>
                <input
                  type="password"
                  value={formData.confirmPassword}
                  onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                  className="mt-1 block w-full border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-700 dark:text-white"
                />
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="must_change_password"
                  checked={formData.must_change_password}
                  onChange={(e) => setFormData({ ...formData, must_change_password: e.target.checked })}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded"
                />
                <label htmlFor="must_change_password" className="ml-2 block text-sm text-slate-900 dark:text-slate-300">
                  Must change password on first login
                </label>
              </div>
              {currentUser?.type === 'admin' && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                    Role
                  </label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                    className="mt-1 block w-full border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-700 dark:text-white"
                  >
                    {USER_ROLES.map(role => (
                      <option key={role.value} value={role.value}>
                        {role.label} - {role.description}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => { setIsCreateModalOpen(false); resetForm(); }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateUser}
                disabled={createUserMutation.isLoading}
                className="btn btn-primary"
              >
                {createUserMutation.isLoading ? 'Creating...' : 'Create User'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {isEditModalOpen && selectedUser && (
        <div className="fixed inset-0 bg-slate-500 bg-opacity-75 dark:bg-slate-900 dark:bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 w-full max-w-md">
            <h2 className="text-lg font-medium text-slate-900 dark:text-white mb-4">
              Edit User: {selectedUser.username}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Email (Optional)
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="mt-1 block w-full border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-700 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  New Password (leave blank to keep current)
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="mt-1 block w-full border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-700 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Confirm New Password
                </label>
                <input
                  type="password"
                  value={formData.confirmPassword}
                  onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                  className="mt-1 block w-full border-slate-300 dark:border-slate-600 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm dark:bg-slate-700 dark:text-white"
                />
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="must_change_password_edit"
                  checked={formData.must_change_password}
                  onChange={(e) => setFormData({ ...formData, must_change_password: e.target.checked })}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded"
                />
                <label htmlFor="must_change_password_edit" className="ml-2 block text-sm text-slate-900 dark:text-slate-300">
                  Must change password on next login
                </label>
              </div>
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => { setIsEditModalOpen(false); resetForm(); }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateUser}
                className="btn btn-primary"
              >
                Update User
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Role Change Modal */}
      {isRoleModalOpen && selectedUser && (
        <div className="fixed inset-0 bg-slate-500 bg-opacity-75 dark:bg-slate-900 dark:bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 w-full max-w-md">
            <h2 className="text-lg font-medium text-slate-900 dark:text-white mb-4">
              Change Role: {selectedUser.username}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Select new role
                </label>
                {USER_ROLES.map(role => (
                  <label key={role.value} className="flex items-start mb-3 cursor-pointer">
                    <input
                      type="radio"
                      value={role.value}
                      checked={selectedRole === role.value}
                      onChange={(e) => setSelectedRole(e.target.value)}
                      className="mt-1 h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300"
                    />
                    <div className="ml-3">
                      <span className="block text-sm font-medium text-slate-900 dark:text-white">
                        {role.label}
                      </span>
                      <span className="block text-xs text-slate-500 dark:text-slate-400">
                        {role.description}
                      </span>
                    </div>
                  </label>
                ))}
              </div>
              {selectedRole === 'admin' && selectedUser.type !== 'admin' && (
                <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-md">
                  <p className="text-sm text-amber-800 dark:text-amber-200">
                    <strong>Warning:</strong> Promoting to Admin grants full system access including the ability to delete users and servers.
                  </p>
                </div>
              )}
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => { setIsRoleModalOpen(false); setSelectedUser(null); setSelectedRole(''); }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateRole}
                disabled={updateRoleMutation.isLoading || selectedRole === selectedUser.type}
                className="btn btn-primary"
              >
                {updateRoleMutation.isLoading ? 'Updating...' : 'Update Role'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Permissions Modal */}
      {isPermissionsModalOpen && selectedUser && (
        <div className="fixed inset-0 bg-slate-500 bg-opacity-75 dark:bg-slate-900 dark:bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-medium text-slate-900 dark:text-white mb-4">
              Manage Permissions: {selectedUser.username}
            </h2>

            <div className="space-y-4">
              {servers.map((server) => {
                const hasPermission = hasPermissionForServer(server.id)
                const permission = getPermissionForServer(server.id)

                return (
                  <div key={server.id} className="border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h3 className="text-sm font-medium text-slate-900 dark:text-white">
                          {server.name}
                        </h3>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {server.type} Server
                        </p>
                      </div>
                      <button
                        onClick={() => toggleServerPermission(selectedUser, server)}
                        className={`px-3 py-1 rounded text-sm font-medium ${
                          hasPermission
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                            : 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300'
                        }`}
                      >
                        {hasPermission ? 'Enabled' : 'Disabled'}
                      </button>
                    </div>

                    {hasPermission && permission && (
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
                        <label className="flex items-center">
                          <input
                            type="checkbox"
                            checked={permission.can_view_sessions}
                            onChange={(e) => updatePermissionDetail(selectedUser, server, 'can_view_sessions', e.target.checked)}
                            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded"
                          />
                          <span className="ml-2 text-sm text-slate-700 dark:text-slate-300">View Sessions</span>
                        </label>

                        <label className="flex items-center">
                          <input
                            type="checkbox"
                            checked={permission.can_view_users}
                            onChange={(e) => updatePermissionDetail(selectedUser, server, 'can_view_users', e.target.checked)}
                            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded"
                          />
                          <span className="ml-2 text-sm text-slate-700 dark:text-slate-300">View Users</span>
                        </label>

                        <label className="flex items-center">
                          <input
                            type="checkbox"
                            checked={permission.can_view_analytics}
                            onChange={(e) => updatePermissionDetail(selectedUser, server, 'can_view_analytics', e.target.checked)}
                            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded"
                          />
                          <span className="ml-2 text-sm text-slate-700 dark:text-slate-300">View Analytics</span>
                        </label>

                        <label className="flex items-center">
                          <input
                            type="checkbox"
                            checked={permission.can_terminate_sessions}
                            onChange={(e) => updatePermissionDetail(selectedUser, server, 'can_terminate_sessions', e.target.checked)}
                            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded"
                          />
                          <span className="ml-2 text-sm text-slate-700 dark:text-slate-300">Terminate Sessions</span>
                        </label>

                        <label className="flex items-center">
                          <input
                            type="checkbox"
                            checked={permission.can_manage_server}
                            onChange={(e) => updatePermissionDetail(selectedUser, server, 'can_manage_server', e.target.checked)}
                            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded"
                          />
                          <span className="ml-2 text-sm text-slate-700 dark:text-slate-300">Manage Server</span>
                        </label>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => { setIsPermissionsModalOpen(false); setSelectedUser(null); }}
                className="btn btn-primary"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}