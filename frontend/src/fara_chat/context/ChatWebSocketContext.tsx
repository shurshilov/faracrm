import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  ReactNode,
} from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import { chatApi, WSMessage, WSNewMessage, Chat } from '@/services/api/chat';
import type { RootState } from '@/store/store';

interface ChatWebSocketContextValue {
  isConnected: boolean;
  subscribe: (chatId: number) => void;
  subscribeAll: (chatIds: number[]) => void;
  unsubscribe: (chatId: number) => void;
  sendTyping: (chatId: number) => void;
  sendRead: (chatId: number, messageId?: number) => void;
  addMessageListener: (listener: (message: WSMessage) => void) => () => void;
}

const ChatWebSocketContext = createContext<ChatWebSocketContextValue | null>(
  null,
);

interface ChatWebSocketProviderProps {
  children: ReactNode;
}

// Тип для события создания чата
interface WSChatCreated {
  type: 'chat_created';
  chat: Chat;
}

export function ChatWebSocketProvider({
  children,
}: ChatWebSocketProviderProps) {
  const dispatch = useDispatch();
  const session = useSelector((state: RootState) => state.auth.session);
  const token = session?.token || '';
  const currentUserId = session?.user_id?.id || 0;

  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isConnectingRef = useRef(false);
  const isMountedRef = useRef(true);

  // Список слушателей сообщений
  const messageListenersRef = useRef<Set<(message: WSMessage) => void>>(
    new Set(),
  );

  // Добавить слушателя
  const addMessageListener = useCallback(
    (listener: (message: WSMessage) => void) => {
      messageListenersRef.current.add(listener);
      return () => {
        messageListenersRef.current.delete(listener);
      };
    },
    [],
  );

  // Обработка входящих сообщений
  const handleMessage = useCallback(
    (message: WSMessage) => {
      console.log('WebSocket message:', message);

      // Уведомляем всех слушателей
      messageListenersRef.current.forEach(listener => {
        try {
          listener(message);
        } catch (e) {
          console.error('Error in message listener:', e);
        }
      });

      // Обработка нового чата
      if (message.type === 'chat_created') {
        const wsMsg = message as unknown as WSChatCreated;
        console.log('New chat created:', wsMsg.chat);

        // Добавляем чат в кэш и делаем refetch для получения полных данных
        dispatch(
          chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
            // Проверяем что чат ещё не добавлен
            if (!draft.data.find(c => c.id === wsMsg.chat.id)) {
              draft.data.unshift(wsMsg.chat);
            }
          }),
        );

        // Делаем refetch чтобы получить полные данные чата
        dispatch(chatApi.util.invalidateTags([{ type: 'Chat', id: 'LIST' }]));
      }

      // Глобальное обновление кэша RTK Query
      if (message.type === 'new_message') {
        const wsMsg = message as WSNewMessage;
        const isOwnMessage =
          wsMsg.message.author?.type === 'user' &&
          wsMsg.message.author?.id === currentUserId;

        if (wsMsg.chat_id) {
          // Обновляем базовый кэш чатов { limit: 100 } для ChatNotification
          dispatch(
            chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
              const chat = draft.data.find(c => c.id === wsMsg.chat_id);
              if (chat) {
                // Увеличиваем unread только если не своё сообщение
                if (!isOwnMessage) {
                  chat.unread_count = (chat.unread_count || 0) + 1;
                }
                chat.last_message = {
                  id: wsMsg.message.id,
                  body: wsMsg.message.body,
                  author_id: wsMsg.message.author?.id || 0,
                  create_date: wsMsg.message.create_date,
                };
                chat.last_message_date = wsMsg.message.create_date;
              }
            }),
          );

          // Добавляем сообщение в кэш сообщений чата
          // Это нужно чтобы сообщения появлялись когда ChatPage не открыт
          dispatch(
            chatApi.util.updateQueryData(
              'getChatMessages',
              { chatId: wsMsg.chat_id, limit: 50 },
              draft => {
                // Проверяем что сообщение ещё не добавлено
                if (!draft.data.find(m => m.id === wsMsg.message.id)) {
                  draft.data.unshift(wsMsg.message);
                }
              },
            ),
          );
        }
      }

      // Обработка messages_read:
      // - Если user_id === currentUserId - мы прочитали чат, сбрасываем unread_count в 0
      // - Если user_id !== currentUserId - кто-то прочитал наши сообщения, обновляем is_read
      if (message.type === 'messages_read') {
        const chatId = (message as any).chat_id;
        const userId = (message as any).user_id;

        if (chatId !== undefined) {
          // Если это мы прочитали - сбрасываем свой unread_count
          if (userId === currentUserId) {
            dispatch(
              chatApi.util.updateQueryData(
                'getChats',
                { limit: 100 },
                draft => {
                  const chat = draft.data.find(c => c.id === chatId);
                  if (chat) {
                    chat.unread_count = 0;
                  }
                },
              ),
            );
          }

          // Обновляем is_read для сообщений в кэше (кто-то прочитал наши сообщения)
          if (userId !== currentUserId) {
            dispatch(
              chatApi.util.updateQueryData(
                'getChatMessages',
                { chatId, limit: 50 },
                draft => {
                  draft.data.forEach(msg => {
                    // Помечаем наши сообщения как прочитанные
                    if (
                      msg.author?.type === 'user' &&
                      msg.author?.id === currentUserId
                    ) {
                      msg.is_read = true;
                    }
                  });
                },
              ),
            );
          }
        }
      }
    },
    [currentUserId, dispatch],
  );

  const connect = useCallback(() => {
    if (
      !token ||
      isConnectingRef.current ||
      wsRef.current?.readyState === WebSocket.OPEN
    ) {
      return;
    }

    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    isConnectingRef.current = true;

    const apiUrl = new URL(API_BASE_URL);
    const protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${apiUrl.host}/ws/chat?token=${token}`;

    console.log('ChatWebSocketProvider: Connecting to', wsUrl);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) {
          ws.close();
          return;
        }

        console.log('ChatWebSocketProvider: Connected');
        isConnectingRef.current = false;
        setIsConnected(true);

        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };

      ws.onclose = () => {
        console.log('ChatWebSocketProvider: Disconnected');
        isConnectingRef.current = false;
        setIsConnected(false);

        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        if (isMountedRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current) {
              connect();
            }
          }, 3000);
        }
      };

      ws.onerror = event => {
        console.error('ChatWebSocketProvider: Error', event);
        isConnectingRef.current = false;
      };

      ws.onmessage = event => {
        try {
          const data = JSON.parse(event.data) as WSMessage;
          if ((data as any).type === 'pong') {
            return;
          }
          handleMessage(data);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      isConnectingRef.current = false;
    }
  }, [token, handleMessage]);

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
      wsRef.current.onclose = null;
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
      sendMessage({ type: 'subscribe', chat_id: chatId });
    },
    [sendMessage],
  );

  const subscribeAll = useCallback(
    (chatIds: number[]) => {
      if (chatIds.length === 0) return;
      console.log(
        'ChatWebSocketProvider: Subscribing to',
        chatIds.length,
        'chats',
      );
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

  // Connect on mount
  useEffect(() => {
    isMountedRef.current = true;

    if (token) {
      connect();
    }

    return () => {
      isMountedRef.current = false;
      disconnect();
    };
  }, [token]);

  const value: ChatWebSocketContextValue = {
    isConnected,
    subscribe,
    subscribeAll,
    unsubscribe,
    sendTyping,
    sendRead,
    addMessageListener,
  };

  return (
    <ChatWebSocketContext.Provider value={value}>
      {children}
    </ChatWebSocketContext.Provider>
  );
}

export function useChatWebSocketContext() {
  const context = useContext(ChatWebSocketContext);
  if (!context) {
    throw new Error(
      'useChatWebSocketContext must be used within ChatWebSocketProvider',
    );
  }
  return context;
}

export default ChatWebSocketContext;
