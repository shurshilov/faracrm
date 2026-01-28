import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

interface SavedFilterRecord {
  id: number;
  name: string;
  model_name: string;
  filter_data: string;
  user_id?: number;
  is_global: boolean;
  is_default: boolean;
  use_count: number;
  last_used_at?: string;
  created_at?: string;
}

export function ViewListSavedFilters() {
  return (
    <List<SavedFilterRecord>
      model="saved_filters"
      order="desc"
      sort="use_count">
      <Field name="id" />
      <Field name="name" />
      <Field name="model_name" />
      <Field name="is_global" />
      <Field name="is_default" />
      <Field name="use_count" />
      <Field name="last_used_at" />
    </List>
  );
}

export default ViewListSavedFilters;
