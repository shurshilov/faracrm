import { useState } from 'react';
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
} from '@tabler/icons-react';
import {
  useFetchCallHistoryMutation,
  useSyncNumbersMutation,
  useTestConnectorMutation,
} from '@/services/api/chat';

/**
 * Общий блок действий телефонного коннектора (одинаков у всех провайдеров —
 * Asterisk, Sipuni, MegaFon):
 *
 * - «Проверить соединение» — пинг API провайдера (список номеров);
 * - «Синхронизировать номера» — линии провайдера → модель phone_number. Без них
 *   не считаются направление звонка, наша линия и оператор, поэтому это
 *   обязательный шаг настройки;
 * - «Прочитать историю» — импорт звонков за период (как cron, но вручную).
 * Релей (TURN) сюда НЕ входит: он общий на всю систему — через него идут и
 * внутренние звонки сотрудников, к телефонии отношения не имеющие. Живёт
 * отдельным разделом «Настройки → Релей звонков»; в карточке одного
 * коннектора выглядел бы его собственной настройкой, чем не является.
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
  // Проверка релея — админская: она ходит в сеть и занимает ресурс на сервере
  // релея, а чинить всё равно админу. Бэкенд это же проверяет сам (403).

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
