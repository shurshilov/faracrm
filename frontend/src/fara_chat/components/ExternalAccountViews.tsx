import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { ViewFormProps } from '@/route/type';
import { FaraRecord } from '@/services/api/crudTypes';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconUser, IconLink, IconSettings } from '@tabler/icons-react';

// === List ===
export function ViewListExternalAccount() {
  return (
    <List<FaraRecord> model="chat_external_account" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
      <Field name="external_id" />
      <Field name="connector_id" />
      <Field name="contact_id" />
      <Field name="active" />
      <Field name="sequence" />
      <Field name="create_date" />
    </List>
  );
}

// === Form ===
export function ViewFormExternalAccount(props: ViewFormProps) {
  return (
    <Form<FaraRecord> model="chat_external_account" {...props}>
      <FormSection title="Основная информация" icon={<IconUser size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label="Имя" />
          <Field name="active" label="Активен" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="external_id" label="Внешний ID" />
          <Field name="sequence" label="Порядок" />
        </FormRow>
      </FormSection>

      <FormSection title="Связи" icon={<IconLink size={18} />}>
        <Field name="connector_id" label="Коннектор" />
        <Field name="contact_id" label="Контакт" />
      </FormSection>

      <FormSection title="Дополнительно" icon={<IconSettings size={18} />}>
        <Field name="raw" label="Сырые данные" />
        <FormRow cols={2}>
          <Field name="create_date" label="Дата создания" />
          <Field name="write_date" label="Дата изменения" />
        </FormRow>
      </FormSection>
    </Form>
  );
}
