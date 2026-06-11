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
 * Расширение формы коннектора для ОФИЦИАЛЬНОЙ бизнес-интеграции MAX.
 *
 * Тип коннектора `max_business` — официальный канал «MAX для бизнеса»
 * (platform-api.max.ru): пишет клиенту первым по номеру телефона. Поля
 * видны только при выборе типа коннектора "max_business".
 */
export function ViewFormConnectorMaxBusiness() {
  const { t } = useTranslation('chat');
  const form = useFormContext();
  const [getSelfAccount, { isFetching }] =
    useLazyGetConnectorSelfAccountQuery();
  const [accountText, setAccountText] = useState<string>('');
  const [opened, { open, close }] = useDisclosure(false);

  if (form.values?.type !== 'max_business') {
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
      <FormSection
        title={t('connector.groups.maxBusiness', 'MAX для бизнеса (официальный)')}
        collapsible>
        <Text size="xs" c="dimmed" mb="xs">
          {t(
            'connector.maxBusiness.hint',
            'Официальный канал «MAX для бизнеса»: можно писать клиенту первым по номеру телефона. Нужен верифицированный бизнес-аккаунт (business.max.ru, верификация через Госуслуги/банк).',
          )}
        </Text>
        <FormRow cols={1}>
          <FieldChar
            name="access_token"
            label={t('connector.fields.maxBusinessToken', 'MAX Business Token')}
            placeholder="токен бизнес-аккаунта"
          />
        </FormRow>
        <FormRow cols={2}>
          <FieldChar
            name="external_account_id"
            label={t('connector.fields.maxBusinessId', 'Account ID')}
            placeholder="1234567890"
          />
          <FieldChar
            name="connector_url"
            label={t('connector.fields.connectorUrl', 'API URL')}
            placeholder="https://platform-api.max.ru"
          />
        </FormRow>
        <Group justify="flex-end" mt="xs">
          <Button
            leftSection={<IconUserSearch size={16} />}
            onClick={handleFetchAccount}
            loading={isFetching}
            disabled={isNewRecord}
            variant="light">
            {t(
              'connector.account.fetchSelfMaxBusiness',
              'Получить данные бизнес-аккаунта',
            )}
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
        title={t(
          'connector.account.modalTitleMaxBusiness',
          'Информация о бизнес-аккаунте MAX',
        )}
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
 * Webhook секция для MAX Business (официальный /subscriptions).
 * Кнопка «Установить» реально дёргает POST /subscriptions на бэке.
 */
export function ViewFormConnectorMaxBusinessWebhooks() {
  const form = useFormContext();

  if (form.values?.type !== 'max_business') {
    return null;
  }

  return <WebhookSection sourceName="MAX Business" />;
}

/**
 * Пустой компонент для замены таба auth у MAX Business.
 */
export function ViewFormConnectorMaxBusinessEmptyAuth() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'max_business') {
    return null;
  }

  return (
    <FormSection>
      <p style={{ color: 'var(--mantine-color-dimmed)' }}>
        {t(
          'connector.maxBusiness.noAuthRequired',
          'MAX Business использует токен бизнес-аккаунта. Настройте его во вкладке "Подключение".',
        )}
      </p>
    </FormSection>
  );
}

// Регистрируем расширения
registerExtension(
  'chat_connector',
  ViewFormConnectorMaxBusiness,
  'after:FormTab:connection',
  ['access_token', 'external_account_id', 'connector_url'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorMaxBusinessWebhooks,
  'after:FormTab:webhooks',
  ['webhook_url', 'webhook_state', 'webhook_hash', 'connector_url'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorMaxBusinessEmptyAuth,
  'after:FormTab:auth',
);

export default ViewFormConnectorMaxBusiness;
