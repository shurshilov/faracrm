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
} from '@mantine/core';
import { IconSearch, IconPlus, IconMessage } from '@tabler/icons-react';
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
 */
function getMessagePreview(lastMessage?: ChatLastMessage | null): string | null {
  if (!lastMessage?.body) return null;
  if (lastMessage.message_type === 'email') {
    return stripHtml(lastMessage.body);
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

  // Формируем аргументы запроса, исключая undefined значения
  const queryArgs = useMemo(() => {
    const args: {
      limit: number;
      is_internal?: boolean;
      chat_type?: string;
      connector_type?: string;
    } = { limit: 100 };
    if (filter.is_internal !== undefined) args.is_internal = filter.is_internal;
    if (filter.chat_type !== undefined) args.chat_type = filter.chat_type;
    if (filter.connector_type !== undefined)
      args.connector_type = filter.connector_type;
    return args;
  }, [filter.is_internal, filter.chat_type, filter.connector_type]);

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
      const otherMember = chat.members.find(m => m.name !== chat.name);
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
        <Group justify="space-between" mb="sm">
          <Text fw={600} size="lg">
            {t('chats')}
          </Text>
          <ActionIcon variant="light" onClick={onNewChat} title={t('newChat')}>
            <IconPlus size={18} />
          </ActionIcon>
        </Group>

        <TextInput
          placeholder={t('searchChats')}
          leftSection={<IconSearch size={16} />}
          value={search}
          onChange={e => setSearch(e.currentTarget.value)}
          size="sm"
        />
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
                onClick={() => onSelectChat(chat)}>
                <Group wrap="nowrap" gap="sm">
                  {getChatIcon(chat)}

                  <Box style={{ flex: 1, overflow: 'hidden' }}>
                    <Group justify="space-between" wrap="nowrap">
                      <Text fw={500} truncate style={{ flex: 1 }}>
                        {chat.name}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {formatTime(chat.last_message_date || chat.create_date)}
                      </Text>
                    </Group>

                    <Group justify="space-between" wrap="nowrap">
                      <Text size="sm" c="dimmed" truncate style={{ flex: 1 }}>
                        {getMessagePreview(chat.last_message) || t('noMessages')}
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
