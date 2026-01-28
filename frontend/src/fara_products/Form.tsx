import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { Product } from '@/services/api/product';
import { Category } from '@/services/api/category';
import { Uom } from '@/services/api/uoms';
import {
  FormSection,
  FormRow,
  FormSheet,
} from '@/components/Form/Layout';
import {
  IconCurrencyDollar,
  IconRuler,
  IconInfoCircle,
  IconTag,
} from '@tabler/icons-react';

export function ViewForm(props: ViewFormProps) {
  return (
    <Form<Product> model="product" {...props}>
      {/* Основной блок с изображением и ключевыми данными */}
      <FormSheet avatar={<Field name="image" />}>
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="type" label="Тип" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="category_id" label="Категория" />
          <Field name="company_id" label="Компания" />
        </FormRow>
      </FormSheet>

      {/* Коды и идентификаторы */}
      <FormSection title="Идентификация" icon={<IconInfoCircle size={18} />}>
        <FormRow cols={3}>
          <Field name="default_code" label="Внутр. код" />
          <Field name="code" label="Код" />
          <Field name="barcode" label="Штрихкод" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="id" label="ID" />
          <Field name="uom_id" label="Ед. измерения" />
        </FormRow>
      </FormSection>

      {/* Цены */}
      <FormSection title="Цены" icon={<IconCurrencyDollar size={18} />}>
        <FormRow cols={3}>
          <Field name="list_price" label="Цена продажи" />
          <Field name="standard_price" label="Себестоимость" />
          <Field name="extra_price" label="Доп. цена" />
        </FormRow>
      </FormSection>

      {/* Характеристики */}
      <FormSection title="Характеристики" icon={<IconRuler size={18} />}>
        <FormRow cols={2}>
          <Field name="weight" label="Вес" />
          <Field name="volume" label="Объём" />
        </FormRow>
        <Field name="description" label="Описание" />
      </FormSection>
    </Form>
  );
}

/**
 * Форма категории
 */
export function ViewFormCategory(props: ViewFormProps) {
  return (
    <Form<Category> model="category" {...props}>
      <FormSection title="Категория" icon={<IconTag size={18} />}>
        <FormRow cols={2}>
          <Field name="id" label="ID" />
          <Field name="name" label="Название" />
        </FormRow>
      </FormSection>
    </Form>
  );
}

/**
 * Форма единицы измерения
 */
export function ViewFormUom(props: ViewFormProps) {
  return (
    <Form<Uom> model="uom" {...props}>
      <FormSection title="Единица измерения" icon={<IconRuler size={18} />}>
        <FormRow cols={2}>
          <Field name="id" label="ID" />
          <Field name="name" label="Название" />
        </FormRow>
      </FormSection>
    </Form>
  );
}
