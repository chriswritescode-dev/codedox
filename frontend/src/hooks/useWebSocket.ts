import { useEffect, useRef, useState, useCallback } from 'react'

interface WebSocketMessage {
  type: string
  [key: string]: any
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onError,
    onOpen,
    onClose,
    reconnectInterval = 5000,
    maxReconnectAttempts = 5,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    // Generate a unique client ID
    const clientId = `web-${Date.now()}-${Math.random()
      .toString(36)
      .substring(2, 15)}`;
    
    // Use environment variable with fallback
    const wsBase = import.meta.env.VITE_WS_URL || '/ws'
    const wsUrl = wsBase.startsWith('ws') 
      ? `${wsBase}/${clientId}` 
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${wsBase}/${clientId}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        setReconnectAttempts(0)
        onOpen?.()
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          onMessage?.(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        onError?.(error)
      }

      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setIsConnected(false)
        wsRef.current = null
        onClose?.()

        // Attempt to reconnect
        if (reconnectAttempts < maxReconnectAttempts) {
          console.log(`Reconnecting in ${reconnectInterval / 1000} seconds...`)
          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectAttempts((prev) => prev + 1)
            connect()
          }, reconnectInterval)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
    }
  }, [onMessage, onError, onOpen, onClose, reconnectInterval, maxReconnectAttempts, reconnectAttempts])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }, [])

  const subscribe = useCallback((jobId: string) => {
    sendMessage({ type: 'subscribe', job_id: jobId })
  }, [sendMessage])

  const unsubscribe = useCallback((jobId: string) => {
    sendMessage({ type: 'unsubscribe', job_id: jobId })
  }, [sendMessage])

  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [])

  return {
    isConnected,
    sendMessage,
    subscribe,
    unsubscribe,
    reconnectAttempts,
  }
}