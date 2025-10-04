import { Fragment, useState, useEffect } from 'react'
import { useLocation, Link } from 'react-router-dom'
import { Disclosure, Menu, Transition } from '@headlessui/react'
import { Bars3Icon, XMarkIcon, UserIcon, KeyIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import { useAuthStore } from '../store/authStore'
import { classNames } from '../utils/classNames'
import ChangePasswordModal from './ChangePasswordModal'
import { usePermissions } from '../hooks/usePermissions'
import { useQuery } from 'react-query'
import api from '../services/api'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { user, logout } = useAuthStore()
  const location = useLocation()
  const [showChangePassword, setShowChangePassword] = useState(false)
  const { hasPermission, isAdmin, isLocalUser, isMediaUser } = usePermissions()
  const [navigation, setNavigation] = useState<Array<{ name: string; href: string }>>([])

  // Fetch site settings
  const { data: siteSettings } = useQuery(
    'site-settings',
    () => api.get('/settings/site').then(res => res.data),
    {
      staleTime: 5 * 60 * 1000, // Cache for 5 minutes
      cacheTime: 10 * 60 * 1000,
    }
  )

  const siteName = siteSettings?.site_name || localStorage.getItem('siteName') || 'The Tower - View'

  const isCurrentPath = (href: string) => {
    // Exact match for root paths
    if (href === '/admin' || href === '/dashboard') {
      return location.pathname === href
    }
    // Prefix match for sub-paths
    return location.pathname.startsWith(href)
  }

  // Build management menu items
  const [managementItems, setManagementItems] = useState<Array<{ name: string; href: string }>>([])

  // Build navigation based on user type and permissions
  useEffect(() => {
    const nav = []
    const management = []

    // Dashboard is always visible for authenticated users
    nav.push({ name: 'Dashboard', href: '/admin' })

    // Media users only see dashboard - no management items
    if (isMediaUser) {
      // Media users don't get any management menu items
      // They can only see the dashboard
    } else if (isAdmin || isLocalUser) {
      // Management menu items for admin and staff/support users
      // Servers - visible to all but functionality limited by manage_servers permission
      management.push({ name: 'Servers', href: '/admin/servers' })

      // Users - requires view_users permission
      if (isAdmin || hasPermission('view_users')) {
        management.push({ name: 'Users', href: '/admin/users' })
      }

      // System Users - all system users can view (admin, staff, support)
      // Media users cannot see this page
      if (isAdmin || isLocalUser) {
        management.push({ name: 'System Users', href: '/admin/local-users' })
      }

      // Audit Logs - requires view_audit_logs permission
      if (isAdmin || hasPermission('view_audit_logs')) {
        nav.push({ name: 'Audit Logs', href: '/admin/audit' })
      }

      // Settings - requires manage_settings permission
      if (isAdmin || hasPermission('manage_settings')) {
        nav.push({ name: 'Settings', href: '/admin/settings' })
      }
    }

    setNavigation(nav)
    setManagementItems(management)
  }, [isAdmin, isLocalUser, isMediaUser, hasPermission])

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <Disclosure as="nav" className="bg-white dark:bg-slate-800 shadow">
        {({ open }) => (
          <>
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between h-16">
                <div className="flex">
                  <div className="flex-shrink-0 flex items-center">
                    <h1 className="text-xl font-bold text-slate-900 dark:text-white">
                      {siteName}
                    </h1>
                  </div>
                  <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                    {/* Dashboard link */}
                    {navigation.filter(item => item.name === 'Dashboard').map((item) => (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={classNames(
                          isCurrentPath(item.href)
                            ? 'border-primary-500 text-slate-900 dark:text-white'
                            : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:text-slate-300 dark:hover:text-white',
                          'inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium'
                        )}
                      >
                        {item.name}
                      </Link>
                    ))}

                    {/* Management Dropdown - now after Dashboard */}
                    {managementItems.length > 0 && (
                      <Menu as="div" className="relative inline-flex">
                        <Menu.Button className={classNames(
                          managementItems.some(item => isCurrentPath(item.href))
                            ? 'border-primary-500 text-slate-900 dark:text-white'
                            : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:text-slate-300 dark:hover:text-white',
                          'inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium h-full'
                        )}>
                          Management
                          <ChevronDownIcon className="ml-1 h-4 w-4" />
                        </Menu.Button>

                        <Transition
                          as={Fragment}
                          enter="transition ease-out duration-100"
                          enterFrom="transform opacity-0 scale-95"
                          enterTo="transform opacity-100 scale-100"
                          leave="transition ease-in duration-75"
                          leaveFrom="transform opacity-100 scale-100"
                          leaveTo="transform opacity-0 scale-95"
                        >
                          <Menu.Items className="absolute left-0 top-full mt-2 w-48 origin-top-left rounded-md bg-white dark:bg-slate-800 py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-50">
                            {managementItems.map((item) => (
                              <Menu.Item key={item.name}>
                                {({ active }) => (
                                  <Link
                                    to={item.href}
                                    className={classNames(
                                      active ? 'bg-slate-100 dark:bg-slate-700' : '',
                                      isCurrentPath(item.href) ? 'text-indigo-600 dark:text-indigo-400 font-semibold' : 'text-slate-700 dark:text-slate-300',
                                      'block px-4 py-2 text-sm'
                                    )}
                                  >
                                    {item.name}
                                  </Link>
                                )}
                              </Menu.Item>
                            ))}
                          </Menu.Items>
                        </Transition>
                      </Menu>
                    )}

                    {/* Other navigation items (Audit Logs, Settings) */}
                    {navigation.filter(item => item.name !== 'Dashboard').map((item) => (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={classNames(
                          isCurrentPath(item.href)
                            ? 'border-primary-500 text-slate-900 dark:text-white'
                            : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:text-slate-300 dark:hover:text-white',
                          'inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium'
                        )}
                      >
                        {item.name}
                      </Link>
                    ))}
                  </div>
                </div>
                <div className="hidden sm:ml-6 sm:flex sm:items-center">
                  <Menu as="div" className="ml-3 relative">
                    <div>
                      <Menu.Button className="bg-white dark:bg-slate-700 flex text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500">
                        <span className="sr-only">Open user menu</span>
                        <div className="h-8 w-8 rounded-full bg-slate-300 dark:bg-slate-600 flex items-center justify-center">
                          <UserIcon className="h-5 w-5 text-slate-600 dark:text-slate-300" />
                        </div>
                      </Menu.Button>
                    </div>
                    <Transition
                      as={Fragment}
                      enter="transition ease-out duration-200"
                      enterFrom="transform opacity-0 scale-95"
                      enterTo="transform opacity-100 scale-100"
                      leave="transition ease-in duration-75"
                      leaveFrom="transform opacity-100 scale-100"
                      leaveTo="transform opacity-0 scale-95"
                    >
                      <Menu.Items className="origin-top-right absolute right-0 mt-2 w-48 rounded-md shadow-lg py-1 bg-white dark:bg-slate-700 ring-1 ring-black ring-opacity-5 focus:outline-none">
                        <div className="px-4 py-2 text-sm text-slate-700 dark:text-slate-300 border-b border-slate-100 dark:border-slate-600">
                          {user?.username}
                          <div className="text-xs text-slate-500 dark:text-slate-400">
                            {user?.type === 'admin' ? 'Administrator' :
                             user?.type === 'media_user' ? 'Media User' :
                             user?.type === 'staff' ? 'Staff' :
                             user?.type === 'support' ? 'Support' : 'Local User'}
                          </div>
                        </div>
                        <Menu.Item>
                          {({ active }) => (
                            <button
                              onClick={() => setShowChangePassword(true)}
                              className={classNames(
                                active ? 'bg-slate-100 dark:bg-slate-600' : '',
                                'block w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-300'
                              )}
                            >
                              <div className="flex items-center">
                                <KeyIcon className="h-4 w-4 mr-2" />
                                Change Password
                              </div>
                            </button>
                          )}
                        </Menu.Item>
                        <Menu.Item>
                          {({ active }) => (
                            <button
                              onClick={logout}
                              className={classNames(
                                active ? 'bg-slate-100 dark:bg-slate-600' : '',
                                'block w-full text-left px-4 py-2 text-sm text-slate-700 dark:text-slate-300'
                              )}
                            >
                              Sign out
                            </button>
                          )}
                        </Menu.Item>
                      </Menu.Items>
                    </Transition>
                  </Menu>
                </div>
                <div className="-mr-2 flex items-center sm:hidden">
                  <Disclosure.Button className="bg-white dark:bg-slate-800 inline-flex items-center justify-center p-2 rounded-md text-slate-400 hover:text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-500">
                    <span className="sr-only">Open main menu</span>
                    {open ? (
                      <XMarkIcon className="block h-6 w-6" aria-hidden="true" />
                    ) : (
                      <Bars3Icon className="block h-6 w-6" aria-hidden="true" />
                    )}
                  </Disclosure.Button>
                </div>
              </div>
            </div>

            <Disclosure.Panel className="sm:hidden">
              <div className="pt-2 pb-3 space-y-1">
                {/* Dashboard first */}
                {navigation.filter(item => item.name === 'Dashboard').map((item) => (
                  <Disclosure.Button
                    key={item.name}
                    as={Link}
                    to={item.href}
                    className={classNames(
                      isCurrentPath(item.href)
                        ? 'bg-primary-50 border-primary-500 text-primary-700 dark:bg-slate-700 dark:text-white'
                        : 'border-transparent text-slate-600 hover:bg-slate-50 hover:border-slate-300 hover:text-slate-800 dark:text-slate-300 dark:hover:bg-slate-700',
                      'block pl-3 pr-4 py-2 border-l-4 text-base font-medium'
                    )}
                  >
                    {item.name}
                  </Disclosure.Button>
                ))}

                {/* Management section for mobile */}
                {managementItems.length > 0 && (
                  <>
                    <div className="px-3 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Management
                    </div>
                    {managementItems.map((item) => (
                      <Disclosure.Button
                        key={item.name}
                        as={Link}
                        to={item.href}
                        className={classNames(
                          isCurrentPath(item.href)
                            ? 'bg-primary-50 border-primary-500 text-primary-700 dark:bg-slate-700 dark:text-white'
                            : 'border-transparent text-slate-600 hover:bg-slate-50 hover:border-slate-300 hover:text-slate-800 dark:text-slate-300 dark:hover:bg-slate-700',
                          'block pl-6 pr-4 py-2 border-l-4 text-base font-medium'
                        )}
                      >
                        {item.name}
                      </Disclosure.Button>
                    ))}
                  </>
                )}

                {/* Other navigation items (Audit Logs, Settings) */}
                {navigation.filter(item => item.name !== 'Dashboard').map((item) => (
                  <Disclosure.Button
                    key={item.name}
                    as={Link}
                    to={item.href}
                    className={classNames(
                      isCurrentPath(item.href)
                        ? 'bg-primary-50 border-primary-500 text-primary-700 dark:bg-slate-700 dark:text-white'
                        : 'border-transparent text-slate-600 hover:bg-slate-50 hover:border-slate-300 hover:text-slate-800 dark:text-slate-300 dark:hover:bg-slate-700',
                      'block pl-3 pr-4 py-2 border-l-4 text-base font-medium'
                    )}
                  >
                    {item.name}
                  </Disclosure.Button>
                ))}
              </div>
              <div className="pt-4 pb-3 border-t border-slate-200 dark:border-slate-700">
                <div className="flex items-center px-4">
                  <div className="flex-shrink-0">
                    <div className="h-10 w-10 rounded-full bg-slate-300 dark:bg-slate-600 flex items-center justify-center">
                      <UserIcon className="h-6 w-6 text-slate-600 dark:text-slate-300" />
                    </div>
                  </div>
                  <div className="ml-3">
                    <div className="text-base font-medium text-slate-800 dark:text-white">
                      {user?.username}
                    </div>
                    <div className="text-sm font-medium text-slate-500 dark:text-slate-400">
                      {user?.type === 'admin' ? 'Administrator' :
                       user?.type === 'media_user' ? 'Media User' :
                       user?.type === 'staff' ? 'Staff' :
                       user?.type === 'support' ? 'Support' : 'Local User'}
                    </div>
                  </div>
                </div>
                <div className="mt-3 space-y-1">
                  <button
                    onClick={() => setShowChangePassword(true)}
                    className="block w-full text-left px-4 py-2 text-base font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-700"
                  >
                    <div className="flex items-center">
                      <KeyIcon className="h-5 w-5 mr-2" />
                      Change Password
                    </div>
                  </button>
                  <button
                    onClick={logout}
                    className="block w-full text-left px-4 py-2 text-base font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-700"
                  >
                    Sign out
                  </button>
                </div>
              </div>
            </Disclosure.Panel>
          </>
        )}
      </Disclosure>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {children}
      </main>

      <ChangePasswordModal
        isOpen={showChangePassword}
        onClose={() => setShowChangePassword(false)}
      />
    </div>
  )
}