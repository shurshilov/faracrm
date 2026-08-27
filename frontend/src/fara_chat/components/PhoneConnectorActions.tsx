import { useState } from 'react';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { FormRow } from '@/components/Form/Layout';
import { Button, Group, Select, Text } from '@mantine/core';
import { DateInput } from '@mantine/dates';
import { notifications } from '@mantine/notifications';
import {
  IconHistory,
  IconPlugConnected,
  IconRefresh,
  IconRouter,
} from '@tabler/icons-react';
import {
  useFetchCallHistoryMutation,
  useSyncNumbersMutation,
  useTestConnectorMutation,
} from '@/services/api/chat';
import {
  useGetIceServersQuery,
  useTestIceMutation,
} from '@/services/api/ice';

/**
 * Общий блок действий телефонного коннектора (одинаков у всех провайдеров —
 * Asterisk, Sipuni, MegaFon):
 *
 * - «Проверить соединение» — пинг API провайдера (список номеров);
 * - «Синхронизировать номера» — линии провайдера → модель phone_number. Без них
 *   не считаются направление звонка, наша линия и оператор, поэтому это
 *   обязательный шаг настройки;
 * - «Прочитать историю» — импорт звонков за период (как cron, но вручную).
 * - «Проверить релей» — жив ли TURN. Он общий на всю систему (и на внутренние
 *   звонки тоже), настраивается в .env, но проверять его ходят сюда: это
 *   единственный экран, где вообще занимаются звонками.
 *
 * Все действия работают по СОХРАНЁННЫМ настройкам коннектора.
 */
