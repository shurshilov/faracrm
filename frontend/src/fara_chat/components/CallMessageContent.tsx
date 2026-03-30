import { useMemo } from 'react';
import { Box, Text, Group, ThemeIcon, Badge } from '@mantine/core';
import {
  IconPhone,
  IconPhoneIncoming,
  IconPhoneOutgoing,
  IconPhoneOff,
  IconPhoneCall,
  IconPlayerPlay,
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
 * Компонент для отображения звонка в чате.
 *
 * Звонок отображается как карточка с:
 * - Иконкой направления (входящий/исходящий)
 * - Статусом (дозвон/разговор/пропущен/отвечен)
 * - Длительностью разговора
 * - Цветовой индикацией (зелёный = отвечен, красный = пропущен)
 *
 * Аудиозапись рендерится через стандартный AttachmentPreview
 * (вложение с mimetype audio/mpeg) — отдельно от этого компонента.
 */
export function CallMessageContent({
  body,
  callDirection,
  callDisposition,
  callDuration,
  callTalkDuration,
  callAnswerTime,
  callEndTime,
  connectorType,
}: CallMessageContentProps) {
  const isIncoming = callDirection === 'incoming';
  const isAnswered = callDisposition === 'answered';
  const isRinging = callDisposition === 'ringing';
  const isMissed =
    callDisposition === 'no_answer' ||
    callDisposition === 'busy' ||
    callDisposition === 'failed' ||
    callDisposition === 'cancelled';

  const directionLabel = isIncoming ? 'Входящий' : 'Исходящий';

  const statusInfo = useMemo(() => {
    switch (callDisposition) {
      case 'ringing':
        return { label: 'Дозвон...', color: 'blue', icon: IconPhoneCall };
      case 'answered':
        return { label: 'Отвечен', color: 'green', icon: IconPhone };
      case 'no_answer':
        return { label: 'Пропущен', color: 'red', icon: IconPhoneOff };
      case 'busy':
        return { label: 'Занято', color: 'orange', icon: IconPhoneOff };
      case 'failed':
        return { label: 'Ошибка', color: 'red', icon: IconPhoneOff };
      case 'cancelled':
        return { label: 'Отменён', color: 'gray', icon: IconPhoneOff };
      default:
        return { label: 'Звонок', color: 'gray', icon: IconPhone };
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

  const DirectionIcon = isIncoming ? IconPhoneIncoming : IconPhoneOutgoing;
  const StatusIcon = statusInfo.icon;

  return (
    <Box className={styles.callContent}>
      <Group gap="sm" wrap="nowrap" align="center">
        {/* Иконка статуса */}
        <ThemeIcon
          size="lg"
          radius="xl"
          variant="light"
          color={statusInfo.color}
          className={isRinging ? styles.ringingIcon : undefined}>
          <StatusIcon size={20} />
        </ThemeIcon>

        {/* Информация о звонке */}
        <Box style={{ flex: 1, minWidth: 0 }}>
          <Group gap="xs" wrap="nowrap">
            <DirectionIcon
              size={14}
              color={`var(--mantine-color-${statusInfo.color}-6)`}
            />
            <Text size="sm" fw={500}>
              {directionLabel} звонок
            </Text>
            <Badge
              size="xs"
              variant="light"
              color={statusInfo.color}
              className={isRinging ? styles.ringingBadge : undefined}>
              {statusInfo.label}
            </Badge>
          </Group>

          {/* Длительность */}
          <Group gap="xs" mt={2}>
            {formattedDuration && (
              <Text size="xs" c="dimmed">
                {formattedDuration}
              </Text>
            )}
            {connectorType && (
              <Text size="xs" c="dimmed">
                via {connectorType}
              </Text>
            )}
          </Group>
        </Box>
      </Group>
    </Box>
  );
}
