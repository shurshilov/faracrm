import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import { WebhookSection } from '@/fara_chat/components/WebhookSection';

/**
 * Расширение формы коннектора для Telegram.
 * Добавляется в таб "connection".
 */
export function ViewFormConnectorTelegram() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'telegram') {
    return null;
  }

  return (
    <FormSection
      title={t('connector.groups.telegram', 'Telegram Bot')}
      collapsible>
      <FormRow cols={1}>
        <FieldChar
          name="access_token"
          label={t('connector.fields.telegramBotToken', 'Bot Token')}
          placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v..."
        />
        <FieldChar
          name="external_account_id"
          label={t('connector.fields.telegramBotId')}
        />
      </FormRow>
    </FormSection>
  );
}

/**
 * Webhook секция для Telegram.
 * Использует общий компонент WebhookSection.
 */
export function ViewFormConnectorTelegramWebhooks() {
  const form = useFormContext();

  if (form.values?.type !== 'telegram') {
    return null;
  }

  return <WebhookSection sourceName="Telegram" />;
}

/**
 * Пустой компонент для замены таба auth у Telegram.
 */
export function ViewFormConnectorTelegramEmptyAuth() {
  const { t } = useTranslation('chat');
  const form = useFormContext();

  if (form.values?.type !== 'telegram') {
    return null;
  }

  return (
    <FormSection>
      <p style={{ color: 'var(--mantine-color-dimmed)' }}>
        {t(
          'connector.telegram.noAuthRequired',
          'Telegram использует Bot Token для авторизации. Настройте его во вкладке "Подключение".',
        )}
      </p>
    </FormSection>
  );
}

// Регистрируем расширения
registerExtension(
  'chat_connector',
  ViewFormConnectorTelegram,
  'after:FormTab:connection',
  ['access_token', 'external_account_id'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorTelegramWebhooks,
  'after:FormTab:webhooks',
  ['webhook_url', 'webhook_state', 'webhook_hash', 'connector_url'],
);

registerExtension(
  'chat_connector',
  ViewFormConnectorTelegramEmptyAuth,
  'after:FormTab:auth',
);

export default ViewFormConnectorTelegram;
