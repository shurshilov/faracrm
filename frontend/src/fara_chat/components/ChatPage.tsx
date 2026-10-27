import { useState, useCallback, useEffect, useRef } from 'react';
import { useMediaQuery } from '@mantine/hooks';
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
  ChatSection,
  GetChatsArgs,
  WSMessage,
  chatApi,
  useMarkChatAsReadMutation,
  useGetChatsQuery,
  useGetChatQuery,
  useGetPinnedMessagesQuery,
  useGetChatConnectorsQuery,
  useSetChatDefaultConnectorMutation,
} from '@/services/api/chat';
import { useHideLayoutHeader } from '@/shared/extensions/layoutHeader';
import { useChatWebSocketContext } from '../context';
import { useChatFilter } from '../hooks/useChatFilter';
import { ChatList, getMessagePreview } from './ChatList';
import { ChatHeader } from './ChatHeader';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { NewChatModal } from './NewChatModal';
import { ChatSettingsModal } from './ChatSettingsModal';
import { MessageSearchModal } from './MessageSearchModal';
import styles from './ChatPage.module.css';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '@/store/store';

/** Раздел чата, как SECTION_SQL на бэке: одиночный GET /chats/{id} его не
 *  отдаёт. */
function chatSection(chat: Chat): ChatSection {
  if (chat.chat_type === 'record') return 'records';
  if (chat.chat_type === 'channel') return 'channels';
  return chat.is_internal ? 'staff' : 'clients';
}

interface ChatPageProps {
  token: string;
  currentUserId: number;
  currentUserName?: string;
}

