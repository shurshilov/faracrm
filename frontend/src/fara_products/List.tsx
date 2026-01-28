import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { Product } from '@/services/api/product';
import { Category } from '@/services/api/category';
import { Uom } from '@/services/api/uoms';

export function ViewList() {
  return (
    <List<Product> model="product" order="desc" sort="id">
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
    <List<Category> model="category" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
    </List>
  );
}

export function ViewListUom() {
  return (
    <List<Uom> model="uom" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
    </List>
  );
}
