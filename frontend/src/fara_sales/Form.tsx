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
  IconUser,
  IconAddressBook,
  IconList,
  IconReceipt,
  IconProgress,
  IconPalette,
} from '@tabler/icons-react';
import { useParams } from 'react-router-dom';
import { PrintButton } from '@/fara_report_docx/PrintButton';
import { FieldContacts } from '@/components/ContactsWidget';

/**
 * Форма заказа на продажу
 */
export function ViewFormSales(props: ViewFormProps) {
  const { id } = useParams<{ id: string }>();

  return (
    <Form<SaleRecord>
      model="sale"
      {...props}
      actions={<PrintButton model="sale" recordId={id} />}>
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
          <Field name="company_id" label="Компания" />
        </FormRow>
        <Field name="active" label="Активен" />
      </FormSection>

      {/* Ответственный и даты */}
      <FormSection title="Ответственный" icon={<IconUser size={18} />}>
        <FormRow cols={2}>
          <Field name="user_id" label="Менеджер" />
          <Field name="date_order" label="Дата заказа" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="origin" label="Источник" />
          <Field name="id" label="ID" />
        </FormRow>
      </FormSection>

      {/* Контакты клиента */}
      <FormSection
        title="Контакты клиента"
        icon={<IconAddressBook size={18} />}>
        <FieldContacts
          name="contact_ids"
          label="Контакты"
          parentField="partner_id"
          parentModel="partners"
        />
      </FormSection>

      {/* Вкладки */}
      <FormTabs defaultTab="lines">
        <FormTab
          name="lines"
          label="Позиции заказа"
          icon={<IconList size={16} />}>
          <Field name="order_line_ids">
            <Field name="id" />
            <Field name="product_id" />
            <Field name="product_uom_qty" />
            <Field name="product_uom_id" />
            <Field name="price_unit" />
            <Field name="discount" />
            <Field name="tax_id" />
            <Field name="price_subtotal" />
            <Field name="price_total" />
          </Field>
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
export function ViewFormSaleLines(props: ViewFormProps) {
  return (
    <Form<SaleLineRecord> model="sale_line" {...props}>
      <FormSection title="Позиция заказа" icon={<IconList size={18} />}>
        <FormRow cols={2}>
          <Field name="sale_id" label="Заказ" />
          <Field name="sequence" label="Последовательность" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="product_id" label="Товар" />
          <Field name="product_uom_id" label="Ед. измерения" />
        </FormRow>
      </FormSection>

      <FormSection title="Цены и количество" icon={<IconReceipt size={18} />}>
        <FormRow cols={3}>
          <Field name="product_uom_qty" label="Количество" />
          <Field name="price_unit" label="Цена за ед." />
          <Field name="discount" label="Скидка (%)" />
        </FormRow>
        <FormRow cols={3}>
          <Field name="tax_id" label="Налог" />
          <Field name="price_subtotal" label="Подитог" />
          <Field name="price_total" label="Итого" />
        </FormRow>
        <Field name="price_tax" label="Сумма налога" />
      </FormSection>

      <Field name="notes" label="Заметки" />
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
