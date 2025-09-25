import { useEffect, useState } from 'react'
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

      // Local users need to fetch their permissions
      if (user.type === 'local_user') {
        try {
          const response = await api.get(`/admin/local-users/${user.id}/permissions`)
          const userPerms: UserPermissions = {}

          // Convert array of permissions to object
          if (response.data && Array.isArray(response.data)) {
            response.data.forEach((perm: string) => {
              userPerms[perm] = true
            })
          }

          setPermissions(userPerms)
        } catch (error) {
          console.error('Error fetching permissions:', error)
          setPermissions({})
        }
        setLoading(false)
        return
      }

      // Media users have no admin permissions
      setPermissions({})
      setLoading(false)
    }

    fetchPermissions()
  }, [user])

  const hasPermission = (permission: Permission): boolean => {
    return permissions[permission] || false
  }

  const hasAnyPermission = (...perms: Permission[]): boolean => {
    return perms.some(perm => permissions[perm])
  }

  const hasAllPermissions = (...perms: Permission[]): boolean => {
    return perms.every(perm => permissions[perm])
  }

  return {
    permissions,
    loading,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    isAdmin: user?.type === 'admin',
    isLocalUser: user?.type === 'local_user',
    isMediaUser: user?.type === 'media_user',
  }
}