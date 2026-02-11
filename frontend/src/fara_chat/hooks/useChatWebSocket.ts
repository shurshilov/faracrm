import { useEffect, useRef, useCallback, useState } from 'react';
import { WSMessage } from '@/services/api/chat';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';

interface UseChatWebSocketOptions {
  token: string;
  onMessage?: (message: WSMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface UseChatWebSocketReturn {
  isConnected: boolean;
  subscribe: (chatId: number) => void;
  subscribeAll: (chatIds: number[]) => void;
  unsubscribe: (chatId: number) => void;
  sendTyping: (chatId: number) => void;
  sendRead: (chatId: number, messageId?: number) => void;
}

export function useChatWebSocket({
  token,
  onMessage,
  onConnect,
  onDisconnect,
  onError,
}: UseChatWebSocketOptions): UseChatWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isConnectingRef = useRef(false);
  const isMountedRef = useRef(true);

  // Store callbacks in refs to avoid dependency issues
  const onMessageRef = useRef(onMessage);
  const onConnectRef = useRef(onConnect);
  const onDisconnectRef = useRef(onDisconnect);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onConnectRef.current = onConnect;
    onDisconnectRef.current = onDisconnect;
    onErrorRef.current = onError;
  }, [onMessage, onConnect, onDisconnect, onError]);

  const connect = useCallback(() => {
    // Prevent multiple simultaneous connection attempts
    if (
      isConnectingRef.current ||
      wsRef.current?.readyState === WebSocket.OPEN
    ) {
      return;
    }

    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.onclose = null; // Prevent reconnect loop
      wsRef.current.close();
      wsRef.current = null;
    }

    isConnectingRef.current = true;

    // Determine WebSocket URL from API_BASE_URL
    const apiUrl = new URL(API_BASE_URL, window.location.origin);
    const protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${apiUrl.host}/ws/chat?token=${token}`;

    console.log('Connecting to WebSocket:', wsUrl);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) {
          ws.close();
          return;
        }

        console.log('Chat WebSocket connected');
        isConnectingRef.current = false;
        setIsConnected(true);
        onConnectRef.current?.();

        // Start ping interval
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };

      ws.onclose = () => {
        console.log('Chat WebSocket disconnected');
        isConnectingRef.current = false;
        setIsConnected(false);
        onDisconnectRef.current?.();

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Reconnect after delay only if still mounted
        if (isMountedRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current) {
              connect();
            }
          }, 3000);
        }
      };

      ws.onerror = event => {
        console.error('Chat WebSocket error:', event);
        isConnectingRef.current = false;
        onErrorRef.current?.(event);
      };

      ws.onmessage = event => {
        try {
          const data = JSON.parse(event.data) as WSMessage;
          console.log('WebSocket raw message:', data);

          // Ignore pong messages
          if ((data as any).type === 'pong') {
            return;
          }

          onMessageRef.current?.(data);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      isConnectingRef.current = false;
    }
  }, [token]); // Only depend on token

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.onclose = null; // Prevent reconnect
      wsRef.current.close();
      wsRef.current = null;
    }

    isConnectingRef.current = false;
  }, []);

  const sendMessage = useCallback((message: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const subscribe = useCallback(
    (chatId: number) => {
      console.log('Subscribing to chat:', chatId);
      sendMessage({ type: 'subscribe', chat_id: chatId });
    },
    [sendMessage],
  );

  const subscribeAll = useCallback(
    (chatIds: number[]) => {
      if (chatIds.length === 0) return;
      console.log('Subscribing to all chats:', chatIds.length);
      sendMessage({ type: 'subscribe_all', chat_ids: chatIds });
    },
    [sendMessage],
  );

  const unsubscribe = useCallback(
    (chatId: number) => {
      sendMessage({ type: 'unsubscribe', chat_id: chatId });
    },
    [sendMessage],
  );

  const sendTyping = useCallback(
    (chatId: number) => {
      sendMessage({ type: 'typing', chat_id: chatId });
    },
    [sendMessage],
  );

  const sendRead = useCallback(
    (chatId: number, messageId?: number) => {
      sendMessage({ type: 'read', chat_id: chatId, message_id: messageId });
    },
    [sendMessage],
  );

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    isMountedRef.current = true;

    if (token) {
      connect();
    }

    return () => {
      isMountedRef.current = false;
      disconnect();
    };
  }, [token]); // Remove connect/disconnect from deps to prevent loops

  return {
    isConnected,
    subscribe,
    subscribeAll,
    unsubscribe,
    sendTyping,
    sendRead,
  };
}

export default useChatWebSocket;
