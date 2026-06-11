import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { WebhookSection } from '@/fara_chat/components/WebhookSection';
import { Button, Group, Modal, Text, Code } from '@mantine/core';
import { IconUserSearch } from '@tabler/icons-react';
import { useDisclosure } from '@mantine/hooks';
import { useState } from 'react';
import { notifications } from '@mantine/notifications';
import { useLazyGetConnectorSelfAccountQuery } from '@/services/api/chat';

/**
 * Расширение формы коннектора для MAX (МАКС).
 *
 * Добавляется в таб "connection" — основные поля интеграции
 * (access_token, external_account_id, connector_url) видны только при
 * выборе типа коннектора "max".
 *
 * Токен бота MAX не содержит id бота, поэтому external_account_id
 * (user_id бота) заполняется кнопкой "Получить данные бота" — она дёргает
 * метод GET /me стратегии через общий endpoint account/self.
 */
export function ViewFormConnectorMaxBot() {
  const { t } = useTranslation('chat');
  const form = useFormContext();
  const [getSelfAccount, { isFetching }] =
    useLazyGetConnectorSelfAccountQuery();
  const [accountText, setAccountText] = useState<string>('');
  const [opened, { open, close }] = useDisclosure(false);

  if (form.values?.type !== 'max_bot') {
    return null;
  }

  const connectorId = form.values?.id;
  const isNewRecord = !connectorId;

  const handleFetchAccount = async () => {
    if (!connectorId) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message: t(
          'connector.account.saveFirst',
          'Сначала сохраните коннектор',
        ),
        color: 'red',
      });
      return;
    }

    try {
      const result = await getSelfAccount({
        connectorId: Number(connectorId),
      }).unwrap();
      const text =
        typeof result === 'string' ? result : JSON.stringify(result, null, 2);
      setAccountText(text);
      open();
    } catch (error: any) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message:
          error?.data?.detail ||
          t(
            'connector.account.fetchError',
            'Не удалось получить данные аккаунта',
          ),
        color: 'red',
      });
    }
  };

  return (
    <>
      <FormSection title={t('connector.groups.maxBot', 'MAX Bot')} collapsible>
        <FormRow cols={1}>
          <FieldChar
            name="access_token"
            label={t('connector.fields.maxBotToken', 'Bot Token')}
            placeholder="O7sH...XaTkQ"
          />
        </FormRow>
        <FormRow cols={2}>
          <FieldChar
            name="external_account_id"
            label={t('connector.fields.maxBotId', 'Bot ID (user_id)')}
            placeholder="1234567890"
          />
          <FieldChar
            name="connector_url"
            label={t('connector.fields.connectorUrl', 'API URL')}
            placeholder="https://botapi.max.ru"
          />
        </FormRow>
        <Group justify="flex-end" mt="xs">
          <Button
            leftSection={<IconUserSearch size={16} />}
            onClick={handleFetchAccount}
            loading={isFetching}
            disabled={isNewRecord}
            variant="light">
            {t('connector.account.fetchSelfMax', 'Получить данные бота MAX')}
          </Button>
        </Group>
        {isNewRecord && (
          <Text size="xs" c="dimmed" mt={4} ta="right">
            {t(
              'connector.account.saveFirstHint',
              'Сначала сохраните коннектор, чтобы сделать запрос',
            )}
          </Text>
        )}
      </FormSection>

      <Modal
        opened={opened}
        onClose={close}
        title={t('connector.account.modalTitleMax', 'Информация о боте MAX')}
        size="lg">
        <Code
          block
          style={{
            maxHeight: 500,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
          {accountText}
        </Code>
      </Modal>
    </>
  );
}

/**
 * Webhook секция для MAX.
 * Использует общий компонент WebhookSection (как у Telegram/Avito).
 */
export function ViewFormConnectorMaxBotWebhooks() {
  const form = useFormContext();

  if (form.values?.type !== 'max_bot') {
    return null;
  }

  return <WebhookSection sourceName="MAX" />;
}

/**
 * Пустой компонент для замены таба auth у MAX.
 * MAX использует статический Bot Token — отдельная авторизация не нужна.
 */
export function ViewFormConnectorMaxBotEmptyAuth() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'max_bot') {
    return null;
  }

  return (
    <FormSection>
      <p style={{ color: 'var(--mantine-color-dimmed)' }}>
        {t(
          'connector.maxBot.noAuthRequired',
          'MAX использует Bot Token для авторизации. Настройте его во вкладке "Подключение".',
        )}
      </p>
    </FormSection>
  );
}

// Регистрируем расширения
registerExtension(
  'chat_connector',
  ViewFormConnectorMaxBot,
  'after:FormTab:connection',
  ['access_token', 'external_account_id', 'connector_url'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorMaxBotWebhooks,
  'after:FormTab:webhooks',
  ['webhook_url', 'webhook_state', 'webhook_hash', 'connector_url'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorMaxBotEmptyAuth,
  'after:FormTab:auth',
);

export default ViewFormConnectorMaxBot;
