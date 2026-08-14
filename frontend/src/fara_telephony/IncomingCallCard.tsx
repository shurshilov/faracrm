// Copyright 2025 FARA CRM
// Всплывашка-карточка звонка. Слушает WS-события пайплайна звонка
// (call.incoming / call.ended) и показывает информационную карточку оператору.
//
// Сам звонок при этом отображается в чате партнёра как сообщение-звонок
// (CallMessageContent + аудиозапись) — это делает существующий рендер чата.
// Здесь только «всплывашка» поверх интерфейса, как просили.
//
// Монтируется один раз в ModernLayout (внутри ChatWebSocketProvider).

import { useEffect, useState, useCallback } from 'react';
import {
  Paper,
  Group,
  Text,
  ThemeIcon,
  ActionIcon,
  Anchor,
} from '@mantine/core';
import {
  IconPhoneIncoming,
  IconPhoneOutgoing,
  IconX,
} from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { useChatWebSocketContext } from '@/fara_chat/context';

interface CallCard {
  message_id?: number;
  direction?: string;
  disposition?: string;
  number?: string;
  name?: string;
  partner_id?: number | null;
  lead_id?: number | null;
  connector_type?: string;
  chat_id?: number;
}

const AUTO_HIDE_MS = 30000;

export function IncomingCallCard() {
  const { addMessageListener } = useChatWebSocketContext();
  const [call, setCall] = useState<CallCard | null>(null);

  const dismiss = useCallback(() => setCall(null), []);

  // Подписка на события звонка из общего WS чата.
  useEffect(() => {
    return addMessageListener((msg: any) => {
      if (msg?.type === 'call.incoming' && msg.call) {
        setCall({ ...msg.call, chat_id: msg.chat_id });
      } else if (msg?.type === 'call.ended' && msg.call) {
        // Эфемерный ARI-попап приходит без message_id → снимаем по номеру;
        // событийные провайдеры (с message_id) — по message_id.
        setCall(prev => {
          if (!prev) return prev;
          const sameMsg =
            msg.call.message_id != null &&
            prev.message_id === msg.call.message_id;
          const sameNum =
            msg.call.number != null && prev.number === msg.call.number;
          return sameMsg || sameNum ? null : prev;
        });
      }
    });
  }, [addMessageListener]);

  // Страховочное авто-скрытие (на случай, если call.ended не пришёл).
  useEffect(() => {
    if (!call) return;
    const t = setTimeout(() => setCall(null), AUTO_HIDE_MS);
    return () => clearTimeout(t);
  }, [call]);

  if (!call) return null;

  const isIncoming = call.direction === 'incoming';
  const Icon = isIncoming ? IconPhoneIncoming : IconPhoneOutgoing;
  const title = isIncoming ? 'Входящий звонок' : 'Исходящий звонок';
  const answered = call.disposition === 'answered';

  const target = call.lead_id
    ? `/leads/${call.lead_id}`
    : call.partner_id
      ? `/partners/${call.partner_id}`
      : call.chat_id
        ? '/chat'
        : null;
  const targetLabel = call.lead_id
    ? 'Открыть лид'
    : call.partner_id
      ? 'Открыть партнёра'
      : 'Открыть чат';

  return (
    <Paper
      shadow="md"
      p="md"
      radius="md"
      withBorder
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        width: 320,
        zIndex: 3000,
      }}>
      <Group justify="space-between" wrap="nowrap" mb={6}>
        <Group gap={10} wrap="nowrap">
          <ThemeIcon
            size={40}
            radius="xl"
            variant="light"
            color={answered ? 'green' : 'blue'}>
            <Icon size={22} />
          </ThemeIcon>
          <div>
            <Text fw={600} size="sm">
              {title}
            </Text>
            <Text size="xs" c="dimmed">
              {answered ? 'Разговор' : 'Дозвон…'}
              {call.connector_type ? ` · ${call.connector_type}` : ''}
            </Text>
          </div>
        </Group>
        <ActionIcon variant="subtle" color="gray" onClick={dismiss}>
          <IconX size={16} />
        </ActionIcon>
      </Group>

      <Text fw={500}>{call.name || call.number || '—'}</Text>
      {call.number && call.name && (
        <Text size="xs" c="dimmed">
          {call.number}
        </Text>
      )}

      {target && (
        <Anchor
          component={Link}
          to={target}
          size="sm"
          onClick={dismiss}
          mt={8}
          style={{ display: 'inline-block' }}>
          {targetLabel}
        </Anchor>
      )}
    </Paper>
  );
}

export default IncomingCallCard;
