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
  List,
  Popover,
  Select,
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
  IconRefresh,
  IconSearch,
} from '@tabler/icons-react';
import { useSelector } from 'react-redux';
import type { RootState } from '@/store/store';
import { useSearchQuery, useUpdateMutation } from '@/services/api/crudApi';
import { useGetSipConfigQuery } from '@/services/api/telephony';
import { FilterExpression } from '@/services/api/crudTypes';
import { useCall } from '@/fara_chat/context/CallContext';
import { useChatWebSocketContext } from '@/fara_chat/context';
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

/** Телефонные контакты клиентов и сотрудников одной выдачей (канал SIP). */
function usePhoneContacts(search: string, enabled: boolean) {
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

  const { data, refetch } = useSearchQuery(
    {
      model: 'contact',
      fields: ['id', 'value', 'name', 'partner_id', 'user_id'],
      filter,
      limit: 20,
    },
    { skip: !enabled || !typeIds.length },
  );

  return { contacts: (data?.data || []) as any[], refetch };
}

/** Внутренний канал — псевдо-коннектор: он есть всегда и ничего не требует. */
const INTERNAL = 'internal';

/**
 * Сотрудники для внутреннего канала. Берём ПОЛЬЗОВАТЕЛЕЙ, а не контакты:
 * внутренний звонок адресуется user_id, номер в нём не участвует вовсе —
 * значит и сотрудник без телефонного контакта должен быть в списке.
 */
function useEmployees(search: string, enabled: boolean) {
  // У модели users нет поля active — фильтруем только по имени, а без поиска
  // фильтр не шлём вовсе.
  const query = search.trim();
  const filter: FilterExpression | undefined = query
    ? [['name', 'ilike', query]]
    : undefined;

  const { data, refetch } = useSearchQuery(
    { model: 'users', fields: ['id', 'name'], filter, limit: 50, sort: 'name' },
    { skip: !enabled },
  );
  return {
    employees: (data?.data || []) as { id: number; name: string }[],
    refetch,
  };
}

