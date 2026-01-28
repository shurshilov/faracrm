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
  return (
    <List<SchemaLanguage> model="language" order="asc" sort="code">
      <Field name="id" />
      <Field name="code" />
      <Field name="name" />
      <Field name="flag" />
      <Field name="active" />
    </List>
  );
}

export default ViewListLanguage;