export function PhoneConnectorActions() {
  const { t } = useTranslation('chat');
  const form = useFormContext();
  const [testConnector, { isLoading: isTesting }] = useTestConnectorMutation();
  const [syncNumbers, { isLoading: isSyncing }] = useSyncNumbersMutation();
  const [fetchCallHistory, { isLoading: isFetchingHistory }] =
    useFetchCallHistoryMutation();
  const { data: iceData } = useGetIceServersQuery();
  const [testIce, { isLoading: isTestingIce }] = useTestIceMutation();
  // Проверка релея — админская: она ходит в сеть и занимает ресурс на сервере
  // релея, а чинить всё равно админу. Бэкенд это же проверяет сам (403).
  const isAdmin = !!useSelector((s: any) => s.auth?.session)?.user_id?.is_admin;

  // Период импорта истории (даты в формате YYYY-MM-DD, Mantine DateInput).
  const [histFrom, setHistFrom] = useState<string | null>(null);
  const [histTo, setHistTo] = useState<string | null>(null);
  // Режим импорта: по умолчанию silent (только звонки, без попапов и лидов).
  const [histMode, setHistMode] = useState<string>('silent');

  const connectorId = form.values?.id;

  const requireSaved = (message: string) => {
    if (connectorId) {
      return true;
    }
    notifications.show({
      title: t('common.info', 'Информация'),
      message,
      color: 'yellow',
    });
    return false;
  };

  const showResult = (
    data: { ok: boolean; message: string },
    okTitle: string,
    failTitle: string,
  ) =>
    notifications.show({
      title: data.ok ? okTitle : failTitle,
      message: data.message,
      color: data.ok ? 'green' : 'red',
      autoClose: data.ok ? 5000 : false,
    });

  const showError = (error: any, fallback: string) =>
    notifications.show({
      title: t('common.error', 'Ошибка'),
      message: error?.data?.detail || fallback,
      color: 'red',
    });

  const handleTest = async () => {
    if (
      !requireSaved(
        t(
          'connector.phone.saveFirst',
          'Сначала сохраните коннектор, затем проверьте соединение',
        ),
      )
    ) {
      return;
    }
    try {
      const { data } = await testConnector({
        connectorId: Number(connectorId),
      }).unwrap();
      showResult(
        data,
        t('connector.phone.testOk', 'Соединение установлено'),
        t('connector.phone.testFail', 'Ошибка соединения'),
      );
    } catch (error: any) {
      showError(
        error,
        t('connector.phone.testError', 'Не удалось проверить соединение'),
      );
    }
  };

  const handleSync = async () => {
    if (
      !requireSaved(
        t(
          'connector.phone.saveFirstSync',
          'Сначала сохраните коннектор, затем синхронизируйте номера',
        ),
      )
    ) {
      return;
    }
    try {
      const { data } = await syncNumbers({
        connectorId: Number(connectorId),
      }).unwrap();
      showResult(
        data,
        t('connector.phone.syncOk', 'Номера синхронизированы'),
        t('connector.phone.syncFail', 'Ошибка синхронизации'),
      );
    } catch (error: any) {
      showError(
        error,
        t('connector.phone.syncError', 'Не удалось синхронизировать номера'),
      );
    }
  };

  const handleFetchHistory = async () => {
    if (
      !requireSaved(
        t(
          'connector.phone.saveFirstHistory',
          'Сначала сохраните коннектор, затем читайте историю звонков',
        ),
      )
    ) {
      return;
    }
    if (!histFrom || !histTo) {
      notifications.show({
        title: t('common.info', 'Информация'),
        message: t(
          'connector.phone.historyPeriodRequired',
          'Укажите период: дату «с» и «по»',
        ),
        color: 'yellow',
      });
      return;
    }

    try {
      // AwareDatetime на бэке требует зону: локальную дату → tz-aware ISO (Z).
      const { data } = await fetchCallHistory({
        connectorId: Number(connectorId),
        start: new Date(`${histFrom}T00:00:00`).toISOString(),
        end: new Date(`${histTo}T23:59:59`).toISOString(),
        mode: histMode as 'normal' | 'no_notify' | 'silent',
      }).unwrap();
      showResult(
        data,
        t('connector.phone.historyOk', 'История прочитана'),
        t('connector.phone.historyFail', 'Не удалось прочитать историю'),
      );
    } catch (error: any) {
      showError(
        error,
        t('connector.phone.historyError', 'Не удалось прочитать историю'),
      );
    }
  };

  // Релей настроен, если бэкенд отдал хоть один turn:/turns: адрес.
  const hasTurn = (iceData?.data?.ice_servers || []).some(server =>
    server.urls.some(url => url.startsWith('turn')),
  );

  const handleTestIce = async () => {
    try {
      const { data } = await testIce().unwrap();
      showResult(
        {
          ok: data.ok,
          message: data.ok
            ? t('connector.phone.turnTestOkMsg', {
                defaultValue:
                  'Релей выдал адрес {{relayed}} (наш внешний адрес {{mapped}}). ' +
                  'Звонки через него пойдут.',
                relayed: data.relayed_address,
                mapped: data.mapped_address || '—',
              })
            : data.error,
        },
        t('connector.phone.turnTestOk', 'Релей работает'),
        t('connector.phone.turnTestFail', 'Релей недоступен'),
      );
    } catch (error: any) {
      showError(
        error,
        t('connector.phone.turnTestError', 'Не удалось проверить релей'),
      );
    }
  };

  return (
    <>
      <Text fw={600} size="sm" mt="md">
        {t('connector.phone.historyGroup', 'История звонков')}
      </Text>
      <Text size="xs" c="dimmed" mb={6}>
        {t(
          'connector.phone.historyHint',
          'Прочитать звонки у провайдера за выбранный период и записать в реестр ' +
            'звонков (как cron, но вручную). Повторный импорт безопасен — дубли гасятся.',
        )}
      </Text>
      <FormRow cols={2}>
        <DateInput
          value={histFrom}
          onChange={setHistFrom}
          valueFormat="DD.MM.YYYY"
          clearable
          label={t('connector.phone.historyFrom', 'С (дата)')}
          placeholder={t('connector.phone.historyPickDate', 'выберите дату')}
        />
        <DateInput
          value={histTo}
          onChange={setHistTo}
          valueFormat="DD.MM.YYYY"
          clearable
          label={t('connector.phone.historyTo', 'По (дата)')}
          placeholder={t('connector.phone.historyPickDate', 'выберите дату')}
        />
      </FormRow>
      <Group justify="space-between" mt="xs" align="flex-end">
        <Select
          w={280}
          label={t('connector.phone.historyMode', 'Режим импорта')}
          value={histMode}
          onChange={v => setHistMode(v || 'silent')}
          allowDeselect={false}
          data={[
            {
              value: 'silent',
              label: t(
                'connector.phone.historyModeSilent',
                'Без уведомлений и без лидов',
              ),
            },
            {
              value: 'no_notify',
              label: t('connector.phone.historyModeNoNotify', 'Без уведомлений'),
            },
            {
              value: 'normal',
              label: t(
                'connector.phone.historyModeNormal',
                'Обычный (попап + лид)',
              ),
            },
          ]}
        />
        <Button
          variant="light"
          color="grape"
          leftSection={<IconHistory size={16} />}
          onClick={handleFetchHistory}
          loading={isFetchingHistory}>
          {t('connector.phone.fetchHistory', 'Прочитать историю')}
        </Button>
      </Group>

      {isAdmin && (
        <>
          <Text fw={600} size="sm" mt="md">
            {t('connector.phone.turnGroup', 'Релей для звонков (TURN)')}
          </Text>
          <Text size="xs" c="dimmed" mb={6}>
            {hasTurn
              ? t(
                  'connector.phone.turnHintOn',
                  'Релей включён и общий для всех звонков — и для звонилки, и ' +
                    'для внутренних звонков сотрудников. Проверка делает ' +
                    'настоящую аллокацию теми же кредами, что получает браузер: ' +
                    'запрос идёт с сервера CRM, путь конкретного клиента она не ' +
                    'проверяет.',
                )
              : t(
                  'connector.phone.turnHintOff',
                  'Релей не отвечает или выключен: звонки идут напрямую и не ' +
                    'соединятся там, где закрыт UDP или строгий NAT. Обычно ' +
                    'релей поднят вместе с CRM — проверьте контейнер turn, ' +
                    'открытые порты 3478 и 49160-49660/udp и ключи turn.* в ' +
                    '«Системных настройках».',
                )}
          </Text>
          <Group justify="flex-end">
            <Button
              variant="light"
              color="indigo"
              disabled={!hasTurn}
              leftSection={<IconRouter size={16} />}
              onClick={handleTestIce}
              loading={isTestingIce}>
              {t('connector.phone.turnTest', 'Проверить релей')}
            </Button>
          </Group>
        </>
      )}

      <Group justify="flex-end" mt="sm">
        <Button
          variant="light"
          color="teal"
          leftSection={<IconRefresh size={16} />}
          onClick={handleSync}
          loading={isSyncing}>
          {t('connector.phone.syncNumbers', 'Синхронизировать номера')}
        </Button>
        <Button
          variant="light"
          leftSection={<IconPlugConnected size={16} />}
          onClick={handleTest}
          loading={isTesting}>
          {t('connector.phone.testConnection', 'Проверить соединение')}
        </Button>
      </Group>
    </>
  );
}

export default PhoneConnectorActions;
