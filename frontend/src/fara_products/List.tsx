import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import RelationCell from '@/components/ListCells/RelationCell';
import type { ProductRecord, CategoryRecord, UomRecord } from '@/types/records';
import { useTranslation } from 'react-i18next';

export function ViewList() {
  const { t } = useTranslation('products');
  return (
    <List<ProductRecord> model="products" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="description" label={t('fields.description')} />
      <Field name="type" label={t('fields.type')} />
      <Field name="uom_id" label={t('fields.uom_id')} />
      <Field
        name="company_id"
        render={value => <RelationCell value={value} model="company" />}
        label={t('fields.company_id')}
      />
      <Field name="category_id" label={t('fields.category_id')} />
      <Field name="default_code" label={t('fields.default_code')} />
      <Field name="code" label={t('fields.code')} />
      <Field name="barcode" label={t('fields.barcode')} />
    </List>
  );
}

export function ViewListCategory() {
  const { t } = useTranslation('products');
  return (
    <List<CategoryRecord> model="category" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
    </List>
  );
}

export function ViewListUom() {
  const { t } = useTranslation('products');
  return (
    <List<UomRecord> model="uom" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
    </List>
  );
}
