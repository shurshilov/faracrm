import { ActionIcon, Indicator, Tooltip } from '@mantine/core';
import { IconMessageCircle } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useGetChatsQuery } from '@/services/api/chat';
import { useSelector } from 'react-redux';
import type { RootState } from '@/store/store';

export function ChatNotification() {
  const { t } = useTranslation('chat');
  const navigate = useNavigate();

  const session = useSelector((state: RootState) => state.auth.session);
  const token = session?.token || '';

  // Список чатов для подсчёта непрочитанных. Обновляется живьём из
  // ChatWebSocketContext вместе с остальными вариантами кэша getChats.
  // Подписок на чаты здесь больше нет: адресатов событий сервер берёт из
  // участников чата (chat_member), клиенту заявлять их не нужно.
  const { data: chatsData } = useGetChatsQuery(
    { limit: 100 },
    { skip: !token },
  );

  // Подсчитываем общее количество непрочитанных
  const totalUnread =
    chatsData?.data?.reduce((sum, chat) => sum + (chat.unread_count || 0), 0) ||
    0;

  const handleClick = () => {
    navigate('/chat');
  };

  return (
    <Tooltip label={t('openChat')} position="bottom" withArrow>
      <Indicator
        inline
        label={totalUnread > 99 ? '99+' : totalUnread}
        size={16}
        disabled={totalUnread === 0}
        color="red"
        offset={4}>
        <ActionIcon
          variant="subtle"
          size="lg"
          onClick={handleClick}
          aria-label={t('openChat')}>
          <IconMessageCircle size={22} />
        </ActionIcon>
      </Indicator>
    </Tooltip>
  );
}

export default ChatNotification;
