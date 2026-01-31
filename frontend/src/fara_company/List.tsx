import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

export type Company = {
  id: number;
  name: string;
  active?: boolean;
  sequence?: number;
  parent_id?: { id: number; name: string } | null;
  child_ids?: { id: number; name: string }[] | null;
};

export function ViewListCompany() {
  const { t } = useTranslation('company');

  return (
    <List<Company> model="company" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="active" label={t('fields.active')} />
      <Field name="sequence" label={t('fields.sequence')} />
      <Field name="parent_id" label={t('fields.parent_id')} />
    </List>
  );
}
