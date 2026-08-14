import { useState } from 'react';
import { FieldBoolean } from '@/components/Form/Fields/FieldBoolean';
import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FieldInteger } from '@/components/Form/Fields/FieldInteger';
import { FieldSelection } from '@/components/Form/Fields/FieldSelection';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { WebhookSection } from '@/fara_chat/components/WebhookSection';
import {
  Accordion,
  Button,
  Code,
  Group,
  Select,
  Switch,
  Text,
} from '@mantine/core';
import { DateInput } from '@mantine/dates';
import {
  IconInfoCircle,
  IconHistory,
  IconPlugConnected,
  IconRefresh,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import {
  useFetchCallHistoryMutation,
  useStartListenerMutation,
  useStopListenerMutation,
  useSyncNumbersMutation,
  useTestConnectorMutation,
} from '@/services/api/chat';

// Поля коннектора Asterisk (нужны, чтобы форма их подгрузила).
// agent_mode — режим транспорта; asterisk_db_* / asterisk_ari_* — настройки
// встроенного (local) режима отдельными типизированными колонками (из БД, через UI).
const ASTERISK_FIELDS = [
  'agent_mode',
  'internal_calls_notify',
  // local: доступ к БД Asterisk (CDR)
  'asterisk_db_dialect',
  'asterisk_db_host',
  'asterisk_db_port',
  'asterisk_db_database',
  'asterisk_db_user',
  'asterisk_db_password',
  'asterisk_db_table_cdr',
  // local: ARI (события + записи)
  'asterisk_ari_url',
  'asterisk_ari_wss',
  'asterisk_ari_login',
  'asterisk_ari_password',
  'asterisk_ari_autostart',
  'asterisk_path_recordings',
  // remote: внешний Asterisk-agent
  'connector_url',
  'access_token',
  'refresh_token',
  'webhook_url',
  'webhook_state',
  'webhook_hash',
];

/**
 * Секция «Подключение» коннектора Asterisk / FreePBX.
 *
 * Режим (agent_mode):
 * - remote: внешний Asterisk-agent (REST + webhook) — поля connector_url / логин / пароль;
 * - local:  встроенный (прямой доступ к БД Asterisk и ARI) — типизированные поля БД/ARI.
 */
export function ViewFormConnectorAsterisk() {
  const { t } = useTranslation('chat');
  const form = useFormContext();
  const [testConnector, { isLoading: isTesting }] = useTestConnectorMutation();
  const [syncNumbers, { isLoading: isSyncing }] = useSyncNumbersMutation();
  const [fetchCallHistory, { isLoading: isFetchingHistory }] =
    useFetchCallHistoryMutation();
  const [startListener, { isLoading: isStarting }] = useStartListenerMutation();
  const [stopListener, { isLoading: isStopping }] = useStopListenerMutation();

  // Период импорта истории из CDR (даты в формате YYYY-MM-DD, Mantine DateInput).
  const [histFrom, setHistFrom] = useState<string | null>(null);
  const [histTo, setHistTo] = useState<string | null>(null);
  // Режим импорта: по умолчанию silent (только сообщения, без попапов и лидов).
  const [histMode, setHistMode] = useState<string>('silent');

  if (form.values?.type !== 'phone_asterisk') {
    return null;
  }

  const connectorId = form.values?.id;
  const isLocal = (form.values?.agent_mode || 'remote') === 'local';
  const autostart = !!form.values?.asterisk_ari_autostart;

  const handleTest = async () => {
    // Проверка идёт по СОХРАНЁННЫМ настройкам — сначала нужно сохранить.
    if (!connectorId) {
      notifications.show({
        title: t('common.info', 'Информация'),
        message: t(
          'connector.asterisk.saveFirst',
          'Сначала сохраните коннектор, затем проверьте соединение',
        ),
        color: 'yellow',
      });
      return;
    }

    try {
      const { data } = await testConnector({
        connectorId: Number(connectorId),
      }).unwrap();

      notifications.show({
        title: data.ok
          ? t('connector.asterisk.testOk', 'Соединение установлено')
          : t('connector.asterisk.testFail', 'Ошибка соединения'),
        message: data.message,
        color: data.ok ? 'green' : 'red',
        autoClose: data.ok ? 4000 : false,
      });
    } catch (error: any) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message:
          error?.data?.detail ||
          t('connector.asterisk.testError', 'Не удалось проверить соединение'),
        color: 'red',
      });
    }
  };

  const handleSync = async () => {
    // Синхронизация идёт по СОХРАНЁННЫМ настройкам — сначала нужно сохранить.
    if (!connectorId) {
      notifications.show({
        title: t('common.info', 'Информация'),
        message: t(
          'connector.asterisk.saveFirstSync',
          'Сначала сохраните коннектор, затем синхронизируйте номера',
        ),
        color: 'yellow',
      });
      return;
    }

    try {
      const { data } = await syncNumbers({
        connectorId: Number(connectorId),
      }).unwrap();

      notifications.show({
        title: data.ok
          ? t('connector.asterisk.syncOk', 'Номера синхронизированы')
          : t('connector.asterisk.syncFail', 'Ошибка синхронизации'),
        message: data.message,
        color: data.ok ? 'green' : 'red',
        autoClose: data.ok ? 5000 : false,
      });
    } catch (error: any) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message:
          error?.data?.detail ||
          t('connector.asterisk.syncError', 'Не удалось синхронизировать номера'),
        color: 'red',
      });
    }
  };

  const handleToggleAutostart = async (next: boolean) => {
    // Работает по СОХРАНЁННЫМ настройкам ARI — сначала сохранить.
    if (!connectorId) {
      notifications.show({
        title: t('common.info', 'Информация'),
        message: t(
          'connector.asterisk.saveFirstListener',
          'Сначала сохраните коннектор и настройки ARI, затем включайте автозапуск',
        ),
        color: 'yellow',
      });
      return;
    }

    try {
      const { data } = next
        ? await startListener({ connectorId: Number(connectorId) }).unwrap()
        : await stopListener({ connectorId: Number(connectorId) }).unwrap();

      // Отражаем ФАКТИЧЕСКОЕ состояние: при неуспешной проверке enabled=false,
      // свич останется выключенным.
      form.setValues({ asterisk_ari_autostart: data.enabled });

      notifications.show({
        title: data.ok
          ? t('connector.asterisk.listenerOk', 'Готово')
          : t('connector.asterisk.listenerFail', 'Не удалось включить'),
        message: data.message,
        color: data.ok ? 'green' : 'red',
        autoClose: data.ok ? 4000 : false,
      });
    } catch (error: any) {
      form.setValues({ asterisk_ari_autostart: false });
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message:
          error?.data?.detail ||
          t('connector.asterisk.listenerError', 'Не удалось изменить автозапуск'),
        color: 'red',
      });
    }
  };

  const handleFetchHistory = async () => {
    // Импорт идёт по СОХРАНЁННЫМ настройкам — сначала нужно сохранить.
    if (!connectorId) {
      notifications.show({
        title: t('common.info', 'Информация'),
        message: t(
          'connector.asterisk.saveFirstHistory',
          'Сначала сохраните коннектор, затем читайте историю из CDR',
        ),
        color: 'yellow',
      });
      return;
    }
    if (!histFrom || !histTo) {
      notifications.show({
        title: t('common.info', 'Информация'),
        message: t(
          'connector.asterisk.historyPeriodRequired',
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

      notifications.show({
        title: data.ok
          ? t('connector.asterisk.historyOk', 'История прочитана')
          : t('connector.asterisk.historyFail', 'Не удалось прочитать историю'),
        message: data.message,
        color: data.ok ? 'green' : 'red',
        autoClose: data.ok ? 6000 : false,
      });
    } catch (error: any) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message:
          error?.data?.detail ||
          t('connector.asterisk.historyError', 'Не удалось прочитать историю из CDR'),
        color: 'red',
      });
    }
  };

  return (
    <FormSection
      title={t('connector.groups.asterisk', 'Asterisk / FreePBX')}
      collapsible>
      <FormRow cols={1}>
        <FieldSelection
          name="agent_mode"
          label={t('connector.fields.asteriskSourceMode', 'Режим транспорта')}
        />
      </FormRow>

      <FormRow cols={1}>
        <FieldBoolean
          name="internal_calls_notify"
          label={t(
            'connector.fields.internalCallsNotify',
            'Попап и лид по внутренним звонкам',
          )}
          description={t(
            'connector.fields.internalCallsNotifyHint',
            'Внутренние звонки (сотрудник↔сотрудник) всегда попадают в историю. ' +
              'Галочка включает по ним живой попап; по умолчанию выключено.',
          )}
        />
      </FormRow>

      {isLocal ? (
        <>
          {/* Свёрнутая по умолчанию подсказка по настройке FreePBX/Asterisk. */}
          <Accordion variant="contained" radius="md" mt="sm">
            <Accordion.Item value="where">
              <Accordion.Control icon={<IconInfoCircle size={16} />}>
                {t(
                  'connector.asterisk.freepbxHintTitle',
                  'Где взять настройки (FreePBX / Asterisk)',
                )}
              </Accordion.Control>
              <Accordion.Panel>
                <Text size="xs" mb={6}>
                  {t(
                    'connector.asterisk.freepbxHintText',
                    'Выполните на сервере АТС (SSH):',
                  )}
                </Text>
                <Code block>
                  {`# ARI логин и пароль
fwconsole setting FPBX_ARI_USER
fwconsole setting FPBX_ARI_PASSWORD

# База данных (host / name / user / pass)
cat /etc/freepbx.conf | grep -E "AMPDB(HOST|NAME|USER|PASS)"

# ARI URL:  http://<PBX>:8088/ari
# ARI WSS:  ws://<PBX>:8088/ari/events`}
                </Code>
              </Accordion.Panel>
            </Accordion.Item>

            <Accordion.Item value="enable">
              <Accordion.Control icon={<IconInfoCircle size={16} />}>
                {t(
                  'connector.asterisk.freepbxEnableTitle',
                  'Как включить ARI и HTTP на FreePBX',
                )}
              </Accordion.Control>
              <Accordion.Panel>
                <Text size="xs" mb={6}>
                  {t(
                    'connector.asterisk.freepbxEnableConsole',
                    'Вариант 1 — через fwconsole (FreePBX сам включит HTTP и сгенерирует конфиги):',
                  )}
                </Text>
                <Code block>
                  {`fwconsole setting ENABLE_ARI 1
fwconsole setting ARI_ALLOWED_ORIGINS "*"
fwconsole reload
# проверить: fwconsole setting --list | grep -iE 'ari|http'

# ВАЖНО (FreePBX 17): HTTP по умолчанию слушает только 127.0.0.1 —
# с другого хоста ARI недоступен. Поставьте bind на все интерфейсы:
#   Advanced Settings → "HTTP Bind Address" → 0.0.0.0
#   (в конфиге это http.conf: bindaddr = 0.0.0.0, см. Вариант 2)`}
                </Code>
                <Text size="xs" mt={8} mb={6}>
                  {t(
                    'connector.asterisk.freepbxEnableConfig',
                    'Вариант 2 — через конфиг-файлы (raw Asterisk):',
                  )}
                </Text>
                <Code block>
                  {`# /etc/asterisk/http.conf
[general]
enabled = yes
bindaddr = 0.0.0.0
bindport = 8088

# /etc/asterisk/ari.conf
[general]
enabled = yes
pretty = yes
allowed_origins = *

[my_ari_user]
type = user
read_only = no
password = ВАШ_ПАРОЛЬ

# применить:
asterisk -rx "module reload http"
asterisk -rx "module reload res_ari"`}
                </Code>
              </Accordion.Panel>
            </Accordion.Item>

            <Accordion.Item value="db-remote">
              <Accordion.Control icon={<IconInfoCircle size={16} />}>
                {t(
                  'connector.asterisk.dbRemoteTitle',
                  'Удалённый доступ к БД Asterisk (MariaDB)',
                )}
              </Accordion.Control>
              <Accordion.Panel>
                <Text size="xs" mb={6}>
                  {t(
                    'connector.asterisk.dbRemoteText',
                    'Чтобы FARA (на другом хосте) могла читать CDR, откройте MariaDB для сети и дайте права пользователю БД с нужного IP:',
                  )}
                </Text>
                <Code block>
                  {`# 1) Слушать сеть — /etc/my.cnf.d/server.cnf
[mysqld]
bind-address = 0.0.0.0

systemctl restart mariadb

# 2) Права пользователю БД с IP FARA
mysql -u root
GRANT ALL PRIVILEGES ON *.* TO 'freepbxuser'@'IP_ФАРЫ' IDENTIFIED BY 'ПАРОЛЬ';
FLUSH PRIVILEGES;
EXIT;`}
                </Code>
                <Text size="xs" c="dimmed" mt={6}>
                  {t(
                    'connector.asterisk.dbRemoteSafer',
                    'Безопаснее вместо ALL на *.* дать только чтение нужных баз: GRANT SELECT ON asterisk.* и asteriskcdrdb.* пользователю с IP FARA.',
                  )}
                </Text>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
          <Text fw={600} size="sm" mt="sm">
            {t('connector.asterisk.dbGroup', 'База данных Asterisk (CDR)')}
          </Text>
          <FormRow cols={1}>
            <FieldSelection
              name="asterisk_db_dialect"
              label={t('connector.fields.asteriskDbDialect', 'СУБД')}
            />
          </FormRow>
          <FormRow cols={2}>
            <FieldChar
              name="asterisk_db_host"
              label={t('connector.fields.asteriskDbHost', 'Хост БД')}
              placeholder="127.0.0.1"
            />
            <FieldInteger
              name="asterisk_db_port"
              label={t('connector.fields.asteriskDbPort', 'Порт БД')}
            />
          </FormRow>
          <FormRow cols={2}>
            <FieldChar
              name="asterisk_db_database"
              label={t('connector.fields.asteriskDbName', 'База данных')}
              placeholder="asteriskcdrdb"
            />
            <FieldChar
              name="asterisk_db_table_cdr"
              label={t('connector.fields.asteriskDbTable', 'Таблица CDR')}
              placeholder="cdr"
            />
          </FormRow>
          <FormRow cols={2}>
            <FieldChar
              name="asterisk_db_user"
              label={t('connector.fields.asteriskDbUser', 'Пользователь БД')}
            />
            <FieldChar
              name="asterisk_db_password"
              label={t('connector.fields.asteriskDbPassword', 'Пароль БД')}
              type="password"
            />
          </FormRow>

          <Text fw={600} size="sm" mt="md">
            {t('connector.asterisk.ariGroup', 'ARI (события и записи)')}
          </Text>
          <FormRow cols={2}>
            <FieldChar
              name="asterisk_ari_url"
              label={t('connector.fields.asteriskAriUrl', 'ARI URL')}
              placeholder="http://pbx:8088/ari"
            />
            <FieldChar
              name="asterisk_ari_wss"
              label={t(
                'connector.fields.asteriskAriWss',
                'ARI WebSocket (WSS)',
              )}
              placeholder="ws://pbx:8088/ari/events"
            />
          </FormRow>
          <FormRow cols={2}>
            <FieldChar
              name="asterisk_ari_login"
              label={t('connector.fields.asteriskAriLogin', 'ARI логин')}
            />
            <FieldChar
              name="asterisk_ari_password"
              label={t('connector.fields.asteriskAriPassword', 'ARI пароль')}
              type="password"
            />
          </FormRow>
          <FormRow cols={1}>
            <FieldChar
              name="asterisk_path_recordings"
              label={t(
                'connector.fields.asteriskPathRecordings',
                'Каталог записей на сервере',
              )}
              placeholder="/var/spool/asterisk/monitor"
            />
          </FormRow>

          <Switch
            mt="md"
            checked={autostart}
            onChange={e => handleToggleAutostart(e.currentTarget.checked)}
            disabled={isStarting || isStopping}
            label={t(
              'connector.asterisk.autostart',
              'Автозапуск ARI-слушателя (события звонков)',
            )}
            description={t(
              'connector.asterisk.autostartDesc',
              'Включается только если ARI отвечает. FARA слушает события in-process; ' +
                'на старте бэкенда поднимается автоматически.',
            )}
          />
          <Text size="xs" c="dimmed" mt={4}>
            {t(
              'connector.asterisk.localHint',
              'Встроенный режим не требует внешнего Asterisk-agent: FARA сама ходит ' +
                'в CDR и слушает ARI. Webhook и REST-поля не используются.',
            )}
          </Text>
        </>
      ) : (
        <>
          <FormRow cols={1}>
            <FieldChar
              name="connector_url"
              label={t('connector.fields.asteriskUrl', 'URL Asterisk-agent')}
              placeholder="http://host:8082"
            />
          </FormRow>
          <FormRow cols={2}>
            <FieldChar
              name="access_token"
              label={t('connector.fields.asteriskLogin', 'Логин (Basic-auth)')}
            />
            <FieldChar
              name="refresh_token"
              label={t(
                'connector.fields.asteriskPassword',
                'Пароль (Basic-auth)',
              )}
              type="password"
            />
          </FormRow>
          <Text size="xs" c="dimmed" mt={4}>
            {t(
              'connector.asterisk.webhookHint',
              'Укажите webhook-URL (вкладка «Webhooks») как адрес отправки ARI-событий в конфиге Asterisk-agent.',
            )}
          </Text>
        </>
      )}

      {/* Импорт истории звонков из CDR за период (работает в обоих режимах). */}
      <Text fw={600} size="sm" mt="md">
        {t('connector.asterisk.historyGroup', 'История звонков (CDR)')}
      </Text>
      <Text size="xs" c="dimmed" mb={6}>
        {t(
          'connector.asterisk.historyHint',
          'Прочитать звонки из CDR за выбранный период и создать call-сообщения ' +
            '(как cron, но вручную). Повторный импорт безопасен — дубли гасятся.',
        )}
      </Text>
      <FormRow cols={2}>
        <DateInput
          value={histFrom}
          onChange={setHistFrom}
          valueFormat="DD.MM.YYYY"
          clearable
          label={t('connector.asterisk.historyFrom', 'С (дата)')}
          placeholder={t('connector.asterisk.historyPickDate', 'выберите дату')}
        />
        <DateInput
          value={histTo}
          onChange={setHistTo}
          valueFormat="DD.MM.YYYY"
          clearable
          label={t('connector.asterisk.historyTo', 'По (дата)')}
          placeholder={t('connector.asterisk.historyPickDate', 'выберите дату')}
        />
      </FormRow>
      <Group justify="space-between" mt="xs" align="flex-end">
        <Select
          w={280}
          label={t('connector.asterisk.historyMode', 'Режим импорта')}
          value={histMode}
          onChange={v => setHistMode(v || 'silent')}
          allowDeselect={false}
          data={[
            {
              value: 'silent',
              label: t(
                'connector.asterisk.historyModeSilent',
                'Без уведомлений и без лидов',
              ),
            },
            {
              value: 'no_notify',
              label: t(
                'connector.asterisk.historyModeNoNotify',
                'Без уведомлений',
              ),
            },
            {
              value: 'normal',
              label: t(
                'connector.asterisk.historyModeNormal',
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
          {t('connector.asterisk.fetchHistory', 'Прочитать историю из CDR')}
        </Button>
      </Group>

      <Group justify="flex-end" mt="sm">
        <Button
          variant="light"
          color="teal"
          leftSection={<IconRefresh size={16} />}
          onClick={handleSync}
          loading={isSyncing}>
          {t('connector.asterisk.syncNumbers', 'Синхронизировать номера')}
        </Button>
        <Button
          variant="light"
          leftSection={<IconPlugConnected size={16} />}
          onClick={handleTest}
          loading={isTesting}>
          {t('connector.asterisk.testConnection', 'Проверить соединение')}
        </Button>
      </Group>
    </FormSection>
  );
}

/** Webhook-секция Asterisk (агент шлёт сюда ARI-события; только remote-режим). */
export function ViewFormConnectorAsteriskWebhooks() {
  const form = useFormContext();

  if (form.values?.type !== 'phone_asterisk') {
    return null;
  }
  // В local-режиме внешний webhook не используется (события слушаются in-process).
  if ((form.values?.agent_mode || 'remote') === 'local') {
    return null;
  }

  return <WebhookSection sourceName="Asterisk" />;
}

/** Пустой таб «Авторизация» — Asterisk использует Basic-auth из «Подключения». */
export function ViewFormConnectorAsteriskEmptyAuth() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'phone_asterisk') {
    return null;
  }

  return (
    <FormSection>
      <p style={{ color: 'var(--mantine-color-dimmed)' }}>
        {t(
          'connector.asterisk.noAuthRequired',
          'Asterisk использует логин/пароль (Basic-auth) из вкладки «Подключение» для доступа к Asterisk-agent.',
        )}
      </p>
    </FormSection>
  );
}

// Регистрируем расширения формы коннектора (гейт по type='phone_asterisk')
registerExtension(
  'chat_connector',
  ViewFormConnectorAsterisk,
  'after:FormTab:connection',
  ASTERISK_FIELDS,
);

registerExtension(
  'chat_connector',
  ViewFormConnectorAsteriskWebhooks,
  'after:FormTab:webhooks',
  [
    'webhook_url',
    'webhook_state',
    'webhook_hash',
    'connector_url',
    'agent_mode',
  ],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorAsteriskEmptyAuth,
  'after:FormTab:auth',
);

export default ViewFormConnectorAsterisk;
