import { useMemo } from 'react';
import { Box, Text, Group, ThemeIcon } from '@mantine/core';
import {
  IconPhone,
  IconPhoneIncoming,
  IconPhoneOutgoing,
  IconPhoneOff,
  IconPhoneCall,
} from '@tabler/icons-react';
import styles from './CallMessageContent.module.css';

interface CallMessageContentProps {
  body?: string;
  callDirection?: string;
  callDisposition?: string;
  callDuration?: number;
  callTalkDuration?: number;
  callAnswerTime?: string;
  callEndTime?: string;
  connectorType?: string;
}

/**
 * Плашка звонка в чате.
 *
 * Layout: одна цветная иконка направления + заголовок + статус + длительность.
 * Цвет всей плашки зависит от disposition:
 *   - ringing  → синий (идёт дозвон, с пульсацией)
 *   - answered → зелёный (успешный разговор)
 *   - прочее   → красный/серый (пропущен/отменён/ошибка)
 *
 * Аудиозапись (если есть) рендерится отдельно через AttachmentPreview.
 */
export function CallMessageContent({
  callDirection,
  callDisposition,
  callDuration,
  callTalkDuration,
  connectorType,
}: CallMessageContentProps) {
  const isIncoming = callDirection === 'incoming';
  const isAnswered = callDisposition === 'answered';
  const isRinging = callDisposition === 'ringing';

  const statusInfo = useMemo(() => {
    switch (callDisposition) {
      case 'ringing':
        return { label: 'Дозвон...', color: 'blue', Icon: IconPhoneCall };
      case 'answered':
        return { label: 'Отвечен', color: 'green', Icon: IconPhone };
      case 'no_answer':
        return { label: 'Пропущен', color: 'red', Icon: IconPhoneOff };
      case 'busy':
        return { label: 'Занято', color: 'orange', Icon: IconPhoneOff };
      case 'failed':
        return { label: 'Ошибка', color: 'red', Icon: IconPhoneOff };
      case 'cancelled':
        return { label: 'Отменён', color: 'gray', Icon: IconPhoneOff };
      default:
        return { label: 'Звонок', color: 'gray', Icon: IconPhone };
    }
  }, [callDisposition]);

  const formattedDuration = useMemo(() => {
    const seconds = callTalkDuration ?? callDuration;
    if (!seconds || seconds === 0) return null;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) {
      return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${m}:${String(s).padStart(2, '0')}`;
  }, [callDuration, callTalkDuration]);

  // Одна иконка направления слева — если отвечен, используем её,
  // иначе иконку статуса (разные визуально: трубка / перечёркнутая / набор).
  const MainIcon = isAnswered
    ? isIncoming
      ? IconPhoneIncoming
      : IconPhoneOutgoing
    : statusInfo.Icon;

  const directionLabel = isIncoming ? 'Входящий звонок' : 'Исходящий звонок';

  return (
    <Box className={styles.callContent}>
      <Group gap={12} wrap="nowrap" align="center">
        <ThemeIcon
          size={36}
          radius="xl"
          variant="light"
          color={statusInfo.color}
          className={isRinging ? styles.ringingIcon : undefined}>
          <MainIcon size={20} />
        </ThemeIcon>

        <Box style={{ flex: 1, minWidth: 0 }}>
          <Text size="sm" fw={600} className={styles.title}>
            {directionLabel}
          </Text>
          <Group gap={6} wrap="nowrap">
            <Text
              size="xs"
              className={styles.status}
              style={{
                color: `var(--mantine-color-${statusInfo.color}-6)`,
              }}>
              {statusInfo.label}
            </Text>
            {formattedDuration && (
              <>
                <Text size="xs" c="dimmed">
                  ·
                </Text>
                <Text size="xs" c="dimmed">
                  {formattedDuration}
                </Text>
              </>
            )}
            {connectorType && (
              <>
                <Text size="xs" c="dimmed">
                  ·
                </Text>
                <Text size="xs" c="dimmed">
                  {connectorType}
                </Text>
              </>
            )}
          </Group>
        </Box>
      </Group>
    </Box>
  );
}
