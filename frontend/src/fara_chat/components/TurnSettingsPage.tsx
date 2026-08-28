// Copyright 2025 FARA CRM
// Раздел «Релей звонков (TURN)» — всё про релей в одном месте.
//
// Живёт отдельной страницей, а не в форме коннектора: релей ОБЩИЙ для всей
// системы. Через него идут и звонки в АТС, и внутренние звонки сотрудников,
// которые к телефонии вообще не относятся. В карточке одного коннектора это
// выглядело так, будто настройка принадлежит ему.
//
// Проверка ОДНА и показывает сразу все состояния: что уезжает в браузер, что
// отвечает релей на запрос с сервера, что видит сам браузер и пустит ли релей
// трафик до АТС. Разбирать это по отдельным кнопкам было бы честнее к коду и
// бесполезнее для того, кто чинит: причина «звука нет» каждый раз оказывается
// в другом звене.

import { useState } from 'react';
import {
  Button,
  Card,
  Code,
  Group,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core';
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconCircleX,
  IconRouter,
  IconSettings,
} from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useGetIceServersQuery, useTestIceMutation } from '@/services/api/ice';
import { checkRelayLoop, gatherIceCandidates } from '../utils/iceProbe';
import {
  buildTurnChecks,
  type CheckStatus,
  type TurnCheck,
  type TurnCheckInput,
} from '../utils/turnChecks';

const STATUS_ICON = {
  ok: IconCircleCheck,
  warn: IconAlertTriangle,
  fail: IconCircleX,
} as const;

const STATUS_COLOR: Record<CheckStatus, string> = {
  ok: 'teal',
  warn: 'orange',
  fail: 'red',
};

/** Результаты проверки без того, что берётся из хуков. */
type ProbeState = Omit<TurnCheckInput, 't' | 'config'>;

/**
 * Команды длинные (STUN-проба — целая строка кода), а переносить их нельзя:
 * скопированный кусок должен вставляться в терминал целиком и работать.
 * Поэтому не перенос, а прокрутка внутри блока — страница при этом не едет
 * вбок (см. maxWidth: '100%').
 */
const SCROLLABLE = {
  overflowX: 'auto' as const,
  whiteSpace: 'pre' as const,
  maxWidth: '100%',
};

function CheckRow({ check }: { check: TurnCheck }) {
  const Icon = STATUS_ICON[check.status];
  const color = STATUS_COLOR[check.status];

  return (
    <Group align="flex-start" wrap="nowrap" gap="sm">
      <ThemeIcon size="sm" radius="xl" variant="light" color={color} mt={2}>
        <Icon size={14} />
      </ThemeIcon>
      <Stack gap={4} style={{ minWidth: 0, flex: 1 }}>
        <Text size="sm" fw={500}>
          {check.title}
        </Text>
        <Text size="xs" c="dimmed" style={{ wordBreak: 'break-word' }}>
          {check.detail}
        </Text>
        {check.fix && (
          <Text size="xs" c={color}>
            {check.fix}
          </Text>
        )}
        {check.command && <Code block style={SCROLLABLE}>{check.command}</Code>}
        {check.diagnose && (
          <Stack gap={2}>
            <Text size="xs" c="dimmed">
              посмотреть руками:
            </Text>
            <Code block style={SCROLLABLE}>
              {check.diagnose}
            </Code>
          </Stack>
        )}
      </Stack>
    </Group>
  );
}

