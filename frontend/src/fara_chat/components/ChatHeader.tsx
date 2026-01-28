import {
  Box,
  Text,
  Group,
  Avatar,
  ActionIcon,
  Menu,
  Badge,
} from '@mantine/core';
import {
  IconDots,
  IconSearch,
  IconPhone,
  IconVideo,
  IconUserPlus,
  IconSettings,
  IconTrash,
  IconBell,
  IconBellOff,
  IconMessage,
  IconPinFilled,
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
}

export function ChatHeader({
  chat,
  isOnline,
  typingUsers = [],
  onAddMember,
  onSettings,
  onSearch,
  onPinnedMessages,
}: ChatHeaderProps) {
  const { t } = useTranslation('chat');

  const members = chat.members || [];

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

          {/* More options menu */}
          <Menu position="bottom-end" withArrow>
            <Menu.Target>
              <ActionIcon variant="subtle" size="lg" title={t('options')}>
                <IconDots size={20} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              {chat.chat_type !== 'direct' && (
                <Menu.Item
                  leftSection={<IconUserPlus size={16} />}
                  onClick={onAddMember}>
                  {t('addMember')}
                </Menu.Item>
              )}

              <Menu.Item leftSection={<IconBell size={16} />}>
                {t('notifications')}
              </Menu.Item>

              <Menu.Item
                leftSection={<IconSettings size={16} />}
                onClick={onSettings}>
                {t('settings')}
              </Menu.Item>

              <Menu.Divider />

              <Menu.Item leftSection={<IconTrash size={16} />} color="red">
                {chat.chat_type === 'direct' ? t('deleteChat') : t('leaveChat')}
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>
    </Box>
  );
}

export default ChatHeader;
