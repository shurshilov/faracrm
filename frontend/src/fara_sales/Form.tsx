import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import type {
  SaleRecord,
  SaleLineRecord,
  TaxRecord,
  SaleStageRecord,
} from '@/types/records';
import {
  FormSection,
  FormRow,
  FormTabs,
  FormTab,
} from '@/components/Form/Layout';
import {
  IconShoppingCart,
  IconList,
  IconReceipt,
  IconProgress,
  IconPalette,
  IconCurrencyDollar,
  IconPackage,
  IconServicemark,
} from '@tabler/icons-react';
import { useParams } from 'react-router-dom';
import { PrintButton } from '@/fara_report_docx/PrintButton';
import { FieldContacts } from '@/components/ContactsWidget';
import { useTranslation } from 'react-i18next';

/**
 * Форма заказа на продажу
 */
export function ViewFormSales(props: ViewFormProps) {
  const { t } = useTranslation('sales');
  const { id } = useParams<{ id: string }>();

  return (
    <Form<SaleRecord>
      model="sales"
      {...props}
      actions={<PrintButton model="sales" recordId={id} />}>
      {/* Основная информация */}
      <FormSection
        title="Основная информация"
        icon={<IconShoppingCart size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label="Номер заказа" />
          <Field name="stage_id" label="Стадия" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="partner_id" label="Клиент" />
          <FieldContacts
            name="contact_ids"
            label="Контакты"
            parentField="partner_id"
            parentModel="partners"
          />
        </FormRow>
        <FormRow cols={2}>
          <Field name="date_order" label="Дата заказа" />
          <Field name="user_id" label="Менеджер" />
        </FormRow>
      </FormSection>

      {/* Вкладки */}
      <FormTabs defaultTab="lines">
        <FormTab
          name="lines"
          label="Позиции заказа"
          icon={<IconList size={16} />}>
          <Field
            name="order_line_ids"
            label=""
            displayField="product_id"
            showCreate={true}
            showSelect={false}
            customForm={ViewFormSaleLinesPopup}
            inline_create={false}
            inline_update={false}>
            <Field name="id" label={t('sales.id')} />
            <Field name="product_id" label={t('sale_line.product_id')} />
            <Field
              name="product_uom_qty"
              label={t('sale_line.product_uom_qty')}
            />
            <Field
              name="product_uom_id"
              label={t('sale_line.product_uom_id')}
            />
            <Field name="price_unit" label={t('sale_line.price_unit')} />
            <Field name="discount" label={t('sale_line.discount')} />
            <Field name="tax_id" label={t('sale_line.tax_id')} />
            <Field
              name="price_subtotal"
              label={t('sale_line.price_subtotal')}
            />
            <Field name="price_total" label={t('sale_line.price_total')} />
          </Field>
        </FormTab>

        <FormTab
          name="info"
          label="Доп. Информация"
          icon={<IconReceipt size={16} />}>
          <FormSection>
            <FormRow cols={2}>
              <Field name="company_id" label="Компания" />
              <Field name="active" label="Активен" />
            </FormRow>
            <FormRow cols={2}>
              <Field name="origin" label="Источник" />
              {/* <Field name="id" label="ID" /> */}
            </FormRow>
          </FormSection>
        </FormTab>
        <FormTab name="notes" label="Заметки" icon={<IconReceipt size={16} />}>
          <Field name="notes" label="Заметки" />
        </FormTab>
      </FormTabs>
    </Form>
  );
}

/**
 * Форма позиции заказа
 */
export function ViewFormSaleLinesPopup(props: ViewFormProps) {
  const { t } = useTranslation('sales');
  return (
    <Form<SaleLineRecord> model="sale_line" {...props}>
      <FormSection
        title={t('sale_line.product_id')}
        icon={<IconPackage size={18} />}>
        <FormRow cols={1}>
          <Field name="product_id" label={t('sale_line.product_id')} />
        </FormRow>
        <FormRow cols={2}>
          <Field
            name="product_uom_qty"
            label={t('sale_line.product_uom_qty')}
          />
          <Field name="product_uom_id" label={t('sale_line.product_uom_id')} />
        </FormRow>
      </FormSection>

      <FormSection
        title={t('menu.price')}
        icon={<IconCurrencyDollar size={18} />}>
        <FormRow cols={2}>
          <Field name="price_unit" label={t('sale_line.price_unit')} />
          <Field name="discount" label={t('sale_line.discount')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="tax_id" label={t('sale_line.tax_id')} />
          <Field name="price_tax" label={t('sale_line.price_tax')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="price_subtotal" label={t('sale_line.price_subtotal')} />
          <Field name="price_total" label={t('sale_line.price_total')} />
        </FormRow>
      </FormSection>

      <FormSection
        title={t('menu.service')}
        icon={<IconServicemark size={18} />}>
        <FormRow cols={1}>
          <Field name="notes" label={t('sale_line.notes')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="sale_id" label={t('sale_line.sale_id')} />
          <Field name="sequence" label={t('sale_line.sequence')} />
        </FormRow>
      </FormSection>
    </Form>
  );
}
export function ViewFormSaleLines(props: ViewFormProps) {
  const { t } = useTranslation('sales');
  return (
    <Form<SaleLineRecord> model="sale_line" {...props}>
      <FormSection title="Позиция заказа" icon={<IconList size={18} />}>
        <FormRow cols={2}>
          <Field name="sale_id" label={t('sale_line.sale_id')} />
          <Field name="sequence" label={t('sale_line.sequence')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="product_id" label={t('sale_line.product_id')} />
          <Field name="product_uom_id" label={t('sale_line.product_uom_id')} />
        </FormRow>
      </FormSection>

      <FormSection title="Цены и количество" icon={<IconReceipt size={18} />}>
        <FormRow cols={3}>
          <Field
            name="product_uom_qty"
            label={t('sale_line.product_uom_qty')}
          />
          <Field name="price_unit" label={t('sale_line.price_unit')} />
          <Field name="discount" label={t('sale_line.discount')} />
        </FormRow>
        <FormRow cols={3}>
          <Field name="tax_id" label={t('sale_line.tax_id')} />
          <Field name="price_subtotal" label={t('sale_line.price_subtotal')} />
          <Field name="price_total" label={t('sale_line.price_total')} />
        </FormRow>
        <Field name="price_tax" label={t('sale_line.price_tax')} />
      </FormSection>

      <Field name="notes" label={t('sale_line.notes')} />
    </Form>
  );
}

/**
 * Форма налога
 */
export function ViewFormTax(props: ViewFormProps) {
  return (
    <Form<TaxRecord> model="tax" {...props}>
      <FormSection title="Налог" icon={<IconReceipt size={18} />}>
        <FormRow cols={2}>
          <Field name="id" label="ID" />
          <Field name="name" label="Название" />
        </FormRow>
      </FormSection>
    </Form>
  );
}

/**
 * Форма стадии продажи
 */
export function ViewFormSaleStage(props: ViewFormProps) {
  return (
    <Form<SaleStageRecord> model="sale_stage" {...props}>
      <FormSection title="Стадия" icon={<IconProgress size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="sequence" label="Последовательность" />
        </FormRow>
      </FormSection>

      <FormSection title="Настройки" icon={<IconPalette size={18} />}>
        <FormRow cols={2}>
          <Field name="color" label="Цвет" />
          <Field name="fold" label="Свёрнута в канбане" />
        </FormRow>
        <Field name="active" label="Активна" />
      </FormSection>
    </Form>
  );
}
