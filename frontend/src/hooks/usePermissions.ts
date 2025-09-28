import { useEffect, useState, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import api from '../services/api'

export type Permission =
  | 'view_analytics'
  | 'view_sessions'
  | 'terminate_sessions'
  | 'view_users'
  | 'manage_users'
  | 'manage_servers'
  | 'view_audit_logs'
  | 'manage_settings'

interface UserPermissions {
  [key: string]: boolean
}

export function usePermissions() {
  const { user } = useAuthStore()
  const [permissions, setPermissions] = useState<UserPermissions>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchPermissions() {
      if (!user) {
        setPermissions({})
        setLoading(false)
        return
      }

      // Admin users have all permissions
      if (user.type === 'admin') {
        setPermissions({
          view_analytics: true,
          view_sessions: true,
          terminate_sessions: true,
          view_users: true,
          manage_users: true,
          manage_servers: true,
          view_audit_logs: true,
          manage_settings: true,
        })
        setLoading(false)
        return
      }

      // Staff and support users have permissions based on their server permissions
      if (user.type === 'local_user' || user.type === 'staff' || user.type === 'support') {
        try {
          // Get user's specific permissions
          const response = await api.get(`/admin/local-users/${user.id}/permissions`)
          const serverPermissions = response.data || []

          // Check if user has any permissions at all
          const hasAnyPermission = serverPermissions.length > 0
          const canViewUsers = serverPermissions.some((p: any) => p.can_view_users)
          const canManageServers = serverPermissions.some((p: any) => p.can_manage_server)

          const userPerms: UserPermissions = {
            view_analytics: hasAnyPermission,  // Can view dashboard if has any permission
            view_sessions: hasAnyPermission,    // Can view sessions if has any permission
            terminate_sessions: canManageServers, // Can terminate if can manage servers
            view_users: canViewUsers,           // Can view users based on permission
            manage_users: false,                // Local users can't manage users
            manage_servers: canManageServers,   // Can manage servers based on permission
            view_audit_logs: false,             // Only admin users can view audit logs
            manage_settings: false,             // Local users can't manage settings
          }

          setPermissions(userPerms)
        } catch (error) {
          console.error('Error fetching permissions:', error)
          // Set minimal permissions for dashboard access
          setPermissions({
            view_analytics: true,  // Always show dashboard
            view_sessions: true,   // Always allow viewing sessions
            view_users: false,
            terminate_sessions: false,
            manage_users: false,
            manage_servers: false,
            view_audit_logs: false,
            manage_settings: false,
          })
        }
        setLoading(false)
        return
      }

      // Media users only have limited permissions
      if (user.type === 'media_user') {
        setPermissions({
          view_analytics: true,    // Can view dashboard analytics
          view_sessions: true,     // Can view sessions on dashboard
          terminate_sessions: false,
          view_users: false,       // Cannot view users page
          manage_users: false,
          manage_servers: false,
          view_audit_logs: false,
          manage_settings: false,
        })
        setLoading(false)
        return
      }

      // Default: no permissions
      setPermissions({})
      setLoading(false)
    }

    fetchPermissions()
  }, [user])

  const hasPermission = useCallback((permission: Permission): boolean => {
    return permissions[permission] || false
  }, [permissions])

  const hasAnyPermission = useCallback((...perms: Permission[]): boolean => {
    return perms.some(perm => permissions[perm])
  }, [permissions])

  const hasAllPermissions = useCallback((...perms: Permission[]): boolean => {
    return perms.every(perm => permissions[perm])
  }, [permissions])

  return {
    permissions,
    loading,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    isAdmin: user?.type === 'admin',
    isLocalUser: user?.type === 'local_user' || user?.type === 'staff' || user?.type === 'support',
    isStaff: user?.type === 'staff' || user?.type === 'local_user',
    isSupport: user?.type === 'support',
    isMediaUser: user?.type === 'media_user',
  }
}