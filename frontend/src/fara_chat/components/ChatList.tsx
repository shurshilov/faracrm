import { useState, useMemo } from 'react';
import {
  Box,
  Text,
  Stack,
  Group,
  Avatar,
  Badge,
  TextInput,
  ActionIcon,
  ScrollArea,
  Skeleton,
  Paper,
  Menu,
  Switch,
  Divider,
} from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { useSelector } from 'react-redux';
import {
  IconSearch,
  IconPlus,
  IconMessage,
  IconDotsVertical,
  IconAdjustments,
} from '@tabler/icons-react';
import { ViewSettingsPopover, ViewSettingsOption } from './ViewSettingsPopover';
import { useTranslation } from 'react-i18next';
import DOMPurify from 'dompurify';
import { useGetChatsQuery, Chat, ChatLastMessage } from '@/services/api/chat';
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
 * Возвращает текст превью последнего сообщения.
 * Для email (по message_type) — очищает через DOMPurify.
 * Для system — парсит JSON {event, params} и форматирует через i18n.
 */
function getMessagePreview(
  lastMessage: ChatLastMessage | null | undefined,
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
  if (lastMessage.message_type === 'email') {
    return stripHtml(lastMessage.body);
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

interface ChatFilter {
  is_internal?: boolean;
  chat_type?: 'direct' | 'group';
  connector_type?: string;
}

interface ChatListProps {
  selectedChatId?: number;
  onSelectChat: (chat: Chat) => void;
  onNewChat: () => void;
  filter?: ChatFilter;
  onRefetchReady?: (refetch: () => void) => void;
}

export function ChatList({
  selectedChatId,
  onSelectChat,
  onNewChat,
  filter = {},
  onRefetchReady,
}: ChatListProps) {
  const { t } = useTranslation('chat');
  const [search, setSearch] = useState('');
  const isMobile = useMediaQuery('(max-width: 768px)');

  // Доп. фильтры видимости. Не персистятся между сессиями — намеренно
  // (защита от «забыл выключить»).
  //   showDeletedChats — мягко удалённые чаты (доступно всем)
  //   showRecordChats  — record-чаты (чаты-хвосты к записям CRM) (доступно всем)
  //   showForeignChats — чаты, где юзер НЕ активный мембер (только для is_admin)
  const [showDeletedChats, setShowDeletedChats] = useState(false);
  const [showRecordChats, setShowRecordChats] = useState(false);
  const [showForeignChats, setShowForeignChats] = useState(false);

  // Для фильтрации админских опций в мобильном меню — на десктопе
  // ViewSettingsPopover делает это сам.
  const session = useSelector((s: any) => s.auth?.session);
  const isAdmin = !!session?.user_id?.is_admin;

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
      {
        key: 'showRecordChats',
        label: t('showRecordChats', 'Показывать record-чаты'),
        checked: showRecordChats,
        onChange: setShowRecordChats,
      },
      {
        key: 'showForeignChats',
        label: t('showForeignChats', 'Показывать чужие чаты'),
        checked: showForeignChats,
        onChange: setShowForeignChats,
        adminOnly: true,
      },
    ],
    [t, showDeletedChats, showRecordChats, showForeignChats],
  );

  // Опции, видимые текущему пользователю (с учётом adminOnly).
  // Нужны для мобильного Menu — там фильтруем сами.
  const mobileVisibleOptions = viewOptions.filter(o => !o.adminOnly || isAdmin);
  const anyMobileOptionActive = mobileVisibleOptions.some(o => o.checked);

  // Формируем аргументы запроса, исключая undefined значения
  const queryArgs = useMemo(() => {
    const args: {
      limit: number;
      is_internal?: boolean;
      chat_type?: string;
      connector_type?: string;
      include_deleted?: boolean;
      include_record?: boolean;
      include_foreign?: boolean;
    } = { limit: 100 };
    if (filter.is_internal !== undefined) args.is_internal = filter.is_internal;
    if (filter.chat_type !== undefined) args.chat_type = filter.chat_type;
    if (filter.connector_type !== undefined)
      args.connector_type = filter.connector_type;
    if (showDeletedChats) args.include_deleted = true;
    if (showRecordChats) args.include_record = true;
    if (showForeignChats) args.include_foreign = true;
    return args;
  }, [
    filter.is_internal,
    filter.chat_type,
    filter.connector_type,
    showDeletedChats,
    showRecordChats,
    showForeignChats,
  ]);

  const { data, isLoading, error, refetch } = useGetChatsQuery(queryArgs);

  // Передаём refetch наверх при монтировании
  useMemo(() => {
    if (onRefetchReady) {
      onRefetchReady(refetch);
    }
  }, [onRefetchReady, refetch]);

  const chats = data?.data || [];

  // Filter chats by search
  const filteredChats = chats.filter(chat =>
    chat.name.toLowerCase().includes(search.toLowerCase()),
  );

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

  const getChatIcon = (chat: Chat) => {
    if (chat.chat_type === 'direct' && chat.members.length === 2) {
      const otherMember = chat.members.find(m => m.name === chat.name);
      return (
        <Avatar color="blue" radius="xl" size="md">
          {getInitials(otherMember?.name || chat.name)}
        </Avatar>
      );
    }
    return (
      <Avatar color="cyan" radius="xl" size="md">
        <IconMessage size={20} />
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
        {/* Заголовок + кнопки — только десктоп.
            На мобильном заголовок-ряд выпиливаем: ModernLayout сверху и так
            занимает место (AppLauncher / submenu / chat notif / avatar),
            повторять "Чаты" + кнопки отдельным рядом — избыточно.
            Меню переезжает на одну строку с поиском (см. ниже). */}
        {!isMobile && (
          <Group justify="space-between" mb="sm">
            <Text fw={600} size="lg">
              {t('chats')}
            </Text>
            <Group gap="xs" wrap="nowrap">
              <ActionIcon
                variant="light"
                onClick={onNewChat}
                title={t('newChat')}>
                <IconPlus size={18} />
              </ActionIcon>
              <ViewSettingsPopover
                size="md"
                variant="light"
                title={t('listSettings', 'Настройки списка')}
                options={viewOptions}
              />
            </Group>
          </Group>
        )}

        {/* Строка поиска. На мобильном справа от инпута — единая кнопка-меню
            (Новый чат + view-фильтры). */}
        <Group gap="xs" wrap="nowrap">
          <TextInput
            placeholder={t('searchChats')}
            leftSection={<IconSearch size={16} />}
            value={search}
            onChange={e => setSearch(e.currentTarget.value)}
            size="sm"
            style={{ flex: 1 }}
          />

          {isMobile && (
            <Menu position="bottom-end" withArrow shadow="md">
              <Menu.Target>
                <ActionIcon
                  variant="light"
                  size="lg"
                  title={t('listMenu', 'Меню')}
                  color={anyMobileOptionActive ? 'orange' : undefined}>
                  <IconDotsVertical size={18} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item
                  leftSection={<IconPlus size={16} />}
                  onClick={onNewChat}>
                  {t('newChat')}
                </Menu.Item>

                {mobileVisibleOptions.length > 0 && (
                  <>
                    <Divider my={4} />
                    <Menu.Label>
                      <Group gap={6} wrap="nowrap">
                        <IconAdjustments size={14} />
                        <span>{t('listSettings', 'Настройки списка')}</span>
                      </Group>
                    </Menu.Label>
                    <Stack gap={6} px="sm" py={4}>
                      {mobileVisibleOptions.map(opt => (
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
                  </>
                )}
              </Menu.Dropdown>
            </Menu>
          )}
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
                    <Group justify="space-between" wrap="nowrap">
                      <Text fw={500} truncate style={{ flex: 1 }}>
                        {chat.name}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {formatTime(
                          chat.last_message_date || chat.create_datetime,
                        )}
                      </Text>
                    </Group>

                    <Group justify="space-between" wrap="nowrap">
                      <Text size="sm" c="dimmed" truncate style={{ flex: 1 }}>
                        {getMessagePreview(chat.last_message, t) ||
                          t('noMessages')}
                      </Text>
                      {chat.unread_count > 0 && (
                        <Badge size="sm" variant="filled" color="blue" circle>
                          {chat.unread_count > 99 ? '99+' : chat.unread_count}
                        </Badge>
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
