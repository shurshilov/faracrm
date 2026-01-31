import { Alert, Code, Text } from '@mantine/core';
import { IconInfoCircle, IconSettings } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FormRow, FormSection } from '@/components/Form/Layout';

interface SystemSettingsRecord {
  id: number;
  key: string;
  value: any;
  description: string;
  module: string;
  is_system: boolean;
}

export function ViewFormSystemSettings(props: ViewFormProps) {
  const { t } = useTranslation('system_settings');

  return (
    <Form<SystemSettingsRecord> model="system_settings" {...props}>
      <FormSection title={t('sections.main')}>
        <Alert
          icon={<IconInfoCircle size={16} />}
          color="blue"
          mb="md"
          variant="light">
          <Text size="sm">{t('alerts.key_format')}</Text>
          <Text size="xs" c="dimmed" mt="xs">
            {t('alerts.key_examples')} <Code>mail.smtp_host</Code>,{' '}
            <Code>auth.session_timeout</Code>,{' '}
            <Code>attachments.max_file_size</Code>
          </Text>
        </Alert>
        <FormRow cols={2}>
          <Field name="key" label={t('fields.key')} />
          <Field name="module" label={t('fields.module')} />
        </FormRow>
        <Field name="value" label={t('fields.value')} allowFileUpload />
        <Field name="description" label={t('fields.description')} />
        <Field name="is_system" label={t('fields.is_system')} />
      </FormSection>
    </Form>
  );
}
