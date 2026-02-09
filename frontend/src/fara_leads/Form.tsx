import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import type {
  LeadRecord,
  LeadStageRecord,
  TeamCrmRecord,
} from '@/types/records';
import { FormSection, FormRow } from '@/components/Form/Layout';
import {
  IconUser,
  IconPhone,
  IconBuilding,
  IconTag,
  IconProgress,
  IconPalette,
} from '@tabler/icons-react';

/**
 * Форма лида/возможности
 */
export function ViewFormLeads(props: ViewFormProps) {
  return (
    <Form<LeadRecord> model="lead" {...props}>
      {/* Основная информация */}
      <FormSection title="Основная информация" icon={<IconUser size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="type" label="Тип" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="stage_id" label="Стадия" />
          <Field name="active" label="Активен" />
        </FormRow>
      </FormSection>

      {/* Связи */}
      <FormSection title="Связи" icon={<IconBuilding size={18} />}>
        <FormRow cols={2}>
          <Field name="parent_id" label="Партнёр" />
          <Field name="company_id" label="Компания" />
        </FormRow>
        <Field name="user_id" label="Ответственный" />
      </FormSection>

      {/* Контакты */}
      <FormSection title="Контактная информация" icon={<IconPhone size={18} />}>
        <FormRow cols={2}>
          <Field name="email" label="Email" />
          <Field name="phone" label="Телефон" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="mobile" label="Мобильный" />
          <Field name="website" label="Вебсайт" />
        </FormRow>
      </FormSection>

      {/* Заметки */}
      <FormSection title="Дополнительно" icon={<IconTag size={18} />}>
        <Field name="notes" label="Заметки" />
      </FormSection>
    </Form>
  );
}

/**
 * Форма команды CRM
 */
export function ViewFormTeamCrm(props: ViewFormProps) {
  return (
    <Form<TeamCrmRecord> model="team_crm" {...props}>
      <FormSection title="Команда CRM" icon={<IconBuilding size={18} />}>
        <FormRow cols={2}>
          <Field name="id" label="ID" />
          <Field name="name" label="Название" />
        </FormRow>
      </FormSection>
    </Form>
  );
}

/**
 * Форма стадии лида
 */
export function ViewFormLeadStage(props: ViewFormProps) {
  return (
    <Form<LeadStageRecord> model="lead_stage" {...props}>
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
