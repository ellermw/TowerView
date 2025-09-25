import { useState, useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'

interface MetricsData {
  server_id: number
  cpu_usage: number
  memory_usage: number
  memory_used_gb: number
  memory_total_gb: number
  container?: string
  timestamp?: string
  gpu?: {
    available: boolean
    gpu_usage?: number
    render_usage?: number
    video_usage?: number
  }
}

interface UseWebSocketMetricsOptions {
  serverIds: number[]
  enabled?: boolean
  onError?: (error: Error) => void
}

export function useWebSocketMetrics({
  serverIds,
  enabled = true,
  onError
}: UseWebSocketMetricsOptions) {
  const [metrics, setMetrics] = useState<Record<number, MetricsData>>({})
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()
  const reconnectAttemptsRef = useRef(0)
  const { token } = useAuthStore()

  const connect = useCallback(() => {
    if (!enabled || !token || serverIds.length === 0) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    if (isConnecting) return

    setIsConnecting(true)

    try {
      // Build WebSocket URL
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsHost = window.location.hostname

      // Try different ports based on environment
      let wsUrl: string
      if (window.location.port === '8080') {
        // Through nginx on port 8080
        wsUrl = `${wsProtocol}//${wsHost}:8080/api/ws/metrics`
      } else if (window.location.port === '80' || window.location.port === '') {
        // Through nginx on port 80
        wsUrl = `${wsProtocol}//${wsHost}/api/ws/metrics`
      } else if (window.location.port === '3002') {
        // Development - try direct connection to backend
        wsUrl = `${wsProtocol}//${wsHost}:8000/api/ws/metrics`
      } else {
        // Direct connection to backend
        wsUrl = `${wsProtocol}//${wsHost}:8000/api/ws/metrics`
      }

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected, sending auth...')
        setIsConnecting(false)

        // Send authentication and server list as first message
        ws.send(JSON.stringify({
          token: token,
          servers: serverIds
        }))

        setIsConnected(true)
        reconnectAttemptsRef.current = 0
        console.log('WebSocket authenticated and ready')
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)

          if (message.type === 'metrics_update' && message.data) {
            // Update metrics state with new data
            const newMetrics: Record<number, MetricsData> = {}
            message.data.forEach((serverMetrics: MetricsData) => {
              if (serverMetrics.server_id) {
                newMetrics[serverMetrics.server_id] = serverMetrics
              }
            })
            setMetrics(newMetrics)
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        if (onError) {
          onError(new Error('WebSocket connection error'))
        }
      }

      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setIsConnected(false)
        setIsConnecting(false)
        wsRef.current = null

        // Don't auto-reconnect - let the user control when to retry
        console.log('WebSocket disconnected. Attempts:', reconnectAttemptsRef.current)
        if (reconnectAttemptsRef.current > 0) {
          console.log('WebSocket connection failed after retry')
        }
      }
    } catch (error) {
      console.error('Error creating WebSocket:', error)
      setIsConnecting(false)
      if (onError) {
        onError(error as Error)
      }
    }
  }, [enabled, token, serverIds, onError])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setIsConnected(false)
    setIsConnecting(false)
  }, [])

  // Update subscription when server list changes
  const updateSubscription = useCallback((newServerIds: number[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'subscribe',
        servers: newServerIds
      }))
    }
  }, [])

  // Connect/disconnect based on enabled state
  useEffect(() => {
    if (enabled) {
      connect()
    } else {
      disconnect()
    }

    return () => {
      disconnect()
    }
  }, [enabled]) // Remove connect and disconnect from deps to prevent loops

  // Update subscription when serverIds change
  useEffect(() => {
    if (isConnected && serverIds.length > 0) {
      updateSubscription(serverIds)
    }
  }, [serverIds, isConnected, updateSubscription])

  // Send periodic ping to keep connection alive
  useEffect(() => {
    if (!isConnected) return

    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000) // Ping every 30 seconds

    return () => clearInterval(pingInterval)
  }, [isConnected])

  return {
    metrics,
    isConnected,
    isConnecting,
    reconnect: connect
  }
}