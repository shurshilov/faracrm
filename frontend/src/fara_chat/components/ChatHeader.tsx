import { ViewSettingsPopover } from './ViewSettingsPopover';
import { CallButton } from './CallButton';
import { useSelector } from 'react-redux';
import type { RootState } from '@store/store';
import { Box, Text, Group, Avatar, ActionIcon, Menu } from '@mantine/core';
import {
  IconDots,
  IconSearch,
  IconSettings,
  IconBell,
  IconMessage,
  IconPinFilled,
  IconArrowLeft,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Chat } from '@/services/api/chat';
import styles from './ChatHeader.module.css';

interface ChatHeaderProps {
  chat: Chat;
  isOnline?: boolean;
  typingUsers?: string[];
  onAddMember?: () => void;
  onSettings?: () => void;
  onSearch?: () => void;
  onPinnedMessages?: () => void;
  onBack?: () => void; // Кнопка "назад" на мобильном
  showDeletedMessages?: boolean;
  onToggleShowDeletedMessages?: (v: boolean) => void;
}

export function ChatHeader({
  chat,
  isOnline,
  typingUsers = [],
  onAddMember,
  onSettings,
  onSearch,
  onPinnedMessages,
  onBack,
  showDeletedMessages = false,
  onToggleShowDeletedMessages,
}: ChatHeaderProps) {
  const { t } = useTranslation('chat');

  const members = chat.members || [];

  // В direct-чате ищем собеседника (user, не партнёра) — для кнопки звонка.
  // Звонить можно только юзеру, не партнёру (нет гарантии WebSocket).
  const currentUserId = useSelector(
    (s: RootState) => s.auth.session?.user_id?.id ?? 0,
  );
  const otherUser =
    chat.chat_type === 'direct'
      ? members.find(
          m =>
            (m.member_type === 'user' || !m.member_type) &&
            m.id !== currentUserId,
        )
      : null;

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const getSubtitle = () => {
    if (typingUsers.length > 0) {
      if (typingUsers.length === 1) {
        return t('userTyping', { name: typingUsers[0] });
      }
      return t('usersTyping', { count: typingUsers.length });
    }

    if (chat.chat_type === 'direct') {
      return isOnline ? t('online') : t('offline');
    }

    return t('membersCount', { count: members.length });
  };

  const getChatIcon = () => {
    if (chat.chat_type === 'direct' && members.length === 2) {
      const otherMember = members.find(m => m.name !== chat.name);
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

  return (
    <Box className={styles.container}>
      <Group justify="space-between" wrap="nowrap">
        <Group gap="sm" wrap="nowrap" style={{ overflow: 'hidden' }}>
          {/* Кнопка "назад" — только на мобильном (передаётся из ChatPage) */}
          {onBack && (
            <ActionIcon variant="subtle" size="lg" onClick={onBack}>
              <IconArrowLeft size={20} />
            </ActionIcon>
          )}
          <Box style={{ position: 'relative' }}>
            {getChatIcon()}
            {chat.chat_type === 'direct' && isOnline && (
              <Box className={styles.onlineIndicator} />
            )}
          </Box>

          <Box style={{ overflow: 'hidden' }}>
            <Text fw={600} truncate>
              {chat.name}
            </Text>
            <Text
              size="sm"
              c={typingUsers.length > 0 ? 'blue' : 'dimmed'}
              truncate>
              {getSubtitle()}
            </Text>
          </Box>
        </Group>

        <Group gap="xs" wrap="nowrap">
          {/* Call button — только в direct-чате между юзерами */}
          {otherUser && (
            <CallButton
              peer={{ id: otherUser.id, name: otherUser.name }}
            />
          )}

          {/* Pinned messages */}
          <ActionIcon
            variant="subtle"
            size="lg"
            onClick={onPinnedMessages}
            title={t('pinnedMessages')}>
            <IconPinFilled size={20} />
          </ActionIcon>

          {/* Search */}
          <ActionIcon
            variant="subtle"
            size="lg"
            onClick={onSearch}
            title={t('search')}>
            <IconSearch size={20} />
          </ActionIcon>

          {/* Soft-delete: show deleted messages (admin only) */}
          <ViewSettingsPopover
            size="lg"
            variant="subtle"
            title={t('chatSettings')}
            options={[
              {
                key: 'showDeletedMessages',
                label: t(
                  'showDeletedMessages',
                  'Показывать удалённые сообщения',
                ),
                checked: showDeletedMessages,
                onChange: v => onToggleShowDeletedMessages?.(v),
                adminOnly: true,
              },
            ]}
          />

          {/* More options menu */}
          <Menu position="bottom-end" withArrow>
            <Menu.Target>
              <ActionIcon variant="subtle" size="lg" title={t('options')}>
                <IconDots size={20} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              {/* Добавление участников теперь через настройки чата */}

              <Menu.Item leftSection={<IconBell size={16} />}>
                {t('notifications')}
              </Menu.Item>

              <Menu.Item
                leftSection={<IconSettings size={16} />}
                onClick={onSettings}>
                {t('settings')}
              </Menu.Item>

              <Menu.Divider />

              {/* <Menu.Item leftSection={<IconTrash size={16} />} color="red">
                {chat.chat_type === 'direct' ? t('deleteChat') : t('leaveChat')}
              </Menu.Item> */}
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>
    </Box>
  );
}

export default ChatHeader;