export function ChatPage({
  currentUserId,
  currentUserName,
}: ChatPageProps) {
  const { t } = useTranslation('chat');
  const dispatch = useDispatch<AppDispatch>();
  const [selectedChat, setSelectedChat] = useState<Chat | null>(null);
  // Soft-delete: видимость удалённых сообщений в открытом чате.
  // Сбрасывается при переключении чата (см. useEffect ниже).
  const [showDeletedMessages, setShowDeletedMessages] = useState(false);
  const isMobile = useMediaQuery('(max-width: 768px)');
  // На мобильном: true = показываем сайдбар, false = показываем чат
  const [showSidebar, setShowSidebar] = useState(true);
  // Открытый чат на мобильном — во весь экран, без шапки приложения
  // (назад к списку — стрелка в шапке чата).
  useHideLayoutHeader(!!isMobile && !showSidebar && !!selectedChat);
  const [selectedConnectorId, setSelectedConnectorId] = useState<number | null>(
    null,
  );
  // Коннектор по умолчанию (per-user, из chat_member) — для галочки в свитчере.
  const [defaultConnectorId, setDefaultConnectorId] = useState<number | null>(
    null,
  );
  const [newChatModalOpen, setNewChatModalOpen] = useState(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [pinnedModalOpen, setPinnedModalOpen] = useState(false);
  const [searchModalOpen, setSearchModalOpen] = useState(false);
  const [typingUsers, setTypingUsers] = useState<Record<number, string[]>>({});
  const selectedChatRef = useRef<Chat | null>(null);
  const refetchChatsRef = useRef<(() => void) | null>(null);
  const skipMarkAsReadRef = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Синхронизируем ref с state
  useEffect(() => {
    selectedChatRef.current = selectedChat;
  }, [selectedChat]);

  // Сбрасываем просмотр удалённых при смене чата (защита от "забыл выключить")
  useEffect(() => {
    setShowDeletedMessages(false);
  }, [selectedChat?.id]);

  // iOS Safari: программная клавиатура не сжимает layout viewport (100dvh
  // остаётся во весь экран), поэтому нижняя панель с полем ввода и кнопкой
  // "Отправить" уезжает под клавиатуру. Через VisualViewport API вычисляем
  // высоту перекрытия клавиатурой и поджимаем контейнер чата на эту величину —
  // input снова оказывается над клавиатурой. Только для мобильных, чтобы не
  // ловить ложные срабатывания при pinch-zoom на десктопе.
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv || !isMobile) {
      containerRef.current?.style.setProperty('--keyboard-inset', '0px');
      return;
    }
    const update = () => {
      const overlap = Math.max(
        0,
        window.innerHeight - vv.height - vv.offsetTop,
      );
      containerRef.current?.style.setProperty(
        '--keyboard-inset',
        `${overlap}px`,
      );
    };
    update();
    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    return () => {
      vv.removeEventListener('resize', update);
      vv.removeEventListener('scroll', update);
    };
  }, [isMobile]);

  // Фильтр списка — в URL (квадраты сайдбара и чипы, см. useChatFilter).
  // undefined-поля в ключ кэша RTK Query не попадают (сериализация JSON).
  const [searchParams, setSearchParams] = useSearchParams();
  const { filter } = useChatFilter();
  const getChatsArgs: GetChatsArgs = { limit: 100, ...filter };

  const [markChatAsRead] = useMarkChatAsReadMutation();

  // Получаем список чатов с фильтром из URL
  const { data: chatsData } = useGetChatsQuery(getChatsArgs);

  // Канал, который просит открывший: ?contact_type=<id типа контакта> со
  // значка контакта (виджет «Контакты», список контактов). Параметр
  // снимается вместе с ?open, поэтому держим его до прихода коннекторов
  // этого чата.
  const requestedContactTypeRef = useRef<number | null>(null);

  // Авто-открытие чата по ?open=chatId (уведомление, значок контакта). Пока
  // open в URL, список — по всем разделам; открыв чат, переходим в его
  // квадрат. Чат ищем в списке; нет там (список дальше первых 100 или из
  // кэша без только что созданного чата) — грузим сам чат.
  const openChatId = Number(searchParams.get('open')) || null;
  const listedChat = openChatId
    ? chatsData?.data.find(c => c.id === openChatId)
    : undefined;
  const { data: openChatData } = useGetChatQuery(
    { chatId: openChatId || 0 },
    { skip: !openChatId || !!listedChat },
  );
  const openChat = listedChat || openChatData?.data;

  useEffect(() => {
    if (!openChatId || !openChat) return;
    requestedContactTypeRef.current =
      Number(searchParams.get('contact_type')) || null;
    setSelectedChat(openChat);
    // Открыть могли из окна создания или настроек (бейдж «есть чат»).
    setNewChatModalOpen(false);
    setSettingsModalOpen(false);
    // На мобильном список и переписка — разные экраны: показываем чат.
    if (isMobile) setShowSidebar(false);
    setSearchParams(
      { section: openChat.section ?? chatSection(openChat) },
      { replace: true },
    );
  }, [openChatId, openChat, searchParams]);

  // Значок контакта без чата: ?new_contact=<id контакта> — визард создания
  // с этим собеседником (подставляет сам NewChatModal); создаёт
  // пользователь кнопкой, параметр снимается при закрытии.
  const newContactId = Number(searchParams.get('new_contact')) || null;
  const handleNewChatClose = () => {
    setNewChatModalOpen(false);
    if (newContactId) setSearchParams({}, { replace: true });
  };

  // Получаем пиннед сообщения для выбранного чата
  const { data: pinnedData, refetch: refetchPinned } =
    useGetPinnedMessagesQuery(
      { chatId: selectedChat?.id || 0 },
      { skip: !selectedChat },
    );

  // Получаем доступные коннекторы для выбранного чата. currentData — ответ
  // именно для этого чата (data при смене чата ещё хранит список прошлого).
  const { data: connectorsData, currentData: currentConnectors } =
    useGetChatConnectorsQuery(
      { chatId: selectedChat?.id || 0 },
      { skip: !selectedChat },
    );

  const availableConnectors = connectorsData?.data || [];

  // При открытии чата подставляем коннектор по умолчанию из ответа бэкенда:
  // галочка пользователя в свитчере, иначе канал, из которого пришёл чат;
  // null = internal. Пришли по значку контакта — канал его типа (один раз,
  // галочку «по умолчанию» не трогаем).
  useEffect(() => {
    const saved = connectorsData?.default_connector_id ?? null;
    setDefaultConnectorId(saved);
    const requested = requestedContactTypeRef.current;
    if (requested && currentConnectors) {
      requestedContactTypeRef.current = null;
      const match = currentConnectors.data.find(
        c => c.contact_type_id === requested,
      );
      if (match) {
        setSelectedConnectorId(match.connector_id);
        return;
      }
    }
    setSelectedConnectorId(saved);
  }, [
    selectedChat?.id,
    connectorsData?.default_connector_id,
    currentConnectors,
  ]);

  const [saveDefaultConnector] = useSetChatDefaultConnectorMutation();
  const handleSetDefaultConnector = useCallback(
    async (cid: number | null) => {
      if (!selectedChat) return;
      setDefaultConnectorId(cid); // локально сразу — для галочки
      try {
        await saveDefaultConnector({
          chatId: selectedChat.id,
          connectorId: cid,
        }).unwrap();
      } catch {
        // сохранить не удалось — оставляем как есть, юзер попробует снова
      }
    },
    [selectedChat, saveDefaultConnector],
  );

  // Открытие модалки pinned с refetch
  const handleOpenPinnedModal = () => {
    refetchPinned();
    setPinnedModalOpen(true);
  };

  // WebSocket. Кэш сообщений и списков правит сам контекст
  // (ChatWebSocketContext) — для всех вариантов аргументов запросов. Здесь
  // остаётся только UI-состояние страницы: индикатор набора.
  const handleWSMessage = useCallback((message: WSMessage) => {
    if (message.type !== 'typing') return;
    const { chat_id: chatId, user_id: userId } = message;

    setTimeout(() => {
      setTypingUsers(prev => {
        const chatTyping = prev[chatId] || [];
        return {
          ...prev,
          [chatId]: chatTyping.filter(id => id !== String(userId)),
        };
      });
    }, 3000);

    setTypingUsers(prev => {
      const chatTyping = prev[chatId] || [];
      if (!chatTyping.includes(String(userId))) {
        return { ...prev, [chatId]: [...chatTyping, String(userId)] };
      }
      return prev;
    });
  }, []);

  const { sendTyping, addMessageListener, isUserOnline } =
    useChatWebSocketContext();

  // Подписываемся на сообщения WebSocket
  useEffect(() => {
    return addMessageListener(handleWSMessage);
  }, [addMessageListener, handleWSMessage]);

  const handleSelectChat = async (chat: Chat) => {
    setSelectedChat(chat);

    // На мобильном — скрываем сайдбар и показываем чат
    if (isMobile) {
      setShowSidebar(false);
    }

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

  // На мобильном — кнопка "назад" из чата возвращает к списку
  const handleBackToList = () => {
    setShowSidebar(true);
  };

  const handleChatCreated = (chat: Chat) => {
    setNewChatModalOpen(false);
    // Открываем как по ?open: в ответе создания нет участников и раздела,
    // а так чат дочитывается целиком и список переходит в его квадрат;
    // канал контакта (?contact_type) подставится там же.
    const contactType = searchParams.get('contact_type');
    setSearchParams(
      {
        open: String(chat.id),
        ...(contactType && { contact_type: contactType }),
      },
      { replace: true },
    );
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
    return otherMember ? isUserOnline(Number(otherMember.id)) : false;
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
      ref={containerRef}
      className={styles.container}
      // height: 100% — наследуем от AppShell.Main (height: 100dvh, padding-bottom: 0).
      // Раньше было calc(100vh - 50px - 2*md): на мобильном 100vh > 100dvh пока
      // видна адресная строка, и нижняя часть с input уезжала за viewport.
      // --keyboard-inset выставляет VisualViewport-эффект выше: на iOS при
      // открытой клавиатуре поджимаем высоту, чтобы input не ушёл под неё.
      style={{ height: 'calc(100% - var(--keyboard-inset, 0px))' }}>
      {/* Chat list sidebar */}
      <Box
        className={`${styles.sidebar} ${isMobile && !showSidebar ? styles.hidden : ''}`}>
        <ChatList
          selectedChatId={selectedChat?.id}
          onSelectChat={handleSelectChat}
          onNewChat={handleNewChat}
          onRefetchReady={refetch => {
            refetchChatsRef.current = refetch;
          }}
        />
      </Box>

      {/* Chat area */}
      <Box
        className={`${styles.chatArea} ${isMobile && showSidebar ? styles.hidden : ''}`}>
        {selectedChat ? (
          <>
            <ChatHeader
              chat={selectedChat}
              isOnline={isDirectChatOnline()}
              typingUsers={getTypingUserNames()}
              onSettings={() => setSettingsModalOpen(true)}
              onPinnedMessages={handleOpenPinnedModal}
              onSearch={() => setSearchModalOpen(true)}
              onBack={isMobile ? handleBackToList : undefined}
              showDeletedMessages={showDeletedMessages}
              onToggleShowDeletedMessages={setShowDeletedMessages}
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
                onChatUpdate={updates =>
                  setSelectedChat(prev =>
                    prev ? { ...prev, ...updates } : null,
                  )
                }
                onMarkUnread={() => {
                  skipMarkAsReadRef.current = true;
                }}
                showDeletedMessages={showDeletedMessages}
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
                defaultConnectorId={defaultConnectorId}
                onSetDefaultConnector={handleSetDefaultConnector}
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
        opened={newChatModalOpen || !!newContactId}
        onClose={handleNewChatClose}
        onChatCreated={handleChatCreated}
        contactId={newContactId}
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
                    {msg.create_datetime
                      ? new Date(msg.create_datetime).toLocaleString()
                      : ''}
                  </Text>
                  <Text size="sm">{getMessagePreview(msg, t)}</Text>
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

      {/* Поиск по сообщениям открытого чата (лупа в шапке) */}
      {selectedChat && (
        <MessageSearchModal
          opened={searchModalOpen}
          onClose={() => setSearchModalOpen(false)}
          chatId={selectedChat.id}
        />
      )}
    </Box>
  );
}

export default ChatPage;
