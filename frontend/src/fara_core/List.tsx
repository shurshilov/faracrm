import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

interface SchemaSystemSettings {
  id: number;
  key: string;
  value: string;
  description: string;
}

export function ViewListSystemSettings() {
  return (
    <List<SchemaSystemSettings> model="system_settings" order="asc" sort="key">
      <Field name="id" />
      <Field name="key" />
      <Field name="value" />
      <Field name="description" />
    </List>
  );
}

export default ViewListSystemSettings;
