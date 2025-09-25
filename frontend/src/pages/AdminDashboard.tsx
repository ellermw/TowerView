import { Routes, Route } from 'react-router-dom'
import AdminHome from '../components/admin/AdminHome'
import ServerManagement from '../components/admin/ServerManagement'
import SessionsList from '../components/admin/SessionsList'
import UsersList from '../components/admin/UsersList'
import AuditLogs from '../components/admin/AuditLogs'

export default function AdminDashboard() {
  return (
    <Routes>
      <Route path="/" element={<AdminHome />} />
      <Route path="/servers" element={<ServerManagement />} />
      <Route path="/sessions" element={<SessionsList />} />
      <Route path="/users" element={<UsersList />} />
      <Route path="/audit" element={<AuditLogs />} />
    </Routes>
  )
}