import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { Partner } from '@/services/api/partner';
import {
  FormSection,
  FormRow,
  FormTabs,
  FormTab,
  FormSheet,
} from '@/components/Form/Layout';
import {
  IconUser,
  IconBuilding,
  IconWorld,
  IconUsers,
} from '@tabler/icons-react';

export function ViewFormPartners(props: ViewFormProps) {
  return (
    <Form<Partner> model="partners" {...props}>
      {/* Основная информация */}
      <FormSheet avatar={<Field name="image" />}>
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="active" label="Активен" />
        </FormRow>

        {/* Контакты — половина ширины */}
        <FormRow cols={2}>
          <Field name="contact_ids" widget="contacts" label="Контакты">
            <Field name="id" />
            <Field name="contact_type_id" />
            <Field name="name" />
            <Field name="is_primary" />
          </Field>
          <div />
        </FormRow>
      </FormSheet>

      {/* Вкладки */}
      <FormTabs defaultTab="children">
        <FormTab name="common" label="Общие" icon={<IconUsers size={16} />}>
          <FormRow cols={2}>
            <Field name="parent_id" label="Родительский партнёр" />
            <Field name="vat" label="ИНН" />
            <Field name="user_id" label="Ответственный" />
            <Field name="company_id" label="Компания" />
          </FormRow>
        </FormTab>
        <FormTab
          name="children"
          label="Дочерние партнёры"
          icon={<IconUsers size={16} />}>
          <Field name="child_ids">
            <Field name="id" />
            <Field name="name" />
          </Field>
        </FormTab>

        <FormTab name="notes" label="Заметки" icon={<IconBuilding size={16} />}>
          <Field name="notes" label="Заметки" />
        </FormTab>

        {/* Настройки */}
        <FormTab
          name="serrings"
          label="Настройки"
          icon={<IconWorld size={18} />}>
          <FormRow cols={2}>
            <Field name="tz" label="Часовой пояс" />
            <Field name="lang" label="Язык" />
          </FormRow>
        </FormTab>
      </FormTabs>
    </Form>
  );
}
