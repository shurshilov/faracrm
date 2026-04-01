import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import DateTimeCell from '@/components/ListCells/DateTimeCell';
import RelationCell from '@/components/ListCells/RelationCell';
import type {
  SaleRecord,
  SaleLineRecord,
  TaxRecord,
  SaleStageRecord,
} from '@/types/records';

export function ViewListSales() {
  return (
    <List<SaleRecord> model="sales" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
      <Field
        name="date_order"
        render={value => <DateTimeCell value={value} format="compact" />}
      />
      <Field
        name="partner_id"
        render={value => <RelationCell value={value} model="partners" />}
      />
      <Field
        name="user_id"
        render={value => <RelationCell value={value} model="users" />}
      />
      <Field
        name="company_id"
        render={value => <RelationCell value={value} model="company" />}
      />
      <Field
        name="stage_id"
        render={value => <RelationCell value={value} model="stages" />}
      />
      <Field name="active" />
    </List>
  );
}

export function ViewListSaleLines() {
  return (
    <List<SaleLineRecord> model="sale_line" order="desc" sort="id">
      <Field name="id" />
      <Field
        name="sale_id"
        render={value => <RelationCell value={value} model="sales" />}
      />
      <Field name="product_id" />
      <Field name="product_uom_qty" />
      <Field name="product_uom_id" />
      <Field name="price_unit" />
      <Field name="discount" />
      <Field name="price_subtotal" />
      <Field name="price_total" />
    </List>
  );
}

export function ViewListTax() {
  return (
    <List<TaxRecord> model="tax" order="desc" sort="id">
      <Field name="id" />
      <Field name="name" />
    </List>
  );
}

export function ViewListSaleStage() {
  return (
    <List<SaleStageRecord> model="sale_stage" order="asc" sort="sequence">
      <Field name="id" />
      <Field name="name" />
      <Field name="sequence" />
      <Field name="color" />
      <Field name="fold" />
    </List>
  );
}
