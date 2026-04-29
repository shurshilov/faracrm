import type { CompanyRecord as Company } from '@/types/records';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import {
  FormSection,
  FormRow,
  FormTabs,
  FormTab,
} from '@/components/Form/Layout';
import {
  IconBuilding,
  IconUsers,
  IconPhoto,
  IconTextCaption,
} from '@tabler/icons-react';

/**
 * Форма компании
 */
export function ViewFormCompany(props: ViewFormProps) {
  return (
    <Form<Company> model="company" {...props}>
      {/* Основная информация */}
      <FormSection
        title="Основная информация"
        icon={<IconBuilding size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="active" label="Активна" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="sequence" label="Последовательность" />
        </FormRow>
        <Field name="parent_id" label="Родительская компания" />
      </FormSection>

      {/* Вкладки */}
      <FormTabs defaultTab="branding">
        <FormTab
          name="branding"
          label="Брендинг"
          icon={<IconPhoto size={16} />}>
          <FormSection title="Логотипы и фон">
            <FormRow cols={3}>
              <Field name="logo_id" label="Логотип CRM" />
              <Field name="login_logo_id" label="Логотип входа" />
              <Field name="login_background_id" label="Фон страницы входа" />
            </FormRow>
          </FormSection>

          <FormSection
            title="Тексты страницы входа"
            icon={<IconTextCaption size={18} />}>
            <FormRow cols={1}>
              <Field
                name="login_title"
                label="Заголовок"
                placeholder="Вход в систему"
              />
              <Field
                name="login_subtitle"
                label="Подзаголовок"
                placeholder="Платформа для управления бизнесом"
              />
              <Field
                name="login_button_color"
                widget="color"
                label="Цвет кнопки входа"
                placeholder="#009982"
              />
              <Field
                name="login_card_style"
                label="Стиль карточки логина"
              />
            </FormRow>
          </FormSection>
        </FormTab>

        <FormTab
          name="children"
          label="Дочерние компании"
          icon={<IconUsers size={16} />}>
          <Field name="child_ids">
            <Field name="id" />
            <Field name="name" />
          </Field>
        </FormTab>
      </FormTabs>
    </Form>
  );
}
