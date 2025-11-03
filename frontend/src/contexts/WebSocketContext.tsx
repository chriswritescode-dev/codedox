import { createContext, useContext, useEffect, useRef, useState, useCallback, ReactNode } from 'react'
import { getClientId } from '../lib/api'
import { WebSocketMessageType } from '../lib/websocketTypes'

interface WebSocketMessage {
  type: string
  [key: string]: any
}

interface WebSocketContextValue {
  isConnected: boolean
  sendMessage: (message: WebSocketMessage) => void
  subscribe: (jobId: string) => void
  unsubscribe: (jobId: string) => void
  addMessageListener: (listener: (message: WebSocketMessage) => void) => () => void
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

interface WebSocketProviderProps {
  children: ReactNode
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function WebSocketProvider({
  children,
  reconnectInterval = 5000,
  maxReconnectAttempts = 5,
}: WebSocketProviderProps) {
  const [isConnected, setIsConnected] = useState(false)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const isConnectingRef = useRef(false)
  const messageListenersRef = useRef<Set<(message: WebSocketMessage) => void>>(new Set())

  const connect = useCallback(() => {
    if (isConnectingRef.current || (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING)) {
      return
    }

    isConnectingRef.current = true

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const clientId = getClientId()
    const wsBase = import.meta.env.VITE_WS_URL || '/ws'
    const wsUrl = wsBase.startsWith('ws') 
      ? `${wsBase}/${clientId}` 
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${wsBase}/${clientId}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('Global WebSocket connected')
        setIsConnected(true)
        setReconnectAttempts(0)
        isConnectingRef.current = false
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          messageListenersRef.current.forEach(listener => listener(message))
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      ws.onerror = (error) => {
        console.error('Global WebSocket error:', error)
      }

      ws.onclose = () => {
        console.log('Global WebSocket disconnected')
        setIsConnected(false)
        wsRef.current = null
        isConnectingRef.current = false

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
      isConnectingRef.current = false
    }
  }, [reconnectInterval, maxReconnectAttempts, reconnectAttempts])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }, [])

  const subscribe = useCallback((jobId: string) => {
    sendMessage({ type: WebSocketMessageType.SUBSCRIBE, job_id: jobId })
  }, [sendMessage])

  const unsubscribe = useCallback((jobId: string) => {
    sendMessage({ type: WebSocketMessageType.UNSUBSCRIBE, job_id: jobId })
  }, [sendMessage])

  const addMessageListener = useCallback((listener: (message: WebSocketMessage) => void) => {
    messageListenersRef.current.add(listener)
    return () => {
      messageListenersRef.current.delete(listener)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [])

  const value: WebSocketContextValue = {
    isConnected,
    sendMessage,
    subscribe,
    unsubscribe,
    addMessageListener,
  }

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocketContext must be used within WebSocketProvider')
  }
  return context
}
