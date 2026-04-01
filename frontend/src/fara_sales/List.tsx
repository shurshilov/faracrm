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
import { useTranslation } from 'react-i18next';

export function ViewListSales() {
  const { t } = useTranslation('sales');
  return (
    <List<SaleRecord> model="sales" order="desc" sort="id">
      <Field name="id" label={t('sales.id')} />
      <Field name="name" label={t('sales.name')} />
      <Field
        name="date_order"
        label={t('sales.date_order')}
        render={value => <DateTimeCell value={value} format="compact" />}
      />
      <Field
        name="partner_id"
        label={t('sales.partner_id')}
        render={value => <RelationCell value={value} model="partners" />}
      />
      <Field
        name="user_id"
        label={t('sales.user_id')}
        render={value => <RelationCell value={value} model="users" />}
      />
      <Field
        name="company_id"
        label={t('sales.company_id')}
        render={value => <RelationCell value={value} model="company" />}
      />
      <Field
        name="stage_id"
        label={t('sales.stage_id')}
        render={value => <RelationCell value={value} model="stages" />}
      />
      <Field name="active" label={t('sales.active')} />
    </List>
  );
}

export function ViewListSaleLines() {
  const { t } = useTranslation('sales');
  return (
    <List<SaleLineRecord> model="sale_line" order="desc" sort="id">
      <Field name="id" label={t('sales.id')} />
      <Field
        name="sale_id"
        label={t('sales.sale_id')}
        render={value => <RelationCell value={value} model="sales" />}
      />
      <Field name="product_id" label={t('sales.product_id')} />
      <Field name="product_uom_qty" label={t('sales.product_uom_qty')} />
      <Field name="product_uom_id" label={t('sales.product_uom_id')} />
      <Field name="price_unit" label={t('sales.price_unit')} />
      <Field name="discount" label={t('sales.discount')} />
      <Field name="price_subtotal" label={t('sales.price_subtotal')} />
      <Field name="price_total" label={t('sales.price_total')} />
    </List>
  );
}

export function ViewListTax() {
  const { t } = useTranslation('sales');
  return (
    <List<TaxRecord> model="tax" order="desc" sort="id">
      <Field name="id" label={t('sales.id')} />
      <Field name="name" label={t('tax.name')} />
    </List>
  );
}

export function ViewListSaleStage() {
  const { t } = useTranslation('sales');
  return (
    <List<SaleStageRecord> model="sale_stage" order="asc" sort="sequence">
      <Field name="id" label={t('sale_stage.id')} />
      <Field name="name" label={t('sale_stage.name')} />
      <Field name="sequence" label={t('sale_stage.sequence')} />
      <Field name="color" label={t('sale_stage.color')} />
      <Field name="fold" label={t('sale_stage.fold')} />
    </List>
  );
}
