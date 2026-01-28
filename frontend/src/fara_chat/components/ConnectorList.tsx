import { List } from '@/components/List/List';
import { Field } from '@/components/List/Field';
import { Badge } from '@mantine/core';
import { useTranslation } from 'react-i18next';

// Компонент для отображения статуса webhook
function WebhookStateBadge({ value }: { value: string }) {
  const colorMap: Record<string, string> = {
    none: 'gray',
    successful: 'green',
    failed: 'red',
  };

  return (
    <Badge color={colorMap[value] || 'gray'} variant="light" size="sm">
      {value}
    </Badge>
  );
}

// Компонент для отображения типа коннектора
function ConnectorTypeBadge({ value }: { value: string }) {
  const colorMap: Record<string, string> = {
    internal: 'blue',
    telegram: 'cyan',
    whatsapp: 'green',
    avito: 'orange',
    vk: 'indigo',
  };

  return (
    <Badge color={colorMap[value] || 'gray'} variant="filled" size="sm">
      {value}
    </Badge>
  );
}

export function ConnectorList() {
  const { t } = useTranslation('chat');

  return (
    <List
      model="chat_connector"
      defaultFields={['name', 'type', 'category', 'active', 'webhook_state']}>
      <Field name="id" label="ID" />
      <Field name="name" label={t('connector.fields.name')} />
      <Field
        name="type"
        label={t('connector.fields.type')}
        render={value => <ConnectorTypeBadge value={value} />}
      />
      <Field name="category" label={t('connector.fields.category')} />
      <Field name="active" label={t('connector.fields.active')} />
      <Field
        name="webhook_state"
        label={t('connector.fields.webhookState')}
        render={value => <WebhookStateBadge value={value} />}
      />
      {/* <Field name="webhook_url" label={t('connector.fields.webhookUrl')} /> */}
      <Field name="connector_url" label={t('connector.fields.connectorUrl')} />
      <Field name="create_date" label={t('connector.fields.createDate')} />
    </List>
  );
}

export default ConnectorList;
