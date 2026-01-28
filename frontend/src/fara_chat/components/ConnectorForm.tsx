import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import {
  FormRow,
  FormTabs,
  FormTab,
  FormSheet,
  FormSection,
} from '@/components/Form/Layout';
import {
  IconSettings,
  IconKey,
  IconHistory,
  IconLink,
  IconWebhook,
  IconUsers,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

/**
 * Базовая форма коннектора чата.
 *
 * Содержит только общие поля для всех типов коннекторов.
 * Специфичные поля (Telegram, Email и т.д.) добавляются через расширения.
 * WebhookSection добавляется через расширение в таб webhooks.
 */
export function ConnectorForm(props: ViewFormProps) {
  const { t } = useTranslation('chat');

  return (
    <Form model="chat_connector" {...props}>
      {/* Основная информация */}
      <FormSheet>
        <FormRow cols={2}>
          <Field name="name" label={t('connector.fields.name')} />
          <Field name="active" label={t('connector.fields.active')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="type" label={t('connector.fields.type')} />
          <Field name="category" label={t('connector.fields.category')} />
        </FormRow>
      </FormSheet>

      {/* Вкладки */}
      <FormTabs defaultTab="connection">
        {/* Подключение */}
        <FormTab
          name="connection"
          label={t('connector.tabs.connection')}
          icon={<IconLink size={16} />}>
          {/* Контент добавляется через расширения */}
        </FormTab>

        {/* Операторы */}
        <FormTab
          name="operators"
          label={t('connector.tabs.operators', 'Операторы')}
          icon={<IconUsers size={16} />}>
          <Field
            name="operator_ids"
            label={t('connector.fields.operators', 'Операторы')}>
            <Field name="id" />
            <Field name="name" />
            <Field name="login" />
          </Field>
        </FormTab>

        {/* Webhooks — контент добавляется через WebhookSection расширение */}
        <FormTab
          name="webhooks"
          label={t('connector.tabs.webhooks', 'Webhooks')}
          icon={<IconWebhook size={16} />}>
          {/* Контент добавляется через расширения */}
        </FormTab>

        {/* Авторизация */}
        <FormTab
          name="auth"
          label={t('connector.tabs.auth')}
          icon={<IconKey size={16} />}>
          {/* Контент добавляется через расширения */}
        </FormTab>

        {/* Настройки */}
        <FormTab
          name="crm"
          label={t('connector.tabs.crm')}
          icon={<IconSettings size={16} />}>
          <FormSection title={t('connector.groups.leadSettings')}>
            <FormRow cols={1}>
              <Field name="lead_type" label={t('connector.fields.leadType')} />
            </FormRow>
          </FormSection>
        </FormTab>

        {/* История */}
        <FormTab
          name="logs"
          label={t('connector.tabs.logs')}
          icon={<IconHistory size={16} />}>
          <FormSection title={t('connector.groups.lastResponse')}>
            <FormRow cols={1}>
              <Field
                name="last_response"
                label={t('connector.fields.lastResponse')}
              />
            </FormRow>
          </FormSection>

          <FormSection title={t('connector.groups.timestamps')}>
            <FormRow cols={2}>
              <Field
                name="create_date"
                label={t('connector.fields.createDate')}
              />
              <Field
                name="write_date"
                label={t('connector.fields.writeDate')}
              />
              <Field name="id" />
            </FormRow>
          </FormSection>
        </FormTab>
      </FormTabs>
    </Form>
  );
}

export default ConnectorForm;
