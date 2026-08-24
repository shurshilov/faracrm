// Copyright 2025 FARA CRM
// Звонилка: иконка в шапке, набор номера, книжка и плашка текущего разговора.
//
// Книжка одна на всех — модель contact полиморфна (партнёр ИЛИ сотрудник), а у
// партнёра своего поля телефона нет вовсе. Поэтому «Клиенты» и «Сотрудники» это
// не две вкладки, а одна выдача с пометкой владельца.

import { useMemo, useState } from 'react';
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Divider,
  Group,
  Indicator,
  List,
  Popover,
  ScrollArea,
  SimpleGrid,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core';
import {
  IconMicrophone,
  IconMicrophoneOff,
  IconPhone,
  IconPhoneOff,
  IconSearch,
} from '@tabler/icons-react';
import { useSearchQuery } from '@/services/api/crudApi';
import { FilterExpression } from '@/services/api/crudTypes';
import { useSipPhone, SipState } from './useSipPhone';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'];

const STATE_LABEL: Record<SipState, string> = {
  disabled: 'Звонилка не настроена',
  offline: 'Нет связи с АТС',
  registered: 'Готов к звонку',
  calling: 'Вызов…',
  incoming: 'Входящий',
  active: 'Разговор',
};

/** Синий — можно звонить, жёлтый — не настроено, красный — АТС не отвечает. */
const STATE_COLOR: Record<SipState, string> = {
  disabled: 'yellow',
  offline: 'red',
  registered: 'blue',
  calling: 'blue',
  incoming: 'green',
  active: 'green',
};

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

/** Телефонные контакты клиентов и сотрудников одной выдачей. */
function usePhoneContacts(search: string) {
  const { data: types } = useSearchQuery({
    model: 'contact_type',
    fields: ['id'],
    filter: [['is_phone_format', '=', true]],
    limit: 50,
  });

  const typeIds = useMemo(
    () => (types?.data || []).map((t: any) => t.id),
    [types],
  );

  const query = search.trim();
  const filter: FilterExpression = [
    ['contact_type_id', 'in', typeIds],
    ['active', '=', true],
  ];
  if (query) {
    filter.push(['value', 'ilike', query]);
  }

  const { data } = useSearchQuery(
    {
      model: 'contact',
      fields: ['id', 'value', 'name', 'partner_id', 'user_id'],
      filter,
      limit: 20,
    },
    { skip: !typeIds.length },
  );

  return (data?.data || []) as any[];
}

