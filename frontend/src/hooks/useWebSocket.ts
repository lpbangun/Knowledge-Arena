import { useEffect, useRef, useCallback, useState } from 'react';
import type { WSEvent } from '../lib/types';

export function useWebSocket(debateId: string | undefined) {
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Map<string, ((data: unknown) => void)[]>>(new Map());
  const reconnectDelayRef = useRef(1000);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  useEffect(() => {
    if (!debateId) return;
    unmountedRef.current = false;

    function connect() {
      if (unmountedRef.current) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/debates/${debateId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectDelayRef.current = 1000;
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (!unmountedRef.current) {
          const delay = reconnectDelayRef.current;
          reconnectDelayRef.current = Math.min(delay * 2, 30000);
          reconnectTimerRef.current = setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        setConnected(false);
        ws.close();
      };

      ws.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data) as WSEvent;
          setEvents((prev) => [...prev.slice(-100), event]);
          const handlers = listenersRef.current.get(event.type);
          if (handlers) handlers.forEach((h) => h(event.data));
        } catch { /* ignore non-JSON */ }
      };
    }

    connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
    };
  }, [debateId]);

  const on = useCallback((eventType: string, handler: (data: unknown) => void) => {
    const current = listenersRef.current.get(eventType) ?? [];
    listenersRef.current.set(eventType, [...current, handler]);
    return () => {
      const updated = (listenersRef.current.get(eventType) ?? []).filter((h) => h !== handler);
      listenersRef.current.set(eventType, updated);
    };
  }, []);

  return { events, connected, on };
}
