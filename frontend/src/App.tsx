import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import LoginPage from './pages/LoginPage'
import AdminDashboard from './pages/AdminDashboard'
import OAuthCallback from './pages/OAuthCallback'
import Layout from './components/Layout'

function App() {
  const { isAuthenticated } = useAuthStore()

  // OAuth callback route should be accessible without authentication
  return (
    <Routes>
      <Route path="/oauth/callback" element={<OAuthCallback />} />
      <Route path="/*" element={isAuthenticated ? <AuthenticatedRoutes /> : <LoginPage />} />
    </Routes>
  )
}

function AuthenticatedRoutes() {
  return (
    <Layout>
      <Routes>
        <Route
          path="/"
          element={<Navigate to="/admin" replace />}
        />
        <Route path="/admin/*" element={<AdminDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

export default App