export function SipPhoneButton() {
  const phone = useSipPhone();
  const [opened, setOpened] = useState(false);
  const [number, setNumber] = useState('');
  const [search, setSearch] = useState('');
  const contacts = usePhoneContacts(search);

  // Кнопка видна ВСЕГДА: ненастроенная звонилка должна объяснить, чего ей не
  // хватает, а не молча отсутствовать. SIP-библиотека при этом не грузится —
  // это решает сам хук по ответу бэкенда.
  const ready = phone.state !== 'disabled';
  const busy = ['calling', 'incoming', 'active'].includes(phone.state);

  const dial = (target: string) => {
    setOpened(false);
    phone.call(target);
  };

  return (
    <>
      <Popover
        opened={opened}
        onChange={setOpened}
        position="bottom-end"
        shadow="md"
        withArrow>
        <Popover.Target>
          <Indicator size={8} offset={4} color={STATE_COLOR[phone.state]}>
            <Tooltip label={STATE_LABEL[phone.state]}>
              <ActionIcon
                variant="subtle"
                size="lg"
                radius="md"
                onClick={() => setOpened(o => !o)}>
                <IconPhone size={22} stroke={1.5} />
              </ActionIcon>
            </Tooltip>
          </Indicator>
        </Popover.Target>

        <Popover.Dropdown p="sm">
          <Box w={260}>
            <Group justify="space-between" mb="xs">
              <Text size="xs" c="dimmed">
                {STATE_LABEL[phone.state]}
              </Text>
              {phone.error && (
                <Text size="xs" c="red" lineClamp={1}>
                  {phone.error}
                </Text>
              )}
            </Group>

            {!ready && (
              <>
                <Text size="xs" mb={4}>
                  Чтобы звонить из CRM, осталось настроить:
                </Text>
                <List size="xs" spacing={4} c="dimmed">
                  {phone.todo.map(item => (
                    <List.Item key={item}>{item}</List.Item>
                  ))}
                </List>
              </>
            )}

            {ready && (
            <>
            <Group gap="xs" wrap="nowrap">
              <TextInput
                flex={1}
                value={number}
                onChange={e => setNumber(e.currentTarget.value)}
                onKeyDown={e => e.key === 'Enter' && dial(number)}
                placeholder="Номер"
              />
              <ActionIcon
                color="green"
                variant="filled"
                size="lg"
                disabled={busy || !number.trim()}
                onClick={() => dial(number)}>
                <IconPhone size={18} />
              </ActionIcon>
            </Group>

            <SimpleGrid cols={3} spacing={4} mt="xs">
              {KEYS.map(key => (
                <Button
                  key={key}
                  variant="default"
                  size="compact-md"
                  onClick={() => setNumber(n => n + key)}>
                  {key}
                </Button>
              ))}
            </SimpleGrid>

            <Divider my="sm" label="Записная книжка" labelPosition="center" />

            <TextInput
              size="xs"
              value={search}
              onChange={e => setSearch(e.currentTarget.value)}
              placeholder="Поиск по номеру"
              leftSection={<IconSearch size={14} />}
            />
            <ScrollArea.Autosize mah={180} mt="xs">
              {contacts.map(contact => (
                <Group
                  key={contact.id}
                  justify="space-between"
                  wrap="nowrap"
                  gap="xs"
                  py={4}
                  style={{ cursor: 'pointer' }}
                  onClick={() => dial(contact.value)}>
                  <Box style={{ minWidth: 0 }}>
                    <Text size="sm" lineClamp={1}>
                      {contact.partner_id?.name ||
                        contact.user_id?.name ||
                        contact.value}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {contact.value}
                    </Text>
                  </Box>
                  {contact.user_id && (
                    <Badge size="xs" variant="light">
                      сотрудник
                    </Badge>
                  )}
                </Group>
              ))}
              {!contacts.length && (
                <Text size="xs" c="dimmed" ta="center" py="sm">
                  Ничего не найдено
                </Text>
              )}
            </ScrollArea.Autosize>
            </>
            )}
          </Box>
        </Popover.Dropdown>
      </Popover>

      {busy && (
        // Плашка разговора. Ниже карточки клиента от бэкенда (bottom 24,
        // z-index 3000) и выше виджета внутренних звонков (z-index 1000).
        <Box
          style={{
            position: 'fixed',
            right: 24,
            bottom: 96,
            zIndex: 2000,
            background: 'var(--mantine-color-body)',
            border: '1px solid var(--mantine-color-default-border)',
            borderRadius: 12,
            padding: 12,
            boxShadow: 'var(--mantine-shadow-md)',
            minWidth: 260,
          }}>
          <Group justify="space-between" wrap="nowrap">
            <Box style={{ minWidth: 0 }}>
              <Text size="sm" fw={600} lineClamp={1}>
                {phone.peer || 'Звонок'}
              </Text>
              <Text size="xs" c="dimmed">
                {phone.state === 'active'
                  ? formatDuration(phone.duration)
                  : STATE_LABEL[phone.state]}
              </Text>
            </Box>
            <Group gap="xs" wrap="nowrap">
              {phone.state === 'incoming' && (
                <ActionIcon
                  color="green"
                  variant="filled"
                  radius="xl"
                  onClick={phone.answer}>
                  <IconPhone size={18} />
                </ActionIcon>
              )}
              {phone.state === 'active' && (
                <ActionIcon
                  variant="light"
                  radius="xl"
                  onClick={phone.toggleMute}>
                  {phone.muted ? (
                    <IconMicrophoneOff size={18} />
                  ) : (
                    <IconMicrophone size={18} />
                  )}
                </ActionIcon>
              )}
              <ActionIcon
                color="red"
                variant="filled"
                radius="xl"
                onClick={phone.hangup}>
                <IconPhoneOff size={18} />
              </ActionIcon>
            </Group>
          </Group>

          {phone.state === 'active' && (
            <SimpleGrid cols={3} spacing={4} mt="xs">
              {KEYS.map(key => (
                <Button
                  key={key}
                  variant="default"
                  size="compact-xs"
                  onClick={() => phone.sendDtmf(key)}>
                  {key}
                </Button>
              ))}
            </SimpleGrid>
          )}
        </Box>
      )}
    </>
  );
}

export default SipPhoneButton;
