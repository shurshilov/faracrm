// Copyright 2025 FARA CRM
// Экран «Звонки» — реестр звонков телефонных коннекторов с
// инлайн-проигрыванием записи + сводная аналитика.
//
// Данные берутся из /telephony/calls и /telephony/calls/stats (см.
// services/api/telephony.ts). Звонок — независимая сущность (таблица call);
// в историю чата он подмешивается на чтении как call_external.

import { Fragment, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Anchor,
  Badge,
  Box,
  Card,
  Center,
  Group,
  Loader,
  ScrollArea,
  Select,
  SimpleGrid,
  Table,
  Text,
  TextInput,
  ThemeIcon,
  Tooltip,
  ActionIcon,
} from '@mantine/core';
import {
  IconArrowsExchange2,
  IconArrowNarrowLeft,
  IconArrowNarrowRight,
  IconSearch,
  IconPlayerPlayFilled,
  IconChevronUp,
} from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { AudioPlayer } from '@/components/Attachment/AudioPlayer';
import {
  useGetCallsQuery,
  useGetCallsStatsQuery,
  CallRow,
} from '@/services/api/telephony';

// Кол-во колонок таблицы (для colSpan раскрывающейся строки записи и «пусто»).
const COLUMN_COUNT = 11;

// Цвет статуса звонка: зелёный — состоялся, красный — пропущен/не отвечен,
// жёлтый — ошибка/техническая проблема, серый — отменён, синий — в процессе.
const dispositionColor: Record<string, string> = {
  answered: 'green',
  no_answer: 'red',
  busy: 'red',
  failed: 'yellow',
  cancelled: 'gray',
  ringing: 'blue',
};

function fmtDuration(sec: number | null): string {
  if (!sec) return '—';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <Card withBorder padding="sm">
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text size="xl" fw={700} c={color}>
        {value}
      </Text>
    </Card>
  );
}

