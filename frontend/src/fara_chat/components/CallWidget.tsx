/**
 * CallWidget — единый UI-виджет для всех фаз звонка.
 *
 * Отображается в правом нижнем углу экрана (не блокирует весь экран).
 * Фазы:
 *   - incoming  : "Входящий от X" + кнопки Принять/Отклонить
 *   - calling   : "Вызов X..." + кнопка Отмена
 *   - connecting: "Соединение..." (идёт ICE/SDP)
 *   - active    : таймер + mute/hangup
 *   - ended     : краткое "Звонок завершён" + причина (автоскрытие через 3с)
 *
 * Монтируется один раз в корне приложения.
 */
import { useEffect, useState } from 'react';
import { Box, Group, Text, ActionIcon, Button, Paper } from '@mantine/core';
import {
  IconPhone,
  IconPhoneOff,
  IconMicrophone,
  IconMicrophoneOff,
} from '@tabler/icons-react';
import { useCall } from '../context/CallContext';
import type { EndReason } from '../hooks/useWebRTCCall';

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60).toString().padStart(2, '0');
  const s = (sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function endReasonLabel(reason: EndReason | null): string {
  switch (reason) {
    case 'hangup':
      return 'Звонок завершён';
    case 'rejected':
      return 'Отклонён';
    case 'timeout':
      return 'Нет ответа';
    case 'offline':
      return 'Пользователь недоступен';
    case 'failed':
      return 'Ошибка соединения';
    default:
      return 'Завершён';
  }
}

export function CallWidget() {
  const {
    state,
    session,
    endReason,
    durationSec,
    acceptCall,
    rejectCall,
    hangup,
    isMuted,
    toggleMute,
  } = useCall();

  // Автоскрытие экрана ended через 3 секунды, чтобы юзер увидел итог и
  // виджет пропал.
  const [hiddenAfterEnd, setHiddenAfterEnd] = useState(false);
  useEffect(() => {
    if (state === 'ended') {
      setHiddenAfterEnd(false);
      const t = setTimeout(() => setHiddenAfterEnd(true), 3000);
      return () => clearTimeout(t);
    }
    setHiddenAfterEnd(false);
  }, [state]);

  if (state === 'idle') return null;
  if (state === 'ended' && hiddenAfterEnd) return null;
  if (!session) return null;

  return (
    <Paper
      shadow="lg"
      radius="md"
      p="md"
      style={{
        position: 'fixed',
        right: 24,
        bottom: 24,
        minWidth: 320,
        zIndex: 1000,
      }}
      withBorder
    >
      <Box>
        <Text size="xs" c="dimmed" mb={4}>
          {state === 'incoming' && 'Входящий звонок'}
          {state === 'calling' && 'Исходящий вызов'}
          {state === 'connecting' && 'Соединение...'}
          {state === 'active' && 'Разговор'}
          {state === 'ended' && endReasonLabel(endReason)}
        </Text>
        <Text fw={600} size="lg">
          {session.peer.name}
        </Text>
        {state === 'active' && (
          <Text size="sm" c="dimmed" mt={4}>
            {formatDuration(durationSec)}
          </Text>
        )}
      </Box>

      <Group justify="flex-end" gap="xs" mt="md">
        {state === 'incoming' && (
          <>
            <Button
              color="red"
              variant="light"
              leftSection={<IconPhoneOff size={16} />}
              onClick={rejectCall}
            >
              Отклонить
            </Button>
            <Button
              color="green"
              leftSection={<IconPhone size={16} />}
              onClick={acceptCall}
            >
              Принять
            </Button>
          </>
        )}

        {(state === 'calling' || state === 'connecting') && (
          <Button
            color="red"
            variant="light"
            leftSection={<IconPhoneOff size={16} />}
            onClick={hangup}
          >
            Отменить
          </Button>
        )}

        {state === 'active' && (
          <>
            <ActionIcon
              size="lg"
              variant={isMuted ? 'filled' : 'light'}
              color={isMuted ? 'orange' : 'gray'}
              onClick={toggleMute}
              title={isMuted ? 'Включить микрофон' : 'Выключить микрофон'}
            >
              {isMuted ? (
                <IconMicrophoneOff size={18} />
              ) : (
                <IconMicrophone size={18} />
              )}
            </ActionIcon>
            <Button
              color="red"
              leftSection={<IconPhoneOff size={16} />}
              onClick={hangup}
            >
              Завершить
            </Button>
          </>
        )}
      </Group>
    </Paper>
  );
}
