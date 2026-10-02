import { useState, useMemo } from 'react';
import {
  Box,
  Text,
  Stack,
  Group,
  Avatar,
  TextInput,
  ActionIcon,
  ScrollArea,
  Skeleton,
  Paper,
  Menu,
  Switch,
  Divider,
} from '@mantine/core';
import { useDebouncedValue, useMediaQuery } from '@mantine/hooks';
import { useSelector } from 'react-redux';
import {
  IconSearch,
  IconPlus,
  IconDotsVertical,
  IconAdjustments,
  IconPin,
  IconPinnedOff,
  IconRestore,
} from '@tabler/icons-react';
import { ViewSettingsPopover, ViewSettingsOption } from './ViewSettingsPopover';
import { useTranslation } from 'react-i18next';
import DOMPurify from 'dompurify';
import {
  useGetChatsQuery,
  usePinChatMutation,
  useRestoreChatMutation,
  Chat,
  GetChatsArgs,
} from '@/services/api/chat';
import { attachmentPreviewUrl } from '@/utils/attachmentUrls';
import { useChatFilter } from '../hooks/useChatFilter';
import { DIRECT_CHAT_COLOR, SECTION_META } from '../sections';
import { ChatSections } from './ChatSections';
import { ChatScopeChips, ChatTypeChips, UnreadChip } from './ChatFilterChips';
import { ConnectorFilter } from './ConnectorFilter';
import styles from './ChatList.module.css';

/**
 * Извлекает чистый текст из HTML через DOMPurify санитизацию.
 * Используется для превью email сообщений в списке чатов.
 */
function stripHtml(html: string): string {
  const clean = DOMPurify.sanitize(html, { ALLOWED_TAGS: [] });
  const div = document.createElement('div');
  div.innerHTML = clean;
  return (div.textContent || '').replace(/\s+/g, ' ').trim();
}

/**
 * Возвращает текст превью сообщения: последнего в списке чатов, а также
 * в результатах поиска и в закреплённых.
 * Для email (по message_type) — очищает через DOMPurify.
 * Для system — парсит JSON {event, params} и форматирует через i18n.
 */
export function getMessagePreview(
  lastMessage:
    | { body?: string; message_type?: string; connector_type?: string }
    | null
    | undefined,
  t: (key: string, options?: Record<string, unknown>) => string,
): string | null {
  if (!lastMessage) return null;
  // Звонок — body пустой, превью собираем по message_type.
  // Можно дополнительно использовать call_disposition, если его
  // добавят в ChatLastMessage, но для старта достаточно общего "Звонок".
  if (lastMessage.message_type === 'call') {
    return `📞 ${t('call', { defaultValue: 'Звонок' })}`;
  }
  if (!lastMessage.body) return null;
  // Письмо: превью — текст без HTML-тегов. Канал в connector_type; старые
  // письма несли message_type==='email' — оставлен фолбэк.
  if (
    lastMessage.connector_type === 'email' ||
    lastMessage.message_type === 'email'
  ) {
    // body — email-формат {subject, html}; для превью берём html (фолбэк —
    // весь body для старых писел без формата), убираем теги.
    let html = lastMessage.body;
    try {
      const data = JSON.parse(lastMessage.body);
      if (
        data &&
        typeof data === 'object' &&
        ('html' in data || 'subject' in data)
      ) {
        html = data.html || data.subject || '';
      }
    } catch {
      // старый формат (plain HTML) — оставляем как есть
    }
    return stripHtml(html);
  }
  if (lastMessage.message_type === 'notification') {
    // body — notification-формат {text, url}; для превью берём text (фолбэк —
    // весь body для старых уведомлений без формата). url в превью не нужен.
    try {
      const data = JSON.parse(lastMessage.body);
      if (
        data &&
        typeof data === 'object' &&
        ('text' in data || 'url' in data)
      ) {
        return data.text || '';
      }
    } catch {
      // старый формат (plain text) — оставляем как есть
    }
    return lastMessage.body;
  }
  if (lastMessage.message_type === 'system') {
    try {
      const payload = JSON.parse(lastMessage.body) as {
        event: string;
        params?: Record<string, unknown>;
      };
      const params = payload.params || {};
      return t(`system_${payload.event}`, {
        actor: (params as { actor_name?: string }).actor_name ?? '',
        target: (params as { target_name?: string }).target_name ?? '',
        defaultValue: payload.event,
      });
    } catch {
      return lastMessage.body;
    }
  }
  return lastMessage.body;
}

