import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import type { ProductRecord, CategoryRecord, UomRecord } from '@/types/records';

export function ViewList() {
  return (
    <List<ProductRecord> model="products" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
      <Field name="description" />
      <Field name="type" />
      <Field name="uom_id" />
      <Field name="company_id" />
      <Field name="category_id" />
      <Field name="default_code" />
      <Field name="code" />
      <Field name="barcode" />
    </List>
  );
}

export function ViewListCategory() {
  return (
    <List<CategoryRecord> model="category" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
    </List>
  );
}

export function ViewListUom() {
  return (
    <List<UomRecord> model="uom" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
    </List>
  );
}
