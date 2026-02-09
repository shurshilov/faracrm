import type { LanguageRecord as SchemaLanguage } from '@/types/records';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconLanguage } from '@tabler/icons-react';

export function ViewFormLanguage(props: ViewFormProps) {
  return (
    <Form<SchemaLanguage> model="language" {...props}>
      <FormSection title="Язык" icon={<IconLanguage size={18} />}>
        <FormRow cols={2}>
          <Field name="code" label="Код" />
          <Field name="name" label="Название" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="flag" label="Флаг" />
          <Field name="active" label="Активен" />
        </FormRow>
        <Field name="id" label="ID" />
      </FormSection>
    </Form>
  );
}

export default ViewFormLanguage;
