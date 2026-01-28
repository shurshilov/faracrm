import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { SchemaUser } from '@/services/api/users';
import { useTranslation } from 'react-i18next';

export default function ViewListUsers() {
  const { t } = useTranslation('users');

  return (
    <List<SchemaUser> model="users" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="login" label={t('fields.login')} />
      {/* <Field name="email" label={t('fields.email')} /> */}
      <Field name="role_ids" label={t('fields.role_ids')} />
      <Field name="contact_ids" label={t('fields.contact_ids')} />
    </List>
  );
}
