import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Box,
  Text,
  Stack,
  Center,
  Modal,
  Paper,
  ScrollArea,
} from '@mantine/core';
import { IconMessageCircle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import {
  Chat,
  ChatMessage,
  WSMessage,
  WSNewMessage,
  chatApi,
  useMarkChatAsReadMutation,
  useGetChatsQuery,
  useGetPinnedMessagesQuery,
  useGetChatConnectorsQuery,
} from '@/services/api/chat';
import { useChatWebSocketContext } from '../context';
import { ChatList } from './ChatList';
import { ChatHeader } from './ChatHeader';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { NewChatModal } from './NewChatModal';
import { ChatSettingsModal } from './ChatSettingsModal';
import styles from './ChatPage.module.css';
import { useDispatch } from 'react-redux';

interface ChatPageProps {
  token: string;
  currentUserId: number;
  currentUserName?: string;
}

export function ChatPage({
  token,
  currentUserId,
  currentUserName,
}: ChatPageProps) {
  const { t } = useTranslation('chat');
  const dispatch = useDispatch();
  const [selectedChat, setSelectedChat] = useState<Chat | null>(null);
  const [selectedConnectorId, setSelectedConnectorId] = useState<number | null>(
    null,
  );
  const [newChatModalOpen, setNewChatModalOpen] = useState(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [pinnedModalOpen, setPinnedModalOpen] = useState(false);
  const [newMessages, setNewMessages] = useState<Record<number, ChatMessage[]>>(
    {},
  );
  const [typingUsers, setTypingUsers] = useState<Record<number, string[]>>({});
  const [onlineUsers, setOnlineUsers] = useState<Set<number>>(new Set());
  const selectedChatRef = useRef<Chat | null>(null);
  const refetchChatsRef = useRef<(() => void) | null>(null);
  const skipMarkAsReadRef = useRef(false);

  // Синхронизируем ref с state
  useEffect(() => {
    selectedChatRef.current = selectedChat;
  }, [selectedChat]);

  // Читаем фильтр из URL query params
  const [searchParams] = useSearchParams();
  const isInternalParam = searchParams.get('is_internal');
  const chatTypeParam = searchParams.get('chat_type');
  const connectorTypeParam = searchParams.get('connector_type');

  // Формируем фильтр для API
  const chatFilter = {
    is_internal:
      isInternalParam === 'true'
        ? true
        : isInternalParam === 'false'
          ? false
          : undefined,
    chat_type: chatTypeParam as 'direct' | 'group' | undefined,
    connector_type: connectorTypeParam || undefined,
  };

  // Аргументы для getChats - исключаем undefined значения для корректного сравнения в RTK Query
  const getChatsArgs = useMemo(() => {
    const args: {
      limit: number;
      is_internal?: boolean;
      chat_type?: string;
      connector_type?: string;
    } = { limit: 100 };
    if (chatFilter.is_internal !== undefined)
      args.is_internal = chatFilter.is_internal;
    if (chatFilter.chat_type !== undefined)
      args.chat_type = chatFilter.chat_type;
    if (chatFilter.connector_type !== undefined)
      args.connector_type = chatFilter.connector_type;
    return args;
  }, [chatFilter.is_internal, chatFilter.chat_type, chatFilter.connector_type]);

  const [markChatAsRead] = useMarkChatAsReadMutation();

  // Получаем список чатов с фильтром из URL
  const { data: chatsData } = useGetChatsQuery(getChatsArgs);

  // Получаем пиннед сообщения для выбранного чата
  const { data: pinnedData, refetch: refetchPinned } =
    useGetPinnedMessagesQuery(
      { chatId: selectedChat?.id || 0 },
      { skip: !selectedChat },
    );

  // Получаем доступные коннекторы для выбранного чата
  const { data: connectorsData } = useGetChatConnectorsQuery(
    { chatId: selectedChat?.id || 0 },
    { skip: !selectedChat },
  );

  const availableConnectors = connectorsData?.data || [];

  // При смене чата выбираем первый внешний коннектор (если есть) или internal
  useEffect(() => {
    if (availableConnectors.length > 0) {
      // Ищем первый не-internal коннектор
      const externalConnector = availableConnectors.find(
        c => c.connector_type !== 'internal' && c.connector_id !== null,
      );
      if (externalConnector) {
        setSelectedConnectorId(externalConnector.connector_id);
      } else {
        setSelectedConnectorId(null); // internal
      }
    }
  }, [selectedChat?.id, availableConnectors.length]);

  // Открытие модалки pinned с refetch
  const handleOpenPinnedModal = () => {
    refetchPinned();
    setPinnedModalOpen(true);
  };

  // WebSocket connection
  const handleWSMessage = useCallback(
    (message: WSMessage) => {
      console.log('WebSocket message received:', message);

      switch (message.type) {
        case 'new_message': {
          const wsMsg = message as WSNewMessage;
          console.log('New message for chat:', wsMsg.chat_id, wsMsg.message);

          // Добавляем сообщение в локальный стейт для отображения
          setNewMessages(prev => ({
            ...prev,
            [wsMsg.chat_id]: [...(prev[wsMsg.chat_id] || []), wsMsg.message],
          }));

          const isOwnMessage = wsMsg.message.author?.id === currentUserId;

          // Обновляем кэш с фильтрами getChatsArgs (если есть фильтры)
          // Контекст уже обновил базовый кэш { limit: 100 }
          const hasFilters =
            getChatsArgs.is_internal !== undefined ||
            getChatsArgs.chat_type !== undefined ||
            getChatsArgs.connector_type !== undefined;

          if (hasFilters && !isOwnMessage) {
            dispatch(
              chatApi.util.updateQueryData('getChats', getChatsArgs, draft => {
                const chat = draft.data.find(c => c.id === wsMsg.chat_id);
                if (chat) {
                  chat.unread_count = (chat.unread_count || 0) + 1;
                  // Обновляем последнее сообщение
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
          }
          break;
        }
        case 'typing': {
          // Handle typing indicator
          setTimeout(() => {
            setTypingUsers(prev => {
              const chatTyping = prev[message.chat_id] || [];
              return {
                ...prev,
                [message.chat_id]: chatTyping.filter(
                  id => id !== String(message.user_id),
                ),
              };
            });
          }, 3000);

          setTypingUsers(prev => {
            const chatTyping = prev[message.chat_id] || [];
            if (!chatTyping.includes(String(message.user_id))) {
              return {
                ...prev,
                [message.chat_id]: [...chatTyping, String(message.user_id)],
              };
            }
            return prev;
          });
          break;
        }
        case 'presence': {
          if (message.status === 'online') {
            setOnlineUsers(prev => new Set(prev).add(message.user_id));
          } else {
            setOnlineUsers(prev => {
              const next = new Set(prev);
              next.delete(message.user_id);
              return next;
            });
          }
          break;
        }
        case 'messages_read': {
          const readByUserId = (message as any).user_id;

          // Обновляем is_read ТОЛЬКО если это другой пользователь прочитал наши сообщения
          if (readByUserId !== currentUserId) {
            dispatch(
              chatApi.util.updateQueryData(
                'getChatMessages',
                { chatId: message.chat_id, limit: 50 },
                draft => {
                  draft.data.forEach(msg => {
                    // Помечаем наши сообщения как прочитанные
                    if (msg.author?.id === currentUserId) {
                      msg.is_read = true;
                    }
                  });
                },
              ),
            );
          }

          // Обновляем unread_count в кэше когда МЫ прочитали сообщения
          if (readByUserId === currentUserId) {
            dispatch(
              chatApi.util.updateQueryData('getChats', getChatsArgs, draft => {
                const chat = draft.data.find(c => c.id === message.chat_id);
                if (chat) {
                  chat.unread_count = 0;
                }
              }),
            );
          }
          break;
        }
      }
    },
    [currentUserId, dispatch, markChatAsRead, getChatsArgs],
  );

  const {
    isConnected,
    subscribe,
    unsubscribe,
    sendTyping,
    sendRead,
    addMessageListener,
  } = useChatWebSocketContext();

  // Подписываемся на сообщения WebSocket
  useEffect(() => {
    return addMessageListener(handleWSMessage);
  }, [addMessageListener, handleWSMessage]);

  const handleSelectChat = async (chat: Chat) => {
    setSelectedChat(chat);

    // Clear new messages for this chat when selected
    // (они уже в кэше getChatMessages благодаря контексту)
    setNewMessages(prev => ({
      ...prev,
      [chat.id]: [],
    }));

    // НЕ помечаем как прочитанное автоматически при выборе чата
    // Прочтение происходит только при явном действии:
    // - клик по области сообщений или инпуту
    // - отправка сообщения
  };

  // Сброс счетчика при клике на область чата
  const handleChatAreaClick = useCallback(() => {
    if (!selectedChat) return;

    // Пропускаем если только что отметили как непрочитанное
    if (skipMarkAsReadRef.current) {
      skipMarkAsReadRef.current = false;
      return;
    }

    // Проверяем unread_count из кэша RTK Query
    const chatFromCache = chatsData?.data.find(c => c.id === selectedChat.id);
    const unreadCount =
      chatFromCache?.unread_count ?? selectedChat.unread_count ?? 0;

    if (unreadCount > 0) {
      markChatAsRead({ chatId: selectedChat.id });

      // Обнуляем счетчик в обоих кэшах
      dispatch(
        chatApi.util.updateQueryData('getChats', getChatsArgs, draft => {
          const cachedChat = draft.data.find(c => c.id === selectedChat.id);
          if (cachedChat) {
            cachedChat.unread_count = 0;
          }
        }),
      );
      dispatch(
        chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
          const cachedChat = draft.data.find(c => c.id === selectedChat.id);
          if (cachedChat) {
            cachedChat.unread_count = 0;
          }
        }),
      );

      // Обновляем локальный state чата
      setSelectedChat(prev => (prev ? { ...prev, unread_count: 0 } : null));
    }
  }, [selectedChat, chatsData, dispatch, getChatsArgs, markChatAsRead]);

  const handleNewChat = () => {
    setNewChatModalOpen(true);
  };

  const handleChatCreated = (chat: Chat) => {
    setSelectedChat(chat);
    // Подписываемся на новый чат
    if (isConnected) {
      subscribe(chat.id);
    }
    // Обновляем список чатов
    if (refetchChatsRef.current) {
      refetchChatsRef.current();
    }
  };

  const handleTyping = () => {
    if (selectedChat) {
      sendTyping(selectedChat.id);
    }
  };

  const isDirectChatOnline = () => {
    if (
      !selectedChat ||
      selectedChat.chat_type !== 'direct' ||
      !selectedChat.members
    )
      return false;
    const otherMember = selectedChat.members.find(
      m => Number(m.id) !== Number(currentUserId),
    );
    return otherMember ? onlineUsers.has(otherMember.id) : false;
  };

  const getTypingUserNames = () => {
    if (!selectedChat || !selectedChat.members) return [];
    const chatTypingIds = typingUsers[selectedChat.id] || [];
    return chatTypingIds
      .map(id => {
        const member = selectedChat.members.find(m => String(m.id) === id);
        return member?.name || '';
      })
      .filter(Boolean);
  };

  return (
    <Box
      className={styles.container}
      style={{ height: 'calc(100vh - 50px - 2 * var(--mantine-spacing-md))' }}>
      {/* Chat list sidebar */}
      <Box className={styles.sidebar}>
        <ChatList
          selectedChatId={selectedChat?.id}
          onSelectChat={handleSelectChat}
          onNewChat={handleNewChat}
          filter={chatFilter}
          onRefetchReady={refetch => {
            refetchChatsRef.current = refetch;
          }}
        />
      </Box>

      {/* Chat area */}
      <Box className={styles.chatArea}>
        {selectedChat ? (
          <>
            <ChatHeader
              chat={selectedChat}
              isOnline={isDirectChatOnline()}
              typingUsers={getTypingUserNames()}
              onSettings={() => setSettingsModalOpen(true)}
              onPinnedMessages={handleOpenPinnedModal}
            />
            <Box
              onClick={handleChatAreaClick}
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0,
              }}>
              <ChatMessages
                chat={selectedChat}
                currentUserId={currentUserId}
                newMessages={newMessages[selectedChat.id] || []}
                onChatUpdate={updates =>
                  setSelectedChat(prev =>
                    prev ? { ...prev, ...updates } : null,
                  )
                }
                onMarkUnread={() => {
                  skipMarkAsReadRef.current = true;
                }}
              />
            </Box>
            <Box onClick={handleChatAreaClick}>
              <ChatInput
                chatId={selectedChat.id}
                currentUserId={currentUserId}
                currentUserName={currentUserName}
                onTyping={handleTyping}
                connectorId={selectedConnectorId ?? undefined}
                connectors={availableConnectors}
                onConnectorSelect={setSelectedConnectorId}
                onMessageSent={handleChatAreaClick}
              />
            </Box>
          </>
        ) : (
          <Center className={styles.emptyState}>
            <Stack align="center" gap="md">
              <IconMessageCircle
                size={64}
                stroke={1}
                color="var(--mantine-color-gray-5)"
              />
              <Text size="lg" c="dimmed">
                {t('selectChatOrCreate')}
              </Text>
            </Stack>
          </Center>
        )}
      </Box>

      {/* New chat modal */}
      <NewChatModal
        opened={newChatModalOpen}
        onClose={() => setNewChatModalOpen(false)}
        onChatCreated={handleChatCreated}
        currentUserId={currentUserId}
      />

      {/* Chat settings modal */}
      {selectedChat && (
        <ChatSettingsModal
          opened={settingsModalOpen}
          onClose={() => setSettingsModalOpen(false)}
          chat={selectedChat}
          currentUserId={currentUserId}
          onChatDeleted={() => setSelectedChat(null)}
        />
      )}

      {/* Pinned messages modal */}
      <Modal
        opened={pinnedModalOpen}
        onClose={() => setPinnedModalOpen(false)}
        title={t('pinnedMessages')}
        size="md">
        <ScrollArea h={400}>
          {pinnedData?.data && pinnedData.data.length > 0 ? (
            <Stack gap="sm">
              {pinnedData.data.map(msg => (
                <Paper key={msg.id} p="sm" withBorder>
                  <Text size="xs" c="dimmed" mb={4}>
                    {msg.author?.name} •{' '}
                    {msg.create_date
                      ? new Date(msg.create_date).toLocaleString()
                      : ''}
                  </Text>
                  <Text size="sm">{msg.body}</Text>
                </Paper>
              ))}
            </Stack>
          ) : (
            <Text c="dimmed" ta="center">
              {t('noPinnedMessages')}
            </Text>
          )}
        </ScrollArea>
      </Modal>
    </Box>
  );
}

export default ChatPage;
