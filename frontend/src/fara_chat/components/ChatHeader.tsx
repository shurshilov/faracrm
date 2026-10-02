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
  IconPinFilled,
  IconArrowLeft,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Chat } from '@/services/api/chat';
import { attachmentPreviewUrl } from '@/utils/attachmentUrls';
import { DIRECT_CHAT_COLOR, SECTION_META } from '../sections';
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

  // Собеседник в direct-чате = участник, который НЕ текущий юзер (по id, не
  // по имени). Включает и партнёра (у внешних чатов собеседник — партнёр).
  const otherMember =
    chat.chat_type === 'direct' && members.length === 2
      ? members.find(
          m =>
            !(
              (m.member_type === 'user' || !m.member_type) &&
              m.id === currentUserId
            ),
        )
      : undefined;

  // Динамическое имя для шапки: в direct-чатах — имя собеседника, а не
  // сохранённое chat.name (там мог остаться формат «X - Y» / имя админа).
  const displayName = otherMember?.name || chat.name;

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
      // Аватар собеседника; инициалы — фолбэк, если у пользователя нет
      // загруженной картинки (image_id пустой) или она не загрузилась.
      const avatarSrc = otherMember?.image_id
        ? attachmentPreviewUrl(otherMember.image_id, 80, 80)
        : undefined;
      return (
        <Avatar color={DIRECT_CHAT_COLOR} radius="xl" size="md" src={avatarSrc}>
          {getInitials(otherMember?.name || chat.name)}
        </Avatar>
      );
    }
    // Иконка и цвет раздела — как в списке и на квадрате слева.
    const { Icon, color } = SECTION_META[chat.section ?? 'staff'];
    return (
      <Avatar color={color} radius="xl" size="md">
        <Icon size={20} />
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
              {displayName}
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
            <CallButton peer={{ id: otherUser.id, name: otherUser.name }} />
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