export function CallsPage() {
  const { t } = useTranslation('common');
  const [direction, setDirection] = useState<string | null>(null);
  const [disposition, setDisposition] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  // id звонка с раскрытым плеером записи (одна запись открыта за раз).
  const [openRecord, setOpenRecord] = useState<number | null>(null);

  const params = {
    limit: 100,
    ...(direction ? { direction } : {}),
    ...(disposition ? { disposition } : {}),
    ...(search ? { search } : {}),
  };
  const { data, isFetching } = useGetCallsQuery(params);
  const { data: stats } = useGetCallsStatsQuery({});

  const calls: CallRow[] = data?.data ?? [];
  const statRows = stats?.data ?? [];
  const sum = (
    pred: (r: { direction: string | null; disposition: string | null }) => boolean,
  ) => statRows.filter(pred).reduce((a, r) => a + Number(r.cnt), 0);
  const total = statRows.reduce((a, r) => a + Number(r.cnt), 0);
  const answered = sum(r => r.disposition === 'answered');
  const missed = sum(r =>
    ['no_answer', 'busy', 'failed', 'cancelled'].includes(r.disposition ?? ''),
  );
  const incoming = sum(r => r.direction === 'incoming');

  const directionWord = (c: CallRow) =>
    c.call_direction === 'outgoing'
      ? t('calls.outgoing', 'Исходящий')
      : t('calls.incoming', 'Входящий');

  return (
    <Box p="md">
      <SimpleGrid cols={{ base: 2, sm: 4 }} mb="md">
        <StatCard label={t('calls.total', 'Всего')} value={total} />
        <StatCard
          label={t('calls.answered', 'Отвечено')}
          value={answered}
          color="green"
        />
        <StatCard
          label={t('calls.missed', 'Пропущено')}
          value={missed}
          color="red"
        />
        <StatCard
          label={t('calls.incoming', 'Входящие')}
          value={incoming}
          color="blue"
        />
      </SimpleGrid>

      <Group mb="md" gap="sm">
        <Select
          placeholder={t('calls.direction', 'Направление')}
          clearable
          value={direction}
          onChange={setDirection}
          data={[
            { value: 'incoming', label: t('calls.incoming', 'Входящие') },
            { value: 'outgoing', label: t('calls.outgoing', 'Исходящие') },
          ]}
          w={160}
        />
        <Select
          placeholder={t('calls.disposition', 'Статус')}
          clearable
          value={disposition}
          onChange={setDisposition}
          data={[
            { value: 'answered', label: t('calls.answered', 'Отвечено') },
            { value: 'no_answer', label: t('calls.noAnswer', 'Не отвечено') },
            { value: 'busy', label: t('calls.busy', 'Занято') },
            { value: 'failed', label: t('calls.failed', 'Ошибка') },
            { value: 'cancelled', label: t('calls.cancelled', 'Отменён') },
          ]}
          w={160}
        />
        <TextInput
          placeholder={t('calls.search', 'Поиск по номеру / имени')}
          leftSection={<IconSearch size={16} />}
          value={search}
          onChange={e => setSearch(e.currentTarget.value)}
          w={260}
        />
      </Group>

      {isFetching ? (
        <Center py="xl">
          <Loader />
        </Center>
      ) : (
        <ScrollArea>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('calls.time', 'Время')}</Table.Th>
                <Table.Th>{t('calls.employee', 'Сотрудник')}</Table.Th>
                <Table.Th>{t('calls.ourNumber', 'Наш номер')}</Table.Th>
                <Table.Th>{t('calls.direction', 'Направление')}</Table.Th>
                <Table.Th>{t('calls.contact', 'Контакт')}</Table.Th>
                <Table.Th>{t('calls.partner', 'Партнёр')}</Table.Th>
                <Table.Th>{t('calls.lead', 'Лид')}</Table.Th>
                <Table.Th>{t('calls.disposition', 'Статус')}</Table.Th>
                <Table.Th ta="center">{t('calls.internalShort', 'Внутр.')}</Table.Th>
                <Table.Th>{t('calls.duration', 'Длит.')}</Table.Th>
                <Table.Th ta="right">{t('calls.record', 'Запись')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {calls.map(c => {
                const color = dispositionColor[c.call_disposition ?? ''] || 'gray';
                const isOpen = openRecord === c.id;
                return (
                  <Fragment key={c.id}>
                    <Table.Tr>
                      <Table.Td>
                        <Text size="sm">{fmtTime(c.started_at)}</Text>
                      </Table.Td>
                      {/* Наш сотрудник */}
                      <Table.Td>
                        <Text size="sm">{c.operator_name || '—'}</Text>
                      </Table.Td>
                      {/* Наш номер (линия) */}
                      <Table.Td>
                        <Text size="sm" fw={600}>
                          {c.line_number || '—'}
                        </Text>
                      </Table.Td>
                      {/* Направление: слово + стрелка */}
                      <Table.Td>
                        <Group gap={6} wrap="nowrap" align="center">
                          <ThemeIcon
                            variant="transparent"
                            size="sm"
                            color={color}>
                            {c.call_direction === 'outgoing' ? (
                              <IconArrowNarrowRight size={18} />
                            ) : (
                              <IconArrowNarrowLeft size={18} />
                            )}
                          </ThemeIcon>
                          <Text size="sm">{directionWord(c)}</Text>
                        </Group>
                      </Table.Td>
                      {/* Контакт */}
                      <Table.Td>
                        <Text size="sm">{c.client_number || '—'}</Text>
                      </Table.Td>
                      {/* Партнёр */}
                      <Table.Td>
                        {c.partner_id ? (
                          <Anchor
                            component={Link}
                            to={`/partners/${c.partner_id}`}
                            size="sm">
                            {c.partner_name}
                          </Anchor>
                        ) : (
                          <Text size="sm" c="dimmed">
                            —
                          </Text>
                        )}
                      </Table.Td>
                      {/* Лид */}
                      <Table.Td>
                        {c.lead_id ? (
                          <Anchor
                            component={Link}
                            to={`/leads/${c.lead_id}`}
                            size="sm">
                            #{c.lead_id}
                          </Anchor>
                        ) : (
                          <Text size="sm" c="dimmed">
                            —
                          </Text>
                        )}
                      </Table.Td>
                      {/* Статус */}
                      <Table.Td>
                        <Badge color={color} variant="light" size="sm">
                          {c.call_disposition ?? '—'}
                        </Badge>
                      </Table.Td>
                      {/* Внутренний */}
                      <Table.Td ta="center">
                        {c.is_internal ? (
                          <Tooltip label={t('calls.internal', 'Внутренний')}>
                            <ThemeIcon
                              variant="light"
                              color="grape"
                              radius="xl"
                              size="md">
                              <IconArrowsExchange2 size={16} />
                            </ThemeIcon>
                          </Tooltip>
                        ) : (
                          <Text size="sm" c="dimmed">
                            —
                          </Text>
                        )}
                      </Table.Td>
                      {/* Длит. */}
                      <Table.Td>
                        <Text size="sm">{fmtDuration(c.call_talk_duration)}</Text>
                      </Table.Td>
                      {/* Запись — самый правый столбец, раскрывается по клику. */}
                      <Table.Td ta="right">
                        {c.record_id ? (
                          <Tooltip
                            label={
                              isOpen
                                ? t('calls.recordHide', 'Свернуть')
                                : t('calls.recordPlay', 'Прослушать')
                            }>
                            <ActionIcon
                              variant={isOpen ? 'filled' : 'light'}
                              radius="xl"
                              color="blue"
                              onClick={() =>
                                setOpenRecord(isOpen ? null : c.id)
                              }>
                              {isOpen ? (
                                <IconChevronUp size={16} />
                              ) : (
                                <IconPlayerPlayFilled size={14} />
                              )}
                            </ActionIcon>
                          </Tooltip>
                        ) : (
                          <Text size="sm" c="dimmed">
                            —
                          </Text>
                        )}
                      </Table.Td>
                    </Table.Tr>
                    {c.record_id && isOpen && (
                      <Table.Tr>
                        <Table.Td colSpan={COLUMN_COUNT} p={0}>
                          <Box px="md" py="xs">
                            <AudioPlayer attachmentId={c.record_id} />
                          </Box>
                        </Table.Td>
                      </Table.Tr>
                    )}
                  </Fragment>
                );
              })}
              {calls.length === 0 && (
                <Table.Tr>
                  <Table.Td colSpan={COLUMN_COUNT}>
                    <Center py="xl">
                      <Text c="dimmed">{t('calls.empty', 'Звонков нет')}</Text>
                    </Center>
                  </Table.Td>
                </Table.Tr>
              )}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      )}
    </Box>
  );
}

export default CallsPage;
