import { useEffect, useRef } from 'react';
import { ActionIcon, Indicator, Tooltip } from '@mantine/core';
import { IconMessageCircle } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useGetChatsQuery } from '@/services/api/chat';
import { useChatWebSocketContext } from '@/fara_chat/context';
import { useSelector } from 'react-redux';
import type { RootState } from '@/store/store';

export function ChatNotification() {
  const { t } = useTranslation('chat');
  const navigate = useNavigate();

  const session = useSelector((state: RootState) => state.auth.session);
  const token = session?.token || '';

  // Получаем список чатов для подсчета непрочитанных
  // Используем { limit: 100 } без фильтров - этот кэш обновляется глобально в контексте
  const { data: chatsData } = useGetChatsQuery(
    { limit: 100 },
    { skip: !token },
  );

  // Подсчитываем общее количество непрочитанных
  const totalUnread =
    chatsData?.data?.reduce((sum, chat) => sum + (chat.unread_count || 0), 0) ||
    0;

  // Используем общий WebSocket контекст
  const { isConnected, subscribeAll } = useChatWebSocketContext();

  // Подписываемся на все чаты при загрузке
  const hasSubscribedRef = useRef(false);

  useEffect(() => {
    if (isConnected && chatsData?.data && !hasSubscribedRef.current) {
      const chatIds = chatsData.data.map(chat => chat.id);
      if (chatIds.length > 0) {
        subscribeAll(chatIds);
        hasSubscribedRef.current = true;
      }
    }
  }, [isConnected, chatsData?.data, subscribeAll]);

  useEffect(() => {
    if (!isConnected) {
      hasSubscribedRef.current = false;
    }
  }, [isConnected]);

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