interface ChatListProps {
  selectedChatId?: number;
  onSelectChat: (chat: Chat) => void;
  onNewChat: () => void;
  onRefetchReady?: (refetch: () => void) => void;
}

export function ChatList({
  selectedChatId,
  onSelectChat,
  onNewChat,
  onRefetchReady,
}: ChatListProps) {
  const { t } = useTranslation('chat');
  const [search, setSearch] = useState('');
  const isMobile = useMediaQuery('(max-width: 768px)');
  // Раздел, папка и чипы — из URL (квадраты сайдбара, чипы ниже).
  const { filter } = useChatFilter();

  // Доп. фильтры видимости. Не персистятся между сессиями — намеренно
  // (защита от «забыл выключить»).
  //   showDeletedChats — мягко удалённые чаты (доступно всем)
  //   showForeignChats — чаты, где юзер НЕ активный мембер (только
  //                      администратору системы)
  const [showDeletedChats, setShowDeletedChats] = useState(false);
  const [showForeignChats, setShowForeignChats] = useState(false);

  const session = useSelector((s: any) => s.auth?.session);
  const user = session?.user_id;
  const currentUserId = user?.id ?? 0;
  // Администратор системы — суперпользователь или роль system_admin, как
  // проверка на бэке (Session.check_system_admin).
  const isSystemAdmin =
    !!user?.is_admin ||
    (user?.role_ids ?? []).some(
      (role: { code: string }) => role.code === 'system_admin',
    );
  // Команды — из сессии (/signin). В сессии, полученной до их добавления,
  // поля нет — переключатель показываем: без команд бэк вернёт «Мои».
  const hasTeams = user?.team_ids?.length !== 0;

  // Один источник правды для опций — используется и десктопным
  // ViewSettingsPopover, и мобильным Menu.
  const viewOptions: ViewSettingsOption[] = useMemo(
    () => [
      {
        key: 'showDeletedChats',
        label: t('showDeletedChats', 'Показывать удалённые чаты'),
        checked: showDeletedChats,
        onChange: setShowDeletedChats,
      },
      ...(isSystemAdmin
        ? [
            {
              key: 'showForeignChats',
              label: t('showForeignChats', 'Показывать чужие чаты'),
              checked: showForeignChats,
              onChange: setShowForeignChats,
            },
          ]
        : []),
    ],
    [t, isSystemAdmin, showDeletedChats, showForeignChats],
  );
  const anyOptionActive = viewOptions.some(o => o.checked);

  // Поиск — на бэке (GET /chats?search=): по имени чата и участников среди
  // ВСЕХ доступных чатов, а не первых 100 загруженных (issue #28).
  // Дебаунс, чтобы не дёргать запрос на каждую букву.
  const [debouncedSearch] = useDebouncedValue(search.trim(), 300);

  // undefined-поля в ключ кэша RTK Query не попадают (сериализация JSON).
  const queryArgs: GetChatsArgs = {
    limit: 100,
    ...filter,
    ...(showDeletedChats && { include_deleted: true }),
    ...(showForeignChats && { include_foreign: true }),
    ...(debouncedSearch && { search: debouncedSearch }),
  };

  const { data, isLoading, error, refetch } = useGetChatsQuery(queryArgs);
  const [pinChat] = usePinChatMutation();
  const [restoreChat] = useRestoreChatMutation();

  // Закрепить/открепить чат. stopPropagation в обработчиках меню не даёт
  // клику выбрать чат — здесь просто шлём мутацию (список пересортируется
  // на бэке после инвалидации Chat LIST).
  const togglePin = (chat: Chat) => {
    pinChat({ chatId: chat.id, pinned: !chat.is_pinned });
  };

  // Восстановить мягко удалённый чат (active=false). Пункт меню виден только
  // у удалённых чатов (их показывает тумблер «Показывать удалённые чаты»).
  // Бэк вернёт active=true и пришлёт chat_created → список рефетчит.
  const handleRestore = (chat: Chat) => {
    restoreChat({ chatId: chat.id });
  };

  // Передаём refetch наверх при монтировании
  useMemo(() => {
    if (onRefetchReady) {
      onRefetchReady(refetch);
    }
  }, [onRefetchReady, refetch]);

  const chats = data?.data || [];

  // Собеседник в direct-чате = участник, который НЕ текущий юзер (по id, не
  // по имени). Включает и партнёра (у внешних чатов собеседник — партнёр).
  const getOtherMember = (chat: Chat) =>
    chat.chat_type === 'direct' && chat.members.length === 2
      ? chat.members.find(
          m =>
            !(
              (m.member_type === 'user' || !m.member_type) &&
              m.id === currentUserId
            ),
        )
      : undefined;

  // Динамическое имя: в direct-чатах — имя собеседника, а не сохранённое
  // chat.name (там мог остаться формат «X - Y» / имя админа).
  const getDisplayName = (chat: Chat) =>
    getOtherMember(chat)?.name || chat.name;

  // Локального фильтра больше нет: список уже отфильтрован бэком по
  // debouncedSearch (иначе чат, найденный по имени участника, отсеялся бы
  // здесь по отображаемому имени).
  const filteredChats = chats;

  const formatTime = (dateString?: string) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return date.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      });
    } else if (days === 1) {
      return t('yesterday');
    } else if (days < 7) {
      return date.toLocaleDateString([], { weekday: 'short' });
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
  };

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  // Остальные чаты — иконка и цвет их раздела, как на квадрате слева.
  const getChatIcon = (chat: Chat) => {
    if (chat.chat_type === 'direct' && chat.members.length === 2) {
      const otherMember = getOtherMember(chat);
      // Аватар собеседника; инициалы — фолбэк, если у пользователя нет
      // загруженной картинки (image_id пустой) или она не загрузилась.
      const avatarSrc = otherMember?.image_id
        ? attachmentPreviewUrl(otherMember.image_id, 80, 80)
        : undefined;
      return (
        <Avatar color={DIRECT_CHAT_COLOR} radius="xl" size={36} src={avatarSrc}>
          {getInitials(otherMember?.name || chat.name)}
        </Avatar>
      );
    }
    const { Icon, color } = SECTION_META[chat.section ?? 'staff'];
    return (
      <Avatar color={color} radius="xl" size={36}>
        <Icon size={18} />
      </Avatar>
    );
  };

  if (error) {
    return (
      <Box className={styles.container}>
        <Text c="red" ta="center" p="md">
          {t('errorLoadingChats')}
        </Text>
      </Box>
    );
  }

  return (
    <Box className={styles.container}>
      {/* Header */}
      <Box className={styles.header}>
        {/* На мобильном сайдбара нет — квадраты полосой над поиском. */}
        {isMobile && (
          <Box mb="sm">
            <ChatSections />
          </Box>
        )}

        {/* Поиск и действия одной строкой. На мобильном справа от инпута —
            единая кнопка-меню (Новый чат + view-фильтры). */}
        <Group gap="xs" wrap="nowrap">
          <TextInput
            placeholder={t('searchChats')}
            leftSection={<IconSearch size={16} />}
            value={search}
            onChange={e => setSearch(e.currentTarget.value)}
            size="sm"
            style={{ flex: 1 }}
          />

          {isMobile ? (
            <Menu position="bottom-end" withArrow shadow="md">
              <Menu.Target>
                <ActionIcon
                  variant="light"
                  size="lg"
                  title={t('listMenu', 'Меню')}
                  color={anyOptionActive ? 'orange' : undefined}>
                  <IconDotsVertical size={18} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item
                  leftSection={<IconPlus size={16} />}
                  onClick={onNewChat}>
                  {t('newChat')}
                </Menu.Item>

                <Divider my={4} />
                <Menu.Label>
                  <Group gap={6} wrap="nowrap">
                    <IconAdjustments size={14} />
                    <span>{t('listSettings', 'Настройки списка')}</span>
                  </Group>
                </Menu.Label>
                <Stack gap={6} px="sm" py={4}>
                  {viewOptions.map(opt => (
                    <Switch
                      key={opt.key}
                      checked={opt.checked}
                      onChange={e => opt.onChange(e.currentTarget.checked)}
                      label={opt.label}
                      disabled={opt.disabled}
                      size="sm"
                    />
                  ))}
                </Stack>
              </Menu.Dropdown>
            </Menu>
          ) : (
            <>
              <ActionIcon
                variant="light"
                size="lg"
                onClick={onNewChat}
                title={t('newChat')}>
                <IconPlus size={18} />
              </ActionIcon>
              <ViewSettingsPopover
                size="lg"
                variant="light"
                title={t('listSettings', 'Настройки списка')}
                options={viewOptions}
              />
            </>
          )}
        </Group>

        {/* Чипы раздела: переключатель (один вариант выбран всегда) +
            накладывающиеся «Непрочитанные» и «Источник». */}
        <Group gap={6} mt="sm" wrap="wrap">
          {filter.section === 'staff' && <ChatTypeChips />}
          {/* Без команд «Моя команда» = «Мои»; «чужие» снимают и членство, и
              команды — в обоих случаях переключатель лишний. */}
          {filter.section === 'clients' && hasTeams && !showForeignChats && (
            <ChatScopeChips />
          )}
          <UnreadChip />
          {filter.section === 'clients' && <ConnectorFilter />}
        </Group>
      </Box>

      {/* Chat List */}
      <ScrollArea className={styles.chatList}>
        {isLoading ? (
          <Stack p="sm" gap="sm">
            {[1, 2, 3, 4, 5].map(i => (
              <Skeleton key={i} height={60} radius="sm" />
            ))}
          </Stack>
        ) : filteredChats.length === 0 ? (
          <Text c="dimmed" ta="center" p="xl">
            {search ? t('noChatsFound') : t('noChats')}
          </Text>
        ) : (
          <Stack gap={0}>
            {filteredChats.map(chat => (
              <Paper
                key={chat.id}
                className={`${styles.chatItem} ${
                  selectedChatId === chat.id ? styles.selected : ''
                }`}
                style={
                  chat.active === false
                    ? { opacity: 0.55, textDecoration: 'line-through' }
                    : undefined
                }
                onClick={() => onSelectChat(chat)}>
                <Group wrap="nowrap" gap="sm">
                  {getChatIcon(chat)}

                  <Box style={{ flex: 1, overflow: 'hidden' }}>
                    <Group justify="space-between" wrap="nowrap" gap={4}>
                      <Text fw={500} size="sm" truncate style={{ flex: 1 }}>
                        {getDisplayName(chat)}
                      </Text>
                      {chat.is_pinned && (
                        <IconPin
                          size={14}
                          color="var(--mantine-color-gray-5)"
                          title={t('pinned')}
                        />
                      )}
                      <Text size="xs" c="dimmed">
                        {formatTime(
                          chat.last_message_date || chat.create_datetime,
                        )}
                      </Text>
                      <Menu position="bottom-end" withinPortal shadow="md">
                        <Menu.Target>
                          <ActionIcon
                            variant="subtle"
                            color="gray"
                            size="sm"
                            title={t('options')}
                            onClick={e => e.stopPropagation()}>
                            <IconDotsVertical size={14} />
                          </ActionIcon>
                        </Menu.Target>
                        <Menu.Dropdown onClick={e => e.stopPropagation()}>
                          <Menu.Item
                            leftSection={
                              chat.is_pinned ? (
                                <IconPinnedOff size={16} />
                              ) : (
                                <IconPin size={16} />
                              )
                            }
                            onClick={() => togglePin(chat)}>
                            {chat.is_pinned ? t('unpin') : t('pin')}
                          </Menu.Item>
                          {chat.active === false && (
                            <Menu.Item
                              leftSection={<IconRestore size={16} />}
                              onClick={() => handleRestore(chat)}>
                              {t('restoreChat', 'Восстановить чат')}
                            </Menu.Item>
                          )}
                        </Menu.Dropdown>
                      </Menu>
                    </Group>

                    <Group justify="space-between" wrap="nowrap">
                      <Text size="xs" c="dimmed" truncate style={{ flex: 1 }}>
                        {getMessagePreview(chat.last_message, t) ||
                          t('noMessages')}
                      </Text>
                      {chat.unread_count > 0 && (
                        <span className={styles.unread}>
                          {chat.unread_count > 99 ? '99+' : chat.unread_count}
                        </span>
                      )}
                    </Group>
                  </Box>
                </Group>
              </Paper>
            ))}
          </Stack>
        )}
      </ScrollArea>
    </Box>
  );
}

export default ChatList;
