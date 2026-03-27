import { useRef, useState, useCallback, useEffect } from "react";

export interface WSMessage {
  type: string;
  text?: string;
  call_id?: string;
  name?: string;
  arguments?: Record<string, unknown>;
  result?: string;
  message?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  thinking_tokens?: number;
  cached_tokens?: number;
}

interface UseWebSocketReturn {
  messages: WSMessage[];
  sendMessage: (text: string) => void;
  sendToolConfirm: (callId: string, confirmed: boolean) => void;
  isConnected: boolean;
  clearMessages: () => void;
}

export default function useWebSocket(): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const pendingRef = useRef<string[]>([]);
  const cleanupRef = useRef(false);
  const retryRef = useRef(0);

  const connect = useCallback(() => {
    if (cleanupRef.current) return;
    const wsUrl = `ws://${window.location.host}/ws/chat`;
    console.log("[WS] connecting to", wsUrl);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] connected");
      setIsConnected(true);
      retryRef.current = 0;
      while (pendingRef.current.length > 0) {
        ws.send(pendingRef.current.shift()!);
      }
    };

    ws.onmessage = (event) => {
      try {
        const data: WSMessage = JSON.parse(event.data);
        setMessages((prev) => [...prev, data]);
      } catch {
        // ignore
      }
    };

    ws.onclose = (e) => {
      console.log("[WS] closed", e.code, e.reason);
      setIsConnected(false);
      wsRef.current = null;
      if (!cleanupRef.current) {
        const delay = Math.min(2000 * (retryRef.current + 1), 10000);
        retryRef.current += 1;
        console.log("[WS] reconnecting in", delay, "ms");
        setTimeout(connect, delay);
      }
    };

    ws.onerror = (e) => {
      console.log("[WS] error", e);
    };
  }, []);

  useEffect(() => {
    cleanupRef.current = false;
    connect();
    return () => {
      cleanupRef.current = true;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  const sendMessage = useCallback((text: string) => {
    const payload: Record<string, unknown> = { type: "chat", text };
    const raw = JSON.stringify(payload);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(raw);
    } else {
      console.log("[WS] queuing message, state:", wsRef.current?.readyState);
      pendingRef.current.push(raw);
    }
  }, []);

  const sendToolConfirm = useCallback((callId: string, confirmed: boolean) => {
    const raw = JSON.stringify({ type: "tool_confirm", call_id: callId, confirmed });
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(raw);
    } else {
      pendingRef.current.push(raw);
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, sendMessage, sendToolConfirm, isConnected, clearMessages };
}
