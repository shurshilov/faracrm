import { useEffect, useRef } from 'react';
import { notifications } from '@mantine/notifications';
import { IconMessage, IconMessagePlus } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { useChatWebSocketContext } from '@/fara_chat/context';
import { useReadQuery } from '@/services/api/crudApi';
import type { RootState } from '@/store/store';
import type { WSMessage, WSNewMessage } from '@/services/api/chat';

// Notification sound — short pleasant chime via Web Audio API
function playNotificationSound() {
  try {
    const ctx = new (window.AudioContext ||
      (window as any).webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.setValueAtTime(1108.73, ctx.currentTime + 0.1);
    osc.type = 'sine';
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.4);
  } catch {
    /* silent */
  }
}

/**
 * NotificationListener — слушает WS и показывает toast-уведомления.
 *
 * ВАЖНО: должен быть внутри ChatWebSocketProvider.
 *
 * Показывает для: new_message, chat_created
 * Не показывает: свои сообщения, если уже на /chat
 * Клик → navigate в чат
 * Настройки: notification_popup / notification_sound из User модели
 */
export function NotificationListener() {
  const navigate = useNavigate();
  const session = useSelector((state: RootState) => state.auth.session);
  const currentUserId = session?.user_id?.id || 0;
  const { addMessageListener } = useChatWebSocketContext();
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;

  // Настройки уведомлений — тот же запрос что и в UserMenu (RTK Query кеширует по ключу)
  const { data: userData } = useReadQuery(
    {
      model: 'users',
      id: currentUserId,
      fields: ['id', 'name', 'image', 'lang_id', 'layout_theme', 'notification_popup', 'notification_sound'],
    },
    { skip: !currentUserId },
  );

  const settingsRef = useRef({ popup: true, sound: true });
  useEffect(() => {
    settingsRef.current = {
      popup: userData?.data?.notification_popup ?? true,
      sound: userData?.data?.notification_sound ?? true,
    };
  }, [userData]);

  useEffect(() => {
    const handler = (message: WSMessage) => {
      if (message.type !== 'new_message' && message.type !== 'chat_created')
        return;

      // Skip own messages
      if (message.type === 'new_message') {
        const wsMsg = message as WSNewMessage;
        if (
          wsMsg.message.author?.type === 'user' &&
          wsMsg.message.author?.id === currentUserId
        )
          return;
      }

      // Skip if on chat page
      if (window.location.pathname.startsWith('/chat')) return;

      // Sound
      if (settingsRef.current.sound) {
        playNotificationSound();
      }

      // Popup
      if (!settingsRef.current.popup) return;

      if (message.type === 'new_message') {
        const wsMsg = message as WSNewMessage;
        notifications.show({
          title: wsMsg.message.author?.name || 'Сообщение',
          message: wsMsg.message.body?.substring(0, 80) || 'Новое сообщение',
          icon: <IconMessage size={18} />,
          color: 'blue',
          autoClose: 5000,
          withCloseButton: true,
          onClick: () => navigateRef.current(`/chat?open=${wsMsg.chat_id}`),
          style: { cursor: 'pointer' },
        });
      }

      if (message.type === 'chat_created') {
        const chatId = (message as any).chat_id;
        notifications.show({
          title: 'Новый чат',
          message: (message as any).chat?.name || 'Создан новый чат',
          icon: <IconMessagePlus size={18} />,
          color: 'teal',
          autoClose: 5000,
          withCloseButton: true,
          onClick: () => navigateRef.current(`/chat?open=${chatId}`),
          style: { cursor: 'pointer' },
        });
      }
    };

    const unsub = addMessageListener(handler);
    return () => unsub();
  }, [addMessageListener, currentUserId]);

  return null;
}

export default NotificationListener;
