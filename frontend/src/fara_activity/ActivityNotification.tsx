import { useEffect, useRef, useState, useCallback } from 'react';
import {
  ActionIcon,
  Indicator,
  Tooltip,
  Popover,
  Stack,
  Text,
  Group,
  Badge,
  ScrollArea,
  UnstyledButton,
  Divider,
  Center,
  Loader,
  Box,
} from '@mantine/core';
import { IconBell, IconCheck, IconExternalLink } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  useGetChatsQuery,
  useGetChatMessagesQuery,
  useMarkChatAsReadMutation,
} from '@/services/api/chat';
import { useChatWebSocketContext } from '@/fara_chat/context';
import { useSelector } from 'react-redux';
import type { RootState } from '@/store/store';

/**
 * Колокольчик уведомлений — показывает notification-сообщения
 * из системного чата (__system__{userId}).
 */
export function ActivityNotification() {
  const { t } = useTranslation('activity');
  const navigate = useNavigate();
  const [opened, setOpened] = useState(false);

  const session = useSelector((state: RootState) => state.auth.session);
  const token = session?.token || '';
  const userId = session?.uid;

  // Получаем список чатов — ищем системный
  const { data: chatsData } = useGetChatsQuery(
    { limit: 100 },
    { skip: !token },
  );

  // Находим системный чат по имени __system__{userId}
  const systemChat = chatsData?.data?.find(
    (chat: any) => chat.name === `__system__${userId}`,
  );

  const systemChatId = systemChat?.id;
  const unreadCount = systemChat?.unread_count || 0;

  // Получаем сообщения из системного чата
  const { data: messagesData, isLoading } = useGetChatMessagesQuery(
    { chatId: systemChatId!, limit: 20 },
    { skip: !systemChatId || !opened },
  );

  const [markAsRead] = useMarkChatAsReadMutation();

  const handleMarkAllRead = useCallback(() => {
    if (systemChatId) {
      markAsRead({ chatId: systemChatId });
    }
  }, [systemChatId, markAsRead]);

  const handleClickNotification = useCallback(
    (resModel?: string, resId?: number) => {
      setOpened(false);
      if (resModel && resId) {
        navigate(`/${resModel}/${resId}`);
      }
    },
    [navigate],
  );

  const messages = messagesData?.data || [];

  return (
    <Popover
      opened={opened}
      onChange={setOpened}
      position="bottom-end"
      width={380}
      shadow="lg"
      offset={8}>
      <Popover.Target>
        <Tooltip label={t('notifications')} position="bottom" withArrow>
          <Indicator
            inline
            label={unreadCount > 99 ? '99+' : unreadCount}
            size={16}
            disabled={unreadCount === 0}
            color="orange"
            offset={4}>
            <ActionIcon
              variant="subtle"
              size="lg"
              onClick={() => setOpened(o => !o)}
              aria-label={t('notifications')}>
              <IconBell size={22} />
            </ActionIcon>
          </Indicator>
        </Tooltip>
      </Popover.Target>

      <Popover.Dropdown p={0}>
        {/* Заголовок */}
        <Group justify="space-between" p="sm" pb="xs">
          <Text fw={600} size="sm">
            {t('notifications')}
          </Text>
          {unreadCount > 0 && (
            <UnstyledButton onClick={handleMarkAllRead}>
              <Group gap={4}>
                <IconCheck size={14} />
                <Text size="xs" c="dimmed">
                  {t('markAllRead')}
                </Text>
              </Group>
            </UnstyledButton>
          )}
        </Group>
        <Divider />

        {/* Список уведомлений */}
        <ScrollArea.Autosize mah={400}>
          {isLoading && (
            <Center py="xl">
              <Loader size="sm" />
            </Center>
          )}

          {!isLoading && messages.length === 0 && (
            <Center py="xl">
              <Text size="sm" c="dimmed">
                {t('noNotifications')}
              </Text>
            </Center>
          )}

          {messages.map((msg: any) => (
            <UnstyledButton
              key={msg.id}
              w="100%"
              p="sm"
              style={{
                borderBottom: '1px solid var(--mantine-color-gray-2)',
                backgroundColor: msg.is_read
                  ? undefined
                  : 'var(--mantine-color-orange-0)',
              }}
              onClick={() =>
                handleClickNotification(msg.res_model, msg.res_id)
              }>
              <Group gap="xs" wrap="nowrap" align="flex-start">
                <Box style={{ flex: 1 }}>
                  <Text size="sm" lineClamp={2}>
                    {msg.body}
                  </Text>
                  <Group gap="xs" mt={4}>
                    <Text size="xs" c="dimmed">
                      {msg.create_date
                        ? new Date(msg.create_date).toLocaleString()
                        : ''}
                    </Text>
                    {msg.res_model && (
                      <Badge size="xs" variant="light" color="gray">
                        {msg.res_model}
                      </Badge>
                    )}
                  </Group>
                </Box>
                {msg.res_model && msg.res_id && (
                  <ActionIcon variant="subtle" size="sm" color="gray">
                    <IconExternalLink size={14} />
                  </ActionIcon>
                )}
              </Group>
            </UnstyledButton>
          ))}
        </ScrollArea.Autosize>

        {/* Футер */}
        {messages.length > 0 && (
          <>
            <Divider />
            <UnstyledButton
              w="100%"
              p="xs"
              onClick={() => {
                setOpened(false);
                navigate('/activity');
              }}>
              <Text size="xs" c="blue" ta="center">
                {t('viewAll')}
              </Text>
            </UnstyledButton>
          </>
        )}
      </Popover.Dropdown>
    </Popover>
  );
}

export default ActivityNotification;
