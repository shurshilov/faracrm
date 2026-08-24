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
import {
  chatApi,
  WSMessage,
  WSNewMessage,
  WSReactionChanged,
  WSMessageEdited,
  WSMessageDeleted,
  WSMessagePinned,
} from '@/services/api/chat';
import type { RootState, AppDispatch } from '@/store/store';
import { logOut } from '@/slices/authSlice';

// Коды закрытия, означающие «сессии нет» — переподключение только плодит
// мусорные хендшейки. 1008 шлёт бэкенд (chat/routers/ws.py), 4001/4003/4401/
// 4403 — контракт до коммита 5e2fa46, оставлены для совместимости.
const AUTH_CLOSE_CODES = [1008, 4001, 4003, 4401, 4403];

interface ChatWebSocketContextValue {
  isConnected: boolean;
  subscribe: (chatId: number) => void;
  subscribeAll: (chatIds: number[]) => void;
  unsubscribe: (chatId: number) => void;
  sendTyping: (chatId: number) => void;
  sendRead: (chatId: number, messageId?: number) => void;
  addMessageListener: (listener: (message: WSMessage) => void) => () => void;
  onlineUsers: Set<number>;
  isUserOnline: (userId: number) => boolean;
  // Сырая отправка JSON-сообщения в WebSocket. Нужна для WebRTC-сигналинга
  // (call.offer, call.answer, call.ice) и future-команд, которым не хочется
  // заводить отдельный метод в провайдере.
  send: (message: object) => void;
}

const ChatWebSocketContext = createContext<ChatWebSocketContextValue | null>(
  null,
);

interface ChatWebSocketProviderProps {
  children: ReactNode;
}

