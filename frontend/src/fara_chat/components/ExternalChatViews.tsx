import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { ViewFormProps } from '@/route/type';
import { FaraRecord } from '@/services/api/crudTypes';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconMessage, IconLink } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

// === List ===
export function ViewListExternalChat() {
  const { t } = useTranslation('chat');
  
  return (
    <List<FaraRecord> model="chat_external_chat" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="external_id" label={t('fields.external_chat_id')} />
      <Field name="connector_id" label={t('fields.connector_id')} />
      <Field name="chat_id" label={t('fields.chat_id')} />
      <Field name="create_date" label={t('fields.create_date')} />
    </List>
  );
}

// === Form ===
export function ViewFormExternalChat(props: ViewFormProps) {
  const { t } = useTranslation('chat');
  
  return (
    <Form<FaraRecord> model="chat_external_chat" {...props}>
      <FormSection title={t('externalChat.sections.connection')} icon={<IconMessage size={18} />}>
        <FormRow cols={2}>
          <Field name="external_id" label={t('fields.external_chat_id')} />
          <Field name="create_date" label={t('fields.create_date')} />
        </FormRow>
      </FormSection>

      <FormSection title={t('externalChat.sections.relations')} icon={<IconLink size={18} />}>
        <FormRow cols={2}>
          <Field name="connector_id" label={t('fields.connector_id')} />
          <Field name="chat_id" label={t('fields.chat_id')} />
        </FormRow>
      </FormSection>
    </Form>
  );
}
