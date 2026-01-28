import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { Partner } from '@/services/api/partner';
import { useTranslation } from 'react-i18next';

export function ViewListPartners() {
  const { t } = useTranslation('partners');

  return (
    <List<Partner> model="partners" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="company_id" label={t('fields.company_id')} />
      <Field name="user_id" label={t('fields.user_id')} />
      <Field name="active" label={t('fields.active')} />
      <Field name="contact_ids" label={t('fields.contact_ids')} />
    </List>
  );
}
