import { useEffect, useRef, useCallback } from 'react'
import { CONFIG } from '../config'
import useSimStore from '../store/useSimStore'

export default function useWebSocket() {
  const ws = useRef(null)
  const reconnectTimer = useRef(null)
  const { handleWSMessage, setWsConnected } = useSimStore()

  const connect = useCallback(() => {
    // Clean up existing connection
    if (ws.current) {
      ws.current.onclose = null
      ws.current.close()
    }

    console.log('[WS] Connecting to:', CONFIG.WS_URL)
    ws.current = new WebSocket(CONFIG.WS_URL)

    ws.current.onopen = () => {
      console.log('[WS] Connected')
      setWsConnected(true)
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
    }

    ws.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type !== 'heartbeat') {
          handleWSMessage(msg)
        }
      } catch (e) {
        console.error('[WS] Parse error:', e)
      }
    }

    ws.current.onclose = () => {
      console.log('[WS] Disconnected — retrying in 3s')
      setWsConnected(false)
      // Auto-reconnect — NEVER pause the simulation on disconnect
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.current.onerror = (err) => {
      console.error('[WS] Error:', err)
    }
  }, [handleWSMessage, setWsConnected])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (ws.current) ws.current.close()
    }
  }, [connect])

  const send = useCallback((data) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data))
    }
  }, [])

  return { send }
}
