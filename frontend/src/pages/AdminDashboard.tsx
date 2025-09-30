import { Routes, Route } from 'react-router-dom'
import AdminHome from '../components/admin/AdminHome'
import UnifiedServerManagement from '../components/admin/UnifiedServerManagement'
import UsersList from '../components/admin/UsersList'
import LocalUsersManagement from '../components/admin/LocalUsersManagement'
import AuditLogs from '../components/admin/AuditLogs'
import Settings from '../components/admin/Settings'
import ErrorBoundary from '../components/ErrorBoundary'

export default function AdminDashboard() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<AdminHome />} />
      <Route path="/servers" element={<UnifiedServerManagement />} />
      <Route path="/users" element={<UsersList />} />
      <Route path="/local-users" element={<LocalUsersManagement />} />
      <Route path="/audit" element={<AuditLogs />} />
      <Route path="/settings" element={<Settings />} />
    </Routes>
    </ErrorBoundary>
  )
}