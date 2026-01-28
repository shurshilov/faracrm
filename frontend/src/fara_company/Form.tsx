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
} from '@tabler/icons-react';

// Тип для Company
export type Company = {
  id: number;
  name: string;
  active?: boolean;
  sequence?: number;
  parent_id?: { id: number; name: string } | null;
  child_ids?: { id: number; name: string }[] | null;
};

/**
 * Форма компании
 */
export function ViewFormCompany(props: ViewFormProps) {
  return (
    <Form<Company> model="company" {...props}>
      {/* Основная информация */}
      <FormSection title="Основная информация" icon={<IconBuilding size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="active" label="Активна" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="id" label="ID" />
          <Field name="sequence" label="Последовательность" />
        </FormRow>
        <Field name="parent_id" label="Родительская компания" />
      </FormSection>

      {/* Вкладки */}
      <FormTabs defaultTab="children">
        <FormTab 
          name="children" 
          label="Дочерние компании" 
          icon={<IconUsers size={16} />}
        >
          <Field name="child_ids">
            <Field name="id" />
            <Field name="name" />
          </Field>
        </FormTab>
      </FormTabs>
    </Form>
  );
}
