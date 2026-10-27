// Copyright 2025 FARA CRM
// Ячейки списка звонков: направление, статус, «внутренний», длительность,
// номер контрагента и запись разговора.
//
// Раньше эта разметка жила внутри кастомной страницы «Звонки». Экран стал
// обычным list/form (модель call), поэтому оформление вынесено в Cell-
// компоненты — как BooleanCell/RelationCell, только специфичные для телефонии.

import { useTranslation } from 'react-i18next';
import {
  ActionIcon,
  Badge,
  Box,
  Group,
  Popover,
  Text,
  ThemeIcon,
  Tooltip,
} from '@mantine/core';
import {
  IconArrowNarrowLeft,
  IconArrowNarrowRight,
  IconArrowsExchange2,
  IconDownload,
  IconPlayerPlayFilled,
} from '@tabler/icons-react';
import { AudioPlayer } from '@/components/Attachment/AudioPlayer';
import { attachmentContentUrl } from '@/utils/attachmentUrls';

export type CallDirection = 'incoming' | 'outgoing';
export type CallDisposition =
  | 'answered'
  | 'no_answer'
  | 'busy'
  | 'failed'
  | 'cancelled';

/** Поля записи звонка, которые нужны ячейкам. */
export interface CallRecord {
  id: number | string;
  direction?: CallDirection | null;
  disposition?: CallDisposition | null;
  is_internal?: boolean;
  number_from?: string | null;
  number_to?: string | null;
  duration_talk?: number | null;
  /** Запись разговора — вложение (m2o), приходит как {id, name}. */
  record_id?: { id: number; name?: string | null } | null;
  [key: string]: any;
}

// Цвет статуса звонка: зелёный — состоялся, красный — пропущен/не отвечен,
// жёлтый — ошибка/техническая проблема, серый — отменён.
const DISPOSITION_COLOR: Record<string, string> = {
  answered: 'green',
  no_answer: 'red',
  busy: 'red',
  failed: 'yellow',
  cancelled: 'gray',
};

export function dispositionColor(value?: string | null): string {
  return DISPOSITION_COLOR[value ?? ''] || 'gray';
}

const Dash = () => (
  <Text size="sm" c="dimmed">
    —
  </Text>
);

/** Направление: стрелка (цвет — по статусу) + слово. */
export function CallDirectionCell({ record }: { record: CallRecord }) {
  const { t } = useTranslation('chat');
  const outgoing = record.direction === 'outgoing';

  return (
    <Group gap={6} wrap="nowrap" align="center">
      <ThemeIcon
        variant="transparent"
        size="sm"
        color={dispositionColor(record.disposition)}>
        {outgoing ? (
          <IconArrowNarrowRight size={18} />
        ) : (
          <IconArrowNarrowLeft size={18} />
        )}
      </ThemeIcon>
      <Text size="sm">
        {outgoing
          ? t('calls.outgoing', 'Исходящий')
          : t('calls.incoming', 'Входящий')}
      </Text>
    </Group>
  );
}

/** Статус звонка — цветная плашка с локализованным названием. */
export function CallDispositionCell({ value }: { value?: string | null }) {
  const { t } = useTranslation('chat');
  if (!value) return <Dash />;

  const labels: Record<string, string> = {
    answered: t('calls.answered', 'Отвечено'),
    no_answer: t('calls.noAnswer', 'Не отвечено'),
    busy: t('calls.busy', 'Занято'),
    failed: t('calls.failed', 'Ошибка'),
    cancelled: t('calls.cancelled', 'Отменён'),
  };

  return (
    <Badge color={dispositionColor(value)} variant="light" size="sm">
      {labels[value] || value}
    </Badge>
  );
}

/** Внутренний звонок (сотрудник ↔ сотрудник). */
export function CallInternalCell({ value }: { value?: boolean }) {
  const { t } = useTranslation('chat');
  if (!value) return <Dash />;

  return (
    <Tooltip label={t('calls.internal', 'Внутренний')}>
      <ThemeIcon variant="light" color="grape" radius="xl" size="md">
        <IconArrowsExchange2 size={16} />
      </ThemeIcon>
    </Tooltip>
  );
}

/** Длительность разговора в м:сс. */
export function CallDurationCell({ value }: { value?: number | null }) {
  if (!value) return <Dash />;
  const minutes = Math.floor(value / 60);
  const seconds = value % 60;
  return <Text size="sm">{`${minutes}:${String(seconds).padStart(2, '0')}`}</Text>;
}

/** Запись разговора: кнопка «play» (плеер раскрывается поповером) и
 *  «скачать» — та же ссылка на содержимое вложения, что в списке файлов. */
export function CallRecordCell({ record }: { record: CallRecord }) {
  const { t } = useTranslation('chat');
  const recording = record.record_id;

  if (!recording) return <Dash />;

  return (
    // Клик по строке открывает форму звонка — плееру это не нужно, поэтому
    // гасим всплытие ОБЁРТКОЙ. Вешать onClick на саму кнопку нельзя: Popover
    // пробрасывает в неё свой обработчик открытия, а Tooltip спредит props
    // ребёнка последними — собственный onClick затирал бы открытие поповера.
    <Box
      style={{ display: 'inline-flex', gap: 4 }}
      onClick={event => event.stopPropagation()}>
      <Popover position="left" shadow="md" withArrow withinPortal>
        <Popover.Target>
          <Tooltip label={t('calls.recordPlay', 'Прослушать')}>
            <ActionIcon variant="light" radius="xl" color="blue">
              <IconPlayerPlayFilled size={14} />
            </ActionIcon>
          </Tooltip>
        </Popover.Target>
        <Popover.Dropdown>
          <Box w={280}>
            <AudioPlayer attachmentId={recording.id} />
          </Box>
        </Popover.Dropdown>
      </Popover>
      <Tooltip label={t('calls.recordDownload', 'Скачать запись')}>
        <ActionIcon
          variant="light"
          radius="xl"
          color="gray"
          component="a"
          href={attachmentContentUrl(recording.id)}
          download={recording.name || 'recording'}>
          <IconDownload size={14} />
        </ActionIcon>
      </Tooltip>
    </Box>
  );
}
