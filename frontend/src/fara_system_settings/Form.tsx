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
        <FormRow cols={2}>
          <Field name="key" />
          <Field name="module" />
        </FormRow>
        <Field name="value" />
        <Field name="description" />
        <Field name="is_system" />
      </FormSection>
    </Form>
  );
}
