import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconSettings } from '@tabler/icons-react';

interface SchemaSystemSettings {
  id: number;
  key: string;
  value: string;
  description: string;
}

export function ViewFormSystemSettings(props: ViewFormProps) {
  return (
    <Form<SchemaSystemSettings> model="system_settings" {...props}>
      <FormSection
        title="Системная настройка"
        icon={<IconSettings size={18} />}>
        <FormRow cols={2}>
          <Field name="key" label="Ключ" />
          <Field name="value" label="Значение" />
        </FormRow>
        <Field name="description" label="Описание" />
        <Field name="id" label="ID" />
      </FormSection>
    </Form>
  );
}

export default ViewFormSystemSettings;
