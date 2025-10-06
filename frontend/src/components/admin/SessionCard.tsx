import React from 'react'
import {
  PlayIcon,
  PauseIcon,
  FilmIcon,
  TvIcon,
  UserIcon,
  DevicePhoneMobileIcon,
  SignalIcon,
  CpuChipIcon,
  XMarkIcon,
  ArrowDownTrayIcon,
  ComputerDesktopIcon
} from '@heroicons/react/24/outline'

interface SessionCardProps {
  session: any
  onTerminate: () => void
  canTerminate: boolean
}

export default function SessionCard({ session, onTerminate, canTerminate }: SessionCardProps) {
  const isEpisode = session.media_type === 'episode'
  const posterUrl = isEpisode ? session.grandparent_thumb : session.thumb

  const formatTime = (ms: number) => {
    const totalSeconds = Math.floor(ms / 1000)
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = totalSeconds % 60

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
    }
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  const getPlayStateIcon = () => {
    if (session.state === 'playing') {
      return <PlayIcon className="h-4 w-4 text-green-500" />
    } else if (session.state === 'paused') {
      return <PauseIcon className="h-4 w-4 text-yellow-500" />
    }
    return <SignalIcon className="h-4 w-4 text-slate-400" />
  }

  const getQualityBadges = () => {
    const badges = []
    if (session.is_4k) badges.push({ text: '4K', color: 'bg-purple-500' })
    if (session.is_dolby_vision) badges.push({ text: 'DV', color: 'bg-pink-500' })
    else if (session.is_hdr) badges.push({ text: 'HDR', color: 'bg-amber-500' })

    if (session.video_decision === 'transcode') {
      badges.push({ text: 'TC', color: 'bg-red-500' })
    } else if (session.video_decision === 'copy' || session.video_decision === 'directstream') {
      badges.push({ text: 'DS', color: 'bg-blue-500' })
    } else if (session.video_decision === 'directplay') {
      badges.push({ text: 'DP', color: 'bg-green-500' })
    }

    return badges
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg shadow-lg overflow-hidden hover:shadow-xl transition-shadow duration-200">
      <div className="flex">
        {/* Poster */}
        <div className="w-32 h-48 flex-shrink-0 bg-slate-200 dark:bg-slate-700 relative">
          {posterUrl ? (
            <img
              src={posterUrl}
              alt={session.title}
              className="w-full h-full object-cover"
              onError={(e) => {
                e.currentTarget.style.display = 'none'
                e.currentTarget.nextElementSibling?.classList.remove('hidden')
              }}
            />
          ) : null}
          <div className={`${posterUrl ? 'hidden' : ''} absolute inset-0 flex items-center justify-center`}>
            {isEpisode ? (
              <TvIcon className="h-12 w-12 text-slate-400" />
            ) : (
              <FilmIcon className="h-12 w-12 text-slate-400" />
            )}
          </div>

          {/* Quality Badges - Overlaid on poster */}
          <div className="absolute top-2 left-2 flex flex-wrap gap-1">
            {getQualityBadges().map((badge, idx) => (
              <span
                key={idx}
                className={`${badge.color} text-white text-xs font-bold px-2 py-0.5 rounded`}
              >
                {badge.text}
              </span>
            ))}
          </div>

          {/* Play state indicator */}
          <div className="absolute bottom-2 right-2 bg-black bg-opacity-60 rounded-full p-1">
            {getPlayStateIcon()}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-4 min-w-0">
          <div className="flex justify-between items-start mb-2">
            <div className="flex-1 min-w-0">
              {/* Title */}
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white truncate">
                {session.title}
              </h3>

              {/* Subtitle for episodes */}
              {isEpisode && (
                <p className="text-sm text-slate-600 dark:text-slate-400 truncate">
                  {session.grandparent_title}
                  {session.parent_title && ` - ${session.parent_title}`}
                  {session.episode_number && ` - Episode ${session.episode_number}`}
                </p>
              )}

              {/* Year for movies */}
              {!isEpisode && session.year && (
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  {session.year}
                </p>
              )}
            </div>

            {/* Terminate button */}
            {canTerminate && (
              <button
                onClick={onTerminate}
                className="ml-2 p-1.5 text-slate-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                title="Terminate session"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            )}
          </div>

          {/* User & Device */}
          <div className="flex items-center gap-4 mb-3 text-sm">
            <div className="flex items-center text-slate-700 dark:text-slate-300">
              <UserIcon className="h-4 w-4 mr-1.5 text-slate-400" />
              <span className="truncate">{session.username || 'Unknown'}</span>
            </div>
            <div className="flex items-center text-slate-700 dark:text-slate-300">
              <DevicePhoneMobileIcon className="h-4 w-4 mr-1.5 text-slate-400" />
              <span className="truncate">{session.device || 'Unknown Device'}</span>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mb-2">
            <div className="flex justify-between text-xs text-slate-600 dark:text-slate-400 mb-1">
              <span>{formatTime(session.progress_ms)}</span>
              <span>{formatTime(session.duration_ms)}</span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, session.progress_percent || 0)}%` }}
              />
            </div>
          </div>

          {/* Stream Info */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center text-slate-600 dark:text-slate-400">
              <SignalIcon className="h-3.5 w-3.5 mr-1" />
              <span>{session.original_resolution || 'Unknown'}</span>
              {session.stream_resolution && session.video_decision === 'transcode' && (
                <span className="ml-1 text-red-600 dark:text-red-400">→ {session.stream_resolution}</span>
              )}
            </div>
            {session.session_bandwidth && (
              <div className="flex items-center text-slate-600 dark:text-slate-400">
                <ArrowDownTrayIcon className="h-3.5 w-3.5 mr-1" />
                <span>{Math.round(parseInt(session.session_bandwidth) / 1000)} Mbps</span>
              </div>
            )}
            {session.transcode_hw_decode && (
              <div className="flex items-center text-green-600 dark:text-green-400">
                <CpuChipIcon className="h-3.5 w-3.5 mr-1" />
                <span>HW Transcode</span>
              </div>
            )}
            {session.location && (
              <div className="flex items-center text-slate-600 dark:text-slate-400">
                <ComputerDesktopIcon className="h-3.5 w-3.5 mr-1" />
                <span className="capitalize">{session.location}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
