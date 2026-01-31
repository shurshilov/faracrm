import { FieldChar } from '@/components/Form/Fields/FieldChar';
import { FormRow, FormSection } from '@/components/Form/Layout';
import { useTranslation } from 'react-i18next';
import { useFormContext } from '@/components/Form/FormContext';
import { Button, Group, Badge, Text, Modal, Code, Stack } from '@mantine/core';
import {
  IconWebhook,
  IconWebhookOff,
  IconInfoCircle,
} from '@tabler/icons-react';
import {
  useSetConnectorWebhookMutation,
  useUnsetConnectorWebhookMutation,
  useLazyGetConnectorWebhookInfoQuery,
} from '@/services/api/chat';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';
import { useDisclosure } from '@mantine/hooks';

interface WebhookSectionProps {
  /** Название источника для кнопки "Информация от ..." */
  sourceName?: string;
}

/**
 * Универсальный компонент секции Webhook.
 * Используется модулями коннекторов которые поддерживают webhook.
 *
 * @example
 * // В fara_chat_telegram
 * registerExtension('chat_connector', () => <WebhookSection sourceName="Telegram" />, ...);
 */
export function WebhookSection({
  sourceName = 'сервера',
}: WebhookSectionProps) {
  const { t } = useTranslation('chat');
  const form = useFormContext();
  const [setWebhook, { isLoading: isSettingWebhook }] =
    useSetConnectorWebhookMutation();
  const [unsetWebhook, { isLoading: isUnsettingWebhook }] =
    useUnsetConnectorWebhookMutation();
  const [getWebhookInfo, { isLoading: isLoadingInfo }] =
    useLazyGetConnectorWebhookInfoQuery();

  const [webhookState, setWebhookState] = useState<string | null>(null);
  const [webhookInfo, setWebhookInfo] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [infoModalOpened, { open: openInfoModal, close: closeInfoModal }] =
    useDisclosure(false);

  const connectorId = form.values?.id;
  const currentState = webhookState ?? form.values?.webhook_state;
  const isWebhookSet = currentState === 'successful';
  const isLoading = isSettingWebhook || isUnsettingWebhook;
  const isNewRecord = !connectorId;

  const handleSetWebhook = async () => {
    if (!connectorId) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message: t(
          'connector.webhook.saveFirst',
          'Сначала сохраните коннектор',
        ),
        color: 'red',
      });
      return;
    }

    try {
      const result = await setWebhook({
        connectorId: Number(connectorId),
      }).unwrap();
      setWebhookState(result.webhook_state);
      notifications.show({
        title: t('common.success', 'Успешно'),
        message: t('connector.webhook.setSuccess', 'Webhook установлен'),
        color: 'green',
      });
    } catch (error: any) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message:
          error?.data?.detail ||
          t('connector.webhook.setError', 'Не удалось установить webhook'),
        color: 'red',
      });
    }
  };

  const handleUnsetWebhook = async () => {
    if (!connectorId) return;

    try {
      const result = await unsetWebhook({
        connectorId: Number(connectorId),
      }).unwrap();
      setWebhookState(result.webhook_state);
      notifications.show({
        title: t('common.success', 'Успешно'),
        message: t('connector.webhook.unsetSuccess', 'Webhook удалён'),
        color: 'green',
      });
    } catch (error: any) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message:
          error?.data?.detail ||
          t('connector.webhook.unsetError', 'Не удалось удалить webhook'),
        color: 'red',
      });
    }
  };

  const handleGetWebhookInfo = async () => {
    if (!connectorId) return;

    try {
      const result = await getWebhookInfo({
        connectorId: Number(connectorId),
      }).unwrap();
      setWebhookInfo(result.data);
      openInfoModal();
    } catch (error: any) {
      notifications.show({
        title: t('common.error', 'Ошибка'),
        message:
          error?.data?.detail ||
          t(
            'connector.webhook.infoError',
            'Не удалось получить информацию о webhook',
          ),
        color: 'red',
      });
    }
  };

  return (
    <>
      <FormSection
        title={t('connector.groups.webhookSettings', 'Настройки Webhook')}>
        {/* Статус и кнопки управления */}
        <Group mb="md" justify="space-between">
          <Group gap="sm">
            <Text size="sm" fw={500}>
              {t('connector.webhook.status', 'Статус')}:
            </Text>
            <Badge
              color={isWebhookSet ? 'green' : 'gray'}
              variant="filled"
              size="lg">
              {isWebhookSet
                ? t('connector.webhook.active', 'Активен')
                : t('connector.webhook.inactive', 'Не установлен')}
            </Badge>
          </Group>

          <Group gap="sm">
            {!isWebhookSet ? (
              <Button
                leftSection={<IconWebhook size={16} />}
                onClick={handleSetWebhook}
                loading={isLoading}
                disabled={isNewRecord}
                color="green">
                {t('connector.webhook.set', 'Установить Webhook')}
              </Button>
            ) : (
              <Button
                leftSection={<IconWebhookOff size={16} />}
                onClick={handleUnsetWebhook}
                loading={isLoading}
                color="red"
                variant="outline">
                {t('connector.webhook.unset', 'Удалить Webhook')}
              </Button>
            )}

            <Button
              leftSection={<IconInfoCircle size={16} />}
              onClick={handleGetWebhookInfo}
              loading={isLoadingInfo}
              disabled={isNewRecord}
              variant="light">
              {t('connector.webhook.getInfo', `Информация от ${sourceName}`)}
            </Button>
          </Group>
        </Group>

        {isNewRecord && (
          <Text size="sm" c="dimmed" mb="md">
            {t(
              'connector.webhook.saveFirst',
              'Сначала сохраните коннектор, чтобы настроить webhook',
            )}
          </Text>
        )}

        <FormRow cols={1}>
          <FieldChar
            name="connector_url"
            label={t('connector.fields.connectorUrl', 'URL коннектора')}
            readOnly={isWebhookSet}
          />
        </FormRow>

        <FormRow cols={2}>
          <FieldChar
            name="webhook_url"
            label={t('connector.fields.webhookUrl', 'Webhook URL')}
            readOnly={isWebhookSet}
          />
          <FieldChar
            name="webhook_hash"
            label={t('connector.fields.webhookHash', 'Секретный хеш')}
            readOnly={isWebhookSet}
          />
        </FormRow>
      </FormSection>

      {/* Модальное окно с информацией о webhook */}
      <Modal
        opened={infoModalOpened}
        onClose={closeInfoModal}
        title={t(
          'connector.webhook.serverInfo',
          `Информация о Webhook от ${sourceName}`,
        )}
        size="lg">
        {webhookInfo && (
          <Stack gap="md">
            <div>
              <Text size="sm" fw={500} mb={4}>
                URL:
              </Text>
              <Code block>{(webhookInfo as any).url || '—'}</Code>
            </div>

            <Group>
              <div>
                <Text size="sm" fw={500}>
                  Pending updates:
                </Text>
                <Badge color="blue" variant="light" size="lg">
                  {(webhookInfo as any).pending_update_count ?? 0}
                </Badge>
              </div>

              {(webhookInfo as any).last_error_date && (
                <div>
                  <Text size="sm" fw={500}>
                    Last error:
                  </Text>
                  <Badge color="red" variant="light" size="lg">
                    {new Date(
                      (webhookInfo as any).last_error_date * 1000,
                    ).toLocaleString()}
                  </Badge>
                </div>
              )}
            </Group>

            {(webhookInfo as any).last_error_message && (
              <div>
                <Text size="sm" fw={500} mb={4}>
                  Last error message:
                </Text>
                <Code block color="red">
                  {(webhookInfo as any).last_error_message}
                </Code>
              </div>
            )}

            <div>
              <Text size="sm" fw={500} mb={4}>
                {t('connector.webhook.fullResponse', 'Полный ответ')}:
              </Text>
              <Code block style={{ maxHeight: 300, overflow: 'auto' }}>
                {JSON.stringify(webhookInfo, null, 2)}
              </Code>
            </div>
          </Stack>
        )}
      </Modal>
    </>
  );
}

export default WebhookSection;
