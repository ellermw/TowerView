import { Routes, Route } from 'react-router-dom'
import MediaUserHome from '../components/media/MediaUserHome'
import WatchHistory from '../components/media/WatchHistory'
import UserStats from '../components/media/UserStats'

export default function MediaUserDashboard() {
  return (
    <Routes>
      <Route path="/" element={<MediaUserHome />} />
      <Route path="/history" element={<WatchHistory />} />
      <Route path="/stats" element={<UserStats />} />
    </Routes>
  )
}