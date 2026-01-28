import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

// Тип для Company
export type Company = {
  id: number;
  name: string;
  active?: boolean;
  sequence?: number;
  parent_id?: { id: number; name: string } | null;
  child_ids?: { id: number; name: string }[] | null;
};

export function ViewListCompany() {
  return (
    <List<Company> model="company" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
      <Field name="active" />
      <Field name="sequence" />
      <Field name="parent_id" />
    </List>
  );
}
