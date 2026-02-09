import type { ContractRecord as Contract } from '@/types/records';
import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FormSection, FormRow } from '@/components/Form/Layout';
import { IconFileText, IconCalendar, IconSettings } from '@tabler/icons-react';

/**
 * Форма договора
 */
export function ViewFormContract(props: ViewFormProps) {
  return (
    <Form<Contract> model="contract" {...props}>
      <FormSection title="Основные данные" icon={<IconFileText size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label="Номер договора" />
          <Field name="type" label="Тип" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="partner_id" label="Контрагент" />
          <Field name="company_id" label="Компания" />
        </FormRow>
      </FormSection>

      <FormSection title="Сроки" icon={<IconCalendar size={18} />}>
        <FormRow cols={2}>
          <Field name="date_start" label="Дата начала" />
          <Field name="date_end" label="Дата окончания" />
        </FormRow>
      </FormSection>

      <FormSection title="Статус" icon={<IconSettings size={18} />}>
        <FormRow cols={3}>
          <Field name="signed" label="Подписан" />
          <Field name="stamp" label="Печать" />
          <Field name="active" label="Активен" />
        </FormRow>
      </FormSection>

      <Field name="notes" label="Примечания" />
    </Form>
  );
}
