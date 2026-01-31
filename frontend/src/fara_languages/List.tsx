import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

interface SchemaLanguage {
  id: number;
  code: string;
  name: string;
  flag: string;
  active: boolean;
}

export function ViewListLanguage() {
  const { t } = useTranslation('languages');

  return (
    <List<SchemaLanguage> model="language" order="asc" sort="code">
      <Field name="id" label={t('fields.id')} />
      <Field name="code" label={t('fields.code')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="flag" label={t('fields.flag')} />
      <Field name="active" label={t('fields.active')} />
    </List>
  );
}

export default ViewListLanguage;