export function TurnSettingsPage() {
  const { t } = useTranslation('chat');
  const { data: iceData, refetch } = useGetIceServersQuery();
  const [testIce] = useTestIceMutation();
  const [running, setRunning] = useState(false);
  const [probe, setProbe] = useState<ProbeState | null>(null);

  // Результаты приходят вразнобой: серверная часть за доли секунды, сквозная
  // проверка через релей — за секунды. Дописываем их по мере готовности, чтобы
  // список наполнялся на глазах, а не появлялся целиком в конце.
  const merge = (patch: ProbeState) =>
    setProbe(prev => ({ ...(prev || {}), ...patch }));

  const translate = (key: string, defaultValue: string) =>
    t(key, { defaultValue });

  const checks = probe
    ? buildTurnChecks({ t: translate, config: iceData?.data, ...probe })
    : [];

  const describeServerError = (error: unknown): string => {
    const status = (error as { status?: number | string })?.status;
    if (status === 429) {
      return t('turn.errTooOften', {
        defaultValue:
          'проверка запускалась только что — повторите через пару секунд',
      });
    }
    if (status === 403) {
      return t('turn.errAdmin', {
        defaultValue: 'проверку с сервера может запускать только администратор',
      });
    }
    return t('turn.errServer', {
      defaultValue: 'запрос не выполнился — смотрите лог бэкенда',
    });
  };

  const handleRun = async () => {
    setRunning(true);
    setProbe({});

    // Креды временные: за время открытой вкладки они протухают, и проверка на
    // старых показала бы «релей отверг креды» на исправном релее.
    let servers: RTCIceServer[] = iceData?.data?.ice_servers || [];
    try {
      const fresh = await refetch().unwrap();
      servers = fresh.data.ice_servers || [];
    } catch {
      // Не беда: проверим тем, что уже есть, а строка «конфигурация» это
      // покажет.
    }

    await Promise.all([
      testIce()
        .unwrap()
        .then(response => merge({ server: response.data }))
        .catch(error => merge({ serverError: describeServerError(error) })),

      (async () => {
        const gather = await gatherIceCandidates(servers);
        merge({ browser: gather });
        // Сквозную проверку запускаем только когда есть чем: без relay-
        // кандидата она гарантированно упрётся в таймаут и скажет то же самое
        // второй раз.
        if (gather.relay.length) {
          merge({ loop: await checkRelayLoop(servers) });
        }
      })().catch(error =>
        merge({
          browserError:
            error instanceof Error ? error.message : String(error),
        }),
      ),
    ]);

    setRunning(false);
  };

  return (
    <Stack p="md" gap="md" maw={900} mx="auto" w="100%">
      <Group gap="xs">
        <IconRouter size={22} />
        <Title order={3}>{t('turn.title', 'Релей звонков (TURN)')}</Title>
      </Group>

      <Text size="sm" c="dimmed">
        {t(
          'turn.intro',
          'Релей нужен там, где браузеры не могут соединиться напрямую: ' +
            'симметричный NAT у мобильных операторов, закрытый наружу UDP в ' +
            'офисе, VPN. Он общий и для внутренних звонков сотрудников, и для ' +
            'звонилки в АТС.',
        )}
      </Text>

      {/* ── Проверка ──────────────────────────────────────────── */}
      <Card withBorder padding="md">
        <Group justify="space-between" mb="xs">
          <Text fw={600}>{t('turn.check', 'Проверка')}</Text>
          <Button
            variant="light"
            color="indigo"
            leftSection={<IconRouter size={16} />}
            onClick={handleRun}
            loading={running}>
            {t('turn.checkButton', 'Проверить релей')}
          </Button>
        </Group>

        <Text size="xs" c="dimmed">
          {t(
            'turn.checkHint',
            'Одна проверка отвечает сразу на всё: выдаётся ли релей браузеру, ' +
              'отвечает ли он с сервера, принят ли секрет, публичный ли адрес ' +
              'он раздаёт, доступен ли по UDP, поднимается ли через него ' +
              'соединение из ЭТОГО браузера и пустит ли он трафик до АТС. ' +
              'Занимает несколько секунд, микрофон не спрашивает. К каждому ' +
              'пункту приложена команда, которой его можно посмотреть руками.',
          )}
        </Text>

        {checks.length > 0 && (
          <Stack gap="md" mt="md">
            {checks.map(check => (
              <CheckRow key={check.id} check={check} />
            ))}
          </Stack>
        )}
      </Card>

      {/* ── Параметры ─────────────────────────────────────────── */}
      <Card withBorder padding="md">
        <Text fw={600} mb="xs">
          {t('turn.params', 'Параметры')}
        </Text>
        <Text size="sm" c="dimmed" mb="xs">
          {t(
            'turn.paramsHint',
            'Адрес, порт, срок жизни пропусков и режим «всё через релей» ' +
              'меняются в системных настройках по ключам turn.* — применяются ' +
              'со следующего звонка, без перезапуска. Пустое значение означает ' +
              '«брать из .env». Секрет через интерфейс не меняется: он общий с ' +
              'сервером релея, который читает его при старте.',
          )}
        </Text>
        <Group>
          <Button
            component={Link}
            to="/system_settings"
            variant="light"
            leftSection={<IconSettings size={16} />}>
            {t('turn.openSettings', 'Открыть системные настройки')}
          </Button>
        </Group>
      </Card>
    </Stack>
  );
}

export default TurnSettingsPage;
