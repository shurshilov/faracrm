import { useTranslation } from 'react-i18next';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { ViewFormProps } from '@/route/type';
import type { ChatExternalAccountRecord } from '@/types/records';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconUser, IconLink, IconSettings } from '@tabler/icons-react';

// === List ===
export function ViewListExternalAccount() {
  const { t } = useTranslation('chat');

  return (
    <List<ChatExternalAccountRecord>
      model="chat_external_account"
      order="desc"
      sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="external_id" label={t('fields.external_id')} />
      <Field name="connector_id" label={t('fields.connector_id')} />
      <Field name="contact_id" label={t('fields.contact_id')} />
      <Field name="active" label={t('fields.active')} />
      <Field name="create_date" label={t('fields.create_date')} />
    </List>
  );
}

// === Form ===
export function ViewFormExternalAccount(props: ViewFormProps) {
  const { t } = useTranslation('chat');

  return (
    <Form<ChatExternalAccountRecord> model="chat_external_account" {...props}>
      <FormSection
        title={t('externalAccount.groups.info')}
        icon={<IconUser size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label={t('externalAccount.fields.name')} />
          <Field name="active" label={t('externalAccount.fields.active')} />
        </FormRow>
        <FormRow cols={2}>
          <Field
            name="external_id"
            label={t('externalAccount.fields.externalId')}
          />
          <Field name="sequence" label={t('externalAccount.fields.sequence')} />
        </FormRow>
      </FormSection>

      <FormSection
        title={t('externalAccount.groups.connection')}
        icon={<IconLink size={18} />}>
        <Field
          name="connector_id"
          label={t('externalAccount.fields.connectorId')}
        />
        <Field
          name="contact_id"
          label={t('externalAccount.fields.partnerId')}
        />
      </FormSection>

      <FormSection
        title={t('externalAccount.groups.rawData')}
        icon={<IconSettings size={18} />}>
        <Field name="raw" label={t('externalAccount.fields.raw')} />
        <FormRow cols={2}>
          <Field
            name="create_date"
            label={t('externalAccount.fields.createDate')}
          />
          <Field
            name="write_date"
            label={t('externalAccount.fields.writeDate')}
          />
        </FormRow>
      </FormSection>
    </Form>
  );
}