export function ChatWebSocketProvider({
  children,
}: ChatWebSocketProviderProps) {
  const dispatch = useDispatch<AppDispatch>();
  const session = useSelector((state: RootState) => state.auth.session);
  const token = session?.token || '';
  const currentUserId = session?.user_id?.id || 0;

  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [onlineUsers, setOnlineUsers] = useState<Set<number>>(new Set());
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setTimeout> | null>(null);
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
      if ((message.type as string) === 'chat_created') {
        const chatId = (message as any).chat_id;
        console.log('New chat created:', chatId);

        // Мёржим онлайн-юзеров этого чата в общий onlineUsers
        const onlineFromEvent = (message as any).online_users as
          | number[]
          | undefined;
        if (onlineFromEvent?.length) {
          setOnlineUsers(prev => {
            const next = new Set(prev);
            for (const uid of onlineFromEvent) next.add(uid);
            return next;
          });
        }

        // Подписываемся на WS-события нового чата
        if (chatId && wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({ type: 'subscribe', chat_id: chatId }),
          );
        }

        // Refetch списка чатов чтобы получить полные данные
        dispatch(chatApi.util.invalidateTags([{ type: 'Chat', id: 'LIST' }]));
      }

      // Presence: add/remove по юзерам. Живёт в контексте, а не в ChatPage,
      // чтобы не терять первое событие до монтирования страницы чата.
      if (message.type === 'presence_update') {
        const add = (message as any).add as number[] | undefined;
        const remove = (message as any).remove as number[] | undefined;
        if ((add && add.length) || (remove && remove.length)) {
          setOnlineUsers(prev => {
            const next = new Set(prev);
            if (add) for (const uid of add) next.add(uid);
            if (remove) for (const uid of remove) next.delete(uid);
            return next;
          });
        }
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
                  create_datetime: wsMsg.message.create_datetime,
                };
                chat.last_message_date = wsMsg.message.create_datetime;
              }
            }),
          );

          // Обновляем счётчики непрочитанных у папок в сайдбаре (считаются
          // на бэке на лету). Только чужое сообщение меняет unread.
          if (!isOwnMessage) {
            dispatch(
              chatApi.util.invalidateTags([
                { type: 'Chat', id: 'FOLDER_UNREAD' },
              ]),
            );
          }

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
          // Панель чата партнёра рендерит тот же getChatMessages(chatId), что и
          // основной чат — отдельного feed-кэша больше нет (модель 1:1).
        }
      }

      // Обработка notification (системные уведомления, cron, активности)
      // Перечитываем список чатов чтобы обновить unread_count и last_message
      if ((message.type as string) === 'notification') {
        dispatch(
          chatApi.util.invalidateTags([
            { type: 'Chat', id: 'LIST' },
            { type: 'Chat', id: 'FOLDER_UNREAD' },
          ]),
        );
      }

      // Обработка messages_read:
      // В watermark-модели чтение = движение курсора пользователя в chat_member.
      // Мы не отслеживаем "кто именно прочитал каждое сообщение", поэтому
      // единственная реакция здесь — сбросить СВОЙ unread_count, когда
      // мы сами прочитали чат (с другого устройства/вкладки).
      if (message.type === 'messages_read') {
        const chatId = (message as any).chat_id;
        const userId = (message as any).user_id;

        if (chatId !== undefined && userId === currentUserId) {
          dispatch(
            chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
              const chat = draft.data.find(c => c.id === chatId);
              if (chat) {
                chat.unread_count = 0;
              }
            }),
          );
          // Мы сами прочитали чат → пересчитать бейджи папок.
          dispatch(
            chatApi.util.invalidateTags([
              { type: 'Chat', id: 'FOLDER_UNREAD' },
            ]),
          );
        }
      }

      // Обработка reaction_changed — обновляем реакции в кэше сообщений
      if (message.type === 'reaction_changed') {
        const wsMsg = message as WSReactionChanged;
        dispatch(
          chatApi.util.updateQueryData(
            'getChatMessages',
            { chatId: wsMsg.chat_id, limit: 50 },
            draft => {
              const msg = draft.data.find(m => m.id === wsMsg.message_id);
              if (msg) {
                msg.reactions = wsMsg.reactions;
              }
            },
          ),
        );
      }

      // Обработка message_edited — обновляем текст сообщения в кэше
      if (message.type === 'message_edited') {
        const wsMsg = message as WSMessageEdited;
        dispatch(
          chatApi.util.updateQueryData(
            'getChatMessages',
            { chatId: wsMsg.chat_id, limit: 50 },
            draft => {
              const msg = draft.data.find(m => m.id === wsMsg.message_id);
              if (msg) {
                msg.body = wsMsg.body;
                msg.is_edited = true;
              }
            },
          ),
        );
        // Обновляем last_message если это было последнее сообщение
        dispatch(
          chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
            const chat = draft.data.find(c => c.id === wsMsg.chat_id);
            if (chat && chat.last_message && chat.last_message.id === wsMsg.message_id) {
              chat.last_message.body = wsMsg.body;
            }
          }),
        );
      }

      // Обработка message_deleted — удаляем сообщение из кэша
      if (message.type === 'message_deleted') {
        const wsMsg = message as WSMessageDeleted;
        dispatch(
          chatApi.util.updateQueryData(
            'getChatMessages',
            { chatId: wsMsg.chat_id, limit: 50 },
            draft => {
              draft.data = draft.data.filter(m => m.id !== wsMsg.message_id);
            },
          ),
        );
        // Обновляем last_message в списке чатов — если удалённое сообщение было последним
        dispatch(
          chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
            const chat = draft.data.find(c => c.id === wsMsg.chat_id);
            if (chat && chat.last_message?.id === wsMsg.message_id) {
              chat.last_message = undefined as any;
            }
          }),
        );
      }

      // Обработка message_pinned — обновляем статус закрепления
      if (message.type === 'message_pinned') {
        const wsMsg = message as WSMessagePinned;
        dispatch(
          chatApi.util.updateQueryData(
            'getChatMessages',
            { chatId: wsMsg.chat_id, limit: 50 },
            draft => {
              const msg = draft.data.find(m => m.id === wsMsg.message_id);
              if (msg) {
                msg.pinned = wsMsg.pinned;
              }
            },
          ),
        );
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

    const apiUrl = new URL(API_BASE_URL, window.location.origin);
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

      ws.onclose = event => {
        console.log('ChatWebSocketProvider: Disconnected', event.code);
        isConnectingRef.current = false;
        setIsConnected(false);
        setOnlineUsers(new Set());

        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Сессии больше нет — переподключаться бессмысленно. Без этой ветки
        // вкладка долбилась в /ws/chat мёртвым токеном раз в 3 секунды вечно.
        // 1008 шлёт chat/routers/ws.py; 4001+ — прежний контракт бэкенда.
        if (AUTH_CLOSE_CODES.includes(event.code)) {
          // Разлогиниваем сами: обработчик 401 в baseQueryWithReauth сюда не
          // доберётся — фоновая вкладка REST-запросов не шлёт.
          console.warn('ChatWebSocketProvider: сессия недействительна, выходим');
          dispatch(logOut());
          return;
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
  }, [token, handleMessage, dispatch]);

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

  const isUserOnline = useCallback(
    (userId: number) => onlineUsers.has(userId),
    [onlineUsers],
  );

  const value: ChatWebSocketContextValue = {
    isConnected,
    subscribe,
    subscribeAll,
    unsubscribe,
    sendTyping,
    sendRead,
    addMessageListener,
    onlineUsers,
    isUserOnline,
    send: sendMessage,
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
