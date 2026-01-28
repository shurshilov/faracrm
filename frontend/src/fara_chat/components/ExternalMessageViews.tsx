import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { ViewFormProps } from '@/route/type';
import { FaraRecord } from '@/services/api/crudTypes';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconMail, IconLink } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

// === List ===
export function ViewListExternalMessage() {
  const { t } = useTranslation('chat');
  
  return (
    <List<FaraRecord> model="chat_external_message" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="external_id" label={t('fields.external_message_id')} />
      <Field name="external_chat_id" label={t('fields.external_chat_id')} />
      <Field name="connector_id" label={t('fields.connector_id')} />
      <Field name="message_id" label={t('fields.message_id')} />
      <Field name="create_date" label={t('fields.create_date')} />
    </List>
  );
}

// === Form ===
export function ViewFormExternalMessage(props: ViewFormProps) {
  const { t } = useTranslation('chat');
  
  return (
    <Form<FaraRecord> model="chat_external_message" {...props}>
      <FormSection title={t('externalMessage.sections.connection')} icon={<IconMail size={18} />}>
        <FormRow cols={2}>
          <Field name="external_id" label={t('fields.external_message_id')} />
          <Field name="external_chat_id" label={t('fields.external_chat_id')} />
        </FormRow>
        <Field name="create_date" label={t('fields.create_date')} />
      </FormSection>

      <FormSection title={t('externalMessage.sections.relations')} icon={<IconLink size={18} />}>
        <FormRow cols={2}>
          <Field name="connector_id" label={t('fields.connector_id')} />
          <Field name="message_id" label={t('fields.message_id')} />
        </FormRow>
      </FormSection>
    </Form>
  );
}
