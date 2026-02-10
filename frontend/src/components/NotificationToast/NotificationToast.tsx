import { useEffect, useRef, useCallback } from 'react';
import { notifications } from '@mantine/notifications';
import {
  IconMessage,
  IconMessagePlus,
  IconBell,
  IconVolume,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { useChatWebSocketContext } from '@/fara_chat/context';
import { useReadQuery } from '@/services/api/crudApi';
import type { RootState } from '@/store/store';
import type { WSMessage, WSNewMessage } from '@/services/api/chat';

// Notification sound - short pleasant chime (base64 encoded tiny mp3 not practical, use Web Audio API)
function playNotificationSound() {
  try {
    const ctx = new (window.AudioContext ||
      (window as any).webkitAudioContext)();
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();

    oscillator.connect(gain);
    gain.connect(ctx.destination);

    oscillator.frequency.setValueAtTime(880, ctx.currentTime); // A5
    oscillator.frequency.setValueAtTime(1108.73, ctx.currentTime + 0.1); // C#6
    oscillator.type = 'sine';

    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);

    oscillator.start(ctx.currentTime);
    oscillator.stop(ctx.currentTime + 0.4);
  } catch {
    // Web Audio API not available — silent
  }
}

/**
 * NotificationToast — слушает WS события и показывает toast-уведомления.
 *
 * Показывает уведомления для:
 * - new_message (новое сообщение в чате)
 * - chat_created (создан новый чат)
 *
 * Клик по уведомлению переносит в соответствующий чат.
 * Не показывает если пользователь уже на странице этого чата.
 *
 * Настройки notification_popup и notification_sound берутся из User модели.
 */
export function NotificationToast() {
  const { t } = useTranslation('chat');
  const navigate = useNavigate();
  const session = useSelector((state: RootState) => state.auth.session);
  const currentUserId = session?.user_id?.id || 0;
  const { addMessageListener } = useChatWebSocketContext();

  // Получаем настройки уведомлений пользователя
  const { data: userData } = useReadQuery(
    {
      model: 'users',
      id: currentUserId,
      fields: ['id', 'notification_popup', 'notification_sound'],
    },
    { skip: !currentUserId },
  );

  const notificationPopup = userData?.data?.notification_popup ?? true;
  const notificationSound = userData?.data?.notification_sound ?? true;

  // Ref чтобы в callback всегда актуальные значения
  const settingsRef = useRef({ popup: true, sound: true });
  settingsRef.current = {
    popup: notificationPopup,
    sound: notificationSound,
  };

  const handleWSMessage = useCallback(
    (message: WSMessage) => {
      // Только new_message и chat_created
      if (message.type !== 'new_message' && message.type !== 'chat_created') {
        return;
      }

      // Не показывать уведомление для своих сообщений
      if (message.type === 'new_message') {
        const wsMsg = message as WSNewMessage;
        if (
          wsMsg.message.author?.type === 'user' &&
          wsMsg.message.author?.id === currentUserId
        ) {
          return;
        }
      }

      // Не показывать если пользователь уже на странице чата
      if (window.location.pathname.startsWith('/chat')) {
        // Можно уточнить: не показывать только если открыт конкретный чат
        // Но для простоты: если на /chat — не показываем
        return;
      }

      // Звук
      if (settingsRef.current.sound) {
        playNotificationSound();
      }

      // Popup
      if (!settingsRef.current.popup) {
        return;
      }

      if (message.type === 'new_message') {
        const wsMsg = message as WSNewMessage;
        const authorName =
          wsMsg.message.author?.name ||
          t('notification.unknownSender', 'Новое сообщение');
        const body =
          wsMsg.message.body?.substring(0, 80) ||
          t('notification.newMessage', 'Новое сообщение');
        const chatId = wsMsg.chat_id;

        notifications.show({
          title: authorName,
          message: body,
          icon: <IconMessage size={18} />,
          color: 'blue',
          autoClose: 5000,
          withCloseButton: true,
          onClick: () => {
            if (chatId) {
              navigate(`/chat?open=${chatId}`);
            } else {
              navigate('/chat');
            }
          },
          style: { cursor: 'pointer' },
        });
      }

      if (message.type === 'chat_created') {
        const chatId = (message as any).chat_id;
        const chatName =
          (message as any).chat?.name ||
          t('notification.newChat', 'Новый чат');

        notifications.show({
          title: t('notification.chatCreated', 'Создан новый чат'),
          message: chatName,
          icon: <IconMessagePlus size={18} />,
          color: 'teal',
          autoClose: 5000,
          withCloseButton: true,
          onClick: () => {
            if (chatId) {
              navigate(`/chat?open=${chatId}`);
            } else {
              navigate('/chat');
            }
          },
          style: { cursor: 'pointer' },
        });
      }
    },
    [currentUserId, navigate, t],
  );

  useEffect(() => {
    const unsubscribe = addMessageListener(handleWSMessage);
    return unsubscribe;
  }, [addMessageListener, handleWSMessage]);

  // Компонент не рендерит ничего — только слушает
  return null;
}

export default NotificationToast;
