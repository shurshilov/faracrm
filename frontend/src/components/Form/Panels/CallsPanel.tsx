/**
 * CallsPanel — история звонков с клиентом на форме записи (лид, заказ,
 * партнёр): отфильтрованный вид тех же коммуникаций, что в панели «Чат»
 * (там звонки подмешаны в переписку), по аналогии с «Вложениями» (файлы из
 * заметок видны и там).
 *
 * От чата не зависит: звонки берутся по партнёру записи напрямую из таблицы
 * call, поэтому клиент, который только звонил, историю здесь получает без
 * «Создать чат». Партнёр записи — тем же резолвом, что и панель «Чат» (RTK
 * отдаёт его из кеша). Клик по строке открывает форму звонка; плеер записи
 * всплытие гасит сам (CallRecordCell).
 */

import { useState } from 'react';
import {
  Button,
  Group,
  Loader,
  Stack,
  Text,
  UnstyledButton,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useSearchQuery } from '@/services/api/crudApi';
import { useResolveRecordPartnerChatQuery } from '@/services/api/chat';
import { DateTimeCell } from '@/components/ListCells';
import {
  CallDirectionCell,
  CallDispositionCell,
  CallDurationCell,
  CallRecordCell,
  CallRecord,
} from '@/fara_telephony/CallCells';

const PAGE_SIZE = 50;

interface CallsPanelProps {
  resModel: string;
  resId: number;
}

export function CallsPanel({ resModel, resId }: CallsPanelProps) {
  const { t } = useTranslation(['common']);
  const navigate = useNavigate();
  const [limit, setLimit] = useState(PAGE_SIZE);

  const resolve = useResolveRecordPartnerChatQuery({ resModel, resId });
  const partnerId = resolve.data?.partner_id ?? null;

  const { data, isLoading } = useSearchQuery(
    {
      model: 'call',
      fields: [
        'id',
        'started_at',
        'direction',
        'disposition',
        'number_from',
        'number_to',
        'duration_talk',
        'record_id',
      ],
      filter: [
        ['partner_id', '=', partnerId ?? 0],
        ['active', '=', true],
      ],
      sort: 'started_at',
      order: 'desc',
      limit,
    },
    { skip: !partnerId },
  );
  const calls = (data?.data || []) as CallRecord[];
  const total = Number(data?.total || 0);

  if (resolve.isLoading || (isLoading && calls.length === 0)) {
    return (
      <Stack align="center" py="xl">
        <Loader size="sm" />
      </Stack>
    );
  }

  if (!partnerId || calls.length === 0) {
    return (
      <Text size="sm" c="dimmed" ta="center" py="md">
        {t('common:noCalls', 'Звонков нет')}
      </Text>
    );
  }

  return (
    <Stack gap={0}>
      {calls.map(call => {
        // Номер клиента — нога, противоположная нашей линии.
        const number =
          call.direction === 'incoming' ? call.number_from : call.number_to;
        return (
          <UnstyledButton
            key={call.id}
            px="xs"
            py="sm"
            style={{
              borderBottom: '1px solid var(--mantine-color-default-border)',
            }}
            onClick={() => navigate(`/call/${call.id}`)}>
            <Group justify="space-between" wrap="nowrap">
              <CallDirectionCell record={call} />
              <DateTimeCell value={call.started_at} />
            </Group>
            <Group justify="space-between" wrap="nowrap" mt={4}>
              <Text size="sm" c="dimmed" truncate>
                {number || '—'}
              </Text>
              <Group gap="xs" wrap="nowrap">
                <CallDurationCell value={call.duration_talk} />
                <CallDispositionCell value={call.disposition} />
                <CallRecordCell record={call} />
              </Group>
            </Group>
          </UnstyledButton>
        );
      })}

      {total > calls.length && (
        <Button
          variant="subtle"
          size="compact-sm"
          onClick={() => setLimit(prev => prev + PAGE_SIZE)}
          loading={isLoading}
          fullWidth>
          {t('common:loadMore', 'Загрузить ещё')} ({total - calls.length})
        </Button>
      )}
    </Stack>
  );
}
