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
 * Расширение формы коннектора для Avito.
 *
 * Добавляется в таб "connection" — основные поля интеграции
 * (client_app_id, client_secret, external_account_id) видны
 * только при выборе типа коннектора "avito".
 *
 * По аналогии с Telegram, чтобы UI не отличался между провайдерами.
 */
export function ViewFormConnectorAvito() {
  const { t } = useTranslation('chat');
  const form = useFormContext();
  const [getSelfAccount, { isFetching }] =
    useLazyGetConnectorSelfAccountQuery();
  const [accountText, setAccountText] = useState<string>('');
  const [opened, { open, close }] = useDisclosure(false);

  if (form.values?.type !== 'avito') {
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
        title={t('connector.groups.avito', 'Avito Messenger')}
        collapsible>
        <FormRow cols={2}>
          <FieldChar
            name="client_app_id"
            label={t('connector.fields.avitoClientId', 'Client ID')}
            placeholder="123456..."
          />
          <FieldChar
            name="client_secret"
            label={t('connector.fields.avitoClientSecret', 'Client Secret')}
            placeholder="abcdef..."
          />
        </FormRow>
        <FormRow cols={2}>
          <FieldChar
            name="external_account_id"
            label={t('connector.fields.avitoAccountId', 'Account Exteranl ID')}
            placeholder="44540672"
          />
          <FieldChar
            name="connector_url"
            label={t('connector.fields.connectorUrl', 'API URL')}
            placeholder="https://api.avito.ru/messenger/"
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
              'connector.account.fetchSelf',
              'Получить данные аккаунта Avito',
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
          'connector.account.modalTitle',
          'Информация об аккаунте Avito',
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
 * Расширение для таба "auth" — кнопки/поля авторизации Avito.
 * Avito использует client_credentials flow; токен генерируется
 * автоматически бэкендом, в UI показываем текущий токен и срок.
 */
export function ViewFormConnectorAvitoAuth() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'avito') {
    return null;
  }

  return (
    <FormSection
      title={t('connector.groups.avitoAuth', 'Avito Authorization')}
      collapsible>
      <FormRow cols={1}>
        <FieldChar
          name="access_token"
          label={t('connector.fields.accessToken', 'Access Token')}
          readOnly
        />
        <FieldChar
          name="access_token_type"
          label={t('connector.fields.accessTokenType', 'Token Type')}
          readOnly
        />
        <FieldChar
          name="access_token_expired"
          label={t('connector.fields.accessTokenExpired', 'Token Expires')}
          readOnly
        />
      </FormRow>
    </FormSection>
  );
}

/**
 * Webhook секция для Avito.
 * Использует общий компонент WebhookSection (как у Telegram).
 */
export function ViewFormConnectorAvitoWebhooks() {
  const form = useFormContext();

  if (form.values?.type !== 'avito') {
    return null;
  }

  return <WebhookSection sourceName="Avito" />;
}

// Регистрируем расширения
registerExtension(
  'chat_connector',
  ViewFormConnectorAvito,
  'after:FormTab:connection',
  ['client_app_id', 'client_secret', 'external_account_id', 'connector_url'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorAvitoAuth,
  'after:FormTab:auth',
  ['access_token', 'access_token_type', 'access_token_expired'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorAvitoWebhooks,
  'after:FormTab:webhooks',
  ['webhook_url', 'webhook_state', 'webhook_hash', 'connector_url'],
);

export default ViewFormConnectorAvito;