export function SipPhoneButton() {
  const internalCall = useCall();
  const [opened, setOpened] = useState(false);
  const [number, setNumber] = useState('');
  const [search, setSearch] = useState('');

  // Канал по умолчанию — на пользователе (как настройки уведомлений).
  const session = useSelector((s: RootState) => s.auth.session);
  const [updateUser] = useUpdateMutation();
  const savedChannel = session?.user_id?.call_connector_id?.id;
  const [channel, setChannel] = useState<string>(
    savedChannel ? String(savedChannel) : INTERNAL,
  );

  // Регистрируемся ВСЕГДА, а не только когда телефонный канал выбран в
  // списке. Список отвечает на вопрос «чем звонить», а принимать надо на
  // обоих каналах сразу: внутренние звонки приходят по сокету чата и так, а
  // с АТС приходили только в ту вкладку, где канал выбран прямо сейчас.
  // Приоритет у выбранного, иначе канал по умолчанию, иначе первый рабочий.
  const { data: sipConfig } = useGetSipConfigQuery();
  const sipChannels = sipConfig?.data?.channels || [];
  const fallbackSipId =
    sipChannels.find(c => c.id === savedChannel && c.available)?.id ??
    sipChannels.find(c => c.available)?.id ??
    null;
  const phone = useSipPhone(
    channel === INTERNAL ? fallbackSipId : Number(channel),
  );

  // Телефонные каналы в списке ВСЕГДА — выбор канала это и есть способ узнать,
  // чего ему не хватает.
  const channels = [
    { value: INTERNAL, label: 'Внутренний (сотруднику)' },
    ...phone.channels.map(c => ({ value: String(c.id), label: c.name })),
  ];
  const viaSip = channel !== INTERNAL;

  // Внутренний канал — сотрудники со статусом, SIP — телефонные контакты.
  const { contacts, refetch: refetchContacts } = usePhoneContacts(
    search,
    viaSip,
  );
  const { employees, refetch: refetchEmployees } = useEmployees(
    search,
    !viaSip,
  );
  const { isUserOnline } = useChatWebSocketContext();
  const myId = session?.user_id?.id;
  // Сначала те, кому реально можно позвонить.
  const employeeList = employees
    .filter(user => user.id !== myId)
    .sort((a, b) => Number(isUserOnline(b.id)) - Number(isUserOnline(a.id)));

  const rememberChannel = async (value: string) => {
    setChannel(value);
    if (!session?.user_id?.id) return;
    try {
      await updateUser({
        model: 'users',
        id: session.user_id.id,
        values: {
          call_connector_id: value === INTERNAL ? null : Number(value),
        },
      });
    } catch {
      /* не смогли запомнить — выбор всё равно действует в этой сессии */
    }
  };

  // Кнопка видна ВСЕГДА: ненастроенная звонилка должна объяснить, чего ей не
  // хватает, а не молча отсутствовать. SIP-библиотека при этом не грузится —
  // это решает сам хук по ответу бэкенда.
  const ready = phone.state !== 'disabled';
  const busy = ['calling', 'incoming', 'active'].includes(phone.state);

  /**
   * Набор номера — только по SIP: у внутреннего звонка адресат это ПОЛЬЗОВАТЕЛЬ
   * CRM, а не номер, поэтому там звонят из книжки (см. dialContact).
   */
  const dial = (target: string) => {
    setOpened(false);
    phone.call(target);
  };

  const dialContact = (contact: any) => dial(contact.value);

  /**
   * Внутренний звонок сотруднику — существующий механизм между браузерами.
   * Плашку разговора рисует уже смонтированный CallWidget, своя не нужна.
   */
  const dialUser = (user: { id: number; name: string }) => {
    setOpened(false);
    internalCall.startCall(user);
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
          {/* Без индикатора на самой иконке: состояние относится к ВЫБРАННОМУ
              каналу, а внутренний готов всегда — точка была бы всегда одного
              цвета и ни о чём не говорила. Статус показываем внутри, рядом с
              выбором канала. */}
          <Tooltip label="Звонки">
            <ActionIcon
              variant="subtle"
              size="lg"
              radius="md"
              onClick={() => setOpened(o => !o)}>
              <IconPhone size={22} stroke={1.5} />
            </ActionIcon>
          </Tooltip>
        </Popover.Target>

        <Popover.Dropdown p="sm">
          <Box w={260}>
            <Select
              size="xs"
              mb="xs"
              label="Чем звонить"
              data={channels}
              value={channel}
              onChange={v => v && rememberChannel(v)}
              allowDeselect={false}
              // БЕЗ портала: в портале опции живут вне DOM поповера, и клик по
              // ним считается кликом снаружи — поповер закрывался раньше, чем
              // срабатывал выбор канала.
              comboboxProps={{ withinPortal: false }}
            />

            <Group justify="space-between" mb="xs" wrap="nowrap">
              <Badge
                variant="dot"
                size="sm"
                color={viaSip ? STATE_COLOR[phone.state] : 'blue'}>
                {viaSip ? STATE_LABEL[phone.state] : 'Готов к звонку'}
              </Badge>
            </Group>

            {/* Ошибка — отдельной строкой во всю ширину. Рядом с бейджем она
                жила с lineClamp={1}, и от подсказки оставалось несколько
                слов: как раз то место, где нужно объяснить, что чинить. */}
            {viaSip && phone.error && (
              <Text size="xs" c="red" mb="xs">
                {phone.error}
              </Text>
            )}

            {viaSip && !ready && (
              <>
                <Text size="xs" mb={4}>
                  Чтобы звонить этим каналом, осталось настроить:
                </Text>
                <List size="xs" spacing={4} c="dimmed">
                  {phone.todo.map(item => (
                    <List.Item key={item}>{item}</List.Item>
                  ))}
                </List>
              </>
            )}

            {/* Набор номера — только у SIP: внутренним звонят конкретному
                сотруднику, а не на номер. */}
            {viaSip && ready && (
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
              </>
            )}

            {/* Ненастроенный SIP-канал книжку не показывает: звонить с него
                всё равно нельзя, а клик по контакту молча ничего не делал бы. */}
            {(!viaSip || ready) && (
              <>
                <Divider
                  my="sm"
                  label={viaSip ? 'Записная книжка' : 'Сотрудники'}
                  labelPosition="center"
                />

                <Group gap="xs" wrap="nowrap">
                  <TextInput
                    flex={1}
                    size="xs"
                    value={search}
                    onChange={e => setSearch(e.currentTarget.value)}
                    placeholder={viaSip ? 'Поиск по номеру' : 'Поиск по имени'}
                    leftSection={<IconSearch size={14} />}
                  />
                  <Tooltip label="Обновить список">
                    <ActionIcon
                      variant="subtle"
                      size="md"
                      onClick={() =>
                        viaSip ? refetchContacts() : refetchEmployees()
                      }>
                      <IconRefresh size={16} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
                <ScrollArea.Autosize mah={180} mt="xs">
                  {/* Внутренним звонком можно достать только того, кто сейчас в
                  сети: приглашение уходит по его же веб-сокету. */}
                  {!viaSip &&
                    employeeList.map(user => {
                      const online = isUserOnline(user.id);
                      return (
                        <Group
                          key={user.id}
                          justify="space-between"
                          wrap="nowrap"
                          gap="xs"
                          py={4}
                          style={{
                            cursor: online ? 'pointer' : 'default',
                            opacity: online ? 1 : 0.5,
                          }}
                          onClick={() =>
                            online && dialUser({ id: user.id, name: user.name })
                          }>
                          <Text size="sm" lineClamp={1}>
                            {user.name}
                          </Text>
                          <Tooltip label={online ? 'В сети' : 'Не в сети'}>
                            <Box
                              w={8}
                              h={8}
                              style={{
                                borderRadius: '50%',
                                flexShrink: 0,
                                background: online
                                  ? 'var(--mantine-color-green-6)'
                                  : 'var(--mantine-color-gray-4)',
                              }}
                            />
                          </Tooltip>
                        </Group>
                      );
                    })}
                  {!viaSip && !employeeList.length && (
                    <Text size="xs" c="dimmed" ta="center" py="sm">
                      Сотрудники не найдены
                    </Text>
                  )}

                  {viaSip &&
                    contacts.map(contact => (
                      <Group
                        key={contact.id}
                        justify="space-between"
                        wrap="nowrap"
                        gap="xs"
                        py={4}
                        style={{ cursor: 'pointer' }}
                        onClick={() => dialContact(contact)}>
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
                  {viaSip && !contacts.length && (
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
