import { useEffect } from 'react'

export default function OAuthCallback() {
  useEffect(() => {
    // Close the window after a short delay to show the success message
    const timer = setTimeout(() => {
      window.close()
      // If window.close() doesn't work (some browsers block it), redirect to home
      setTimeout(() => {
        window.location.href = '/'
      }, 1000)
    }, 2000)

    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
      <div className="text-center">
        <div className="mb-4">
          <svg
            className="mx-auto h-16 w-16 text-green-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
          Authentication Successful!
        </h2>
        <p className="text-slate-600 dark:text-slate-400">
          This window will close automatically...
        </p>
        <p className="text-sm text-slate-500 dark:text-slate-500 mt-4">
          If the window doesn't close, you can safely close it manually.
        </p>
      </div>
    </div>
  )
}
