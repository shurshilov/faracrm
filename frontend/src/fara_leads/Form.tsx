import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import type {
  LeadRecord,
  LeadStageRecord,
  TeamCrmRecord,
} from '@/types/records';
import {
  FormSection,
  FormRow,
  FormTabs,
  FormTab,
} from '@/components/Form/Layout';
import {
  IconUser,
  IconBuilding,
  IconTag,
  IconProgress,
  IconPalette,
} from '@tabler/icons-react';

/**
 * Форма лида/возможности.
 * По аналогии с формой продаж: основные поля сверху (FormSection),
 * остальное — во вкладках (FormTabs).
 */
export function ViewFormLeads(props: ViewFormProps) {
  return (
    <Form<LeadRecord> model="leads" {...props}>
      {/* Основная информация */}
      <FormSection title="Основная информация" icon={<IconUser size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label="Название" />
          <Field name="type" label="Тип" />
        </FormRow>
        <FormRow cols={2}>
          <Field name="partner_id" label="Партнёр" />
          {/* Контакты партнёра: parentField="partner_id" — владелец берётся
              из partner_id лида; фильтр контактов (partner_id) — из метаданных
              One2many. Здесь же иконка перехода в чат с партнёром. */}
          <Field
            name="contact_ids"
            widget="contacts"
            label="Контакты"
            parentField="partner_id">
            <Field name="contact_type_id" />
            <Field name="name" />
            <Field name="is_primary" />
          </Field>
        </FormRow>
        <FormRow cols={2}>
          <Field name="stage_id" label="Стадия" />
          <Field name="user_id" label="Ответственный" />
        </FormRow>
      </FormSection>

      {/* Вкладки */}
      <FormTabs defaultTab="info">
        <FormTab
          name="info"
          label="Доп. информация"
          icon={<IconBuilding size={16} />}>
          <FormSection>
            <FormRow cols={2}>
              <Field name="company_id" label="Компания" />
              <Field name="website" label="Вебсайт" />
            </FormRow>
            <Field name="active" label="Активен" />
          </FormSection>
        </FormTab>

        <FormTab name="notes" label="Заметки" icon={<IconTag size={16} />}>
          <Field name="notes" label="Заметки" />
        </FormTab>
      </FormTabs>
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
          <Field name="color" label="Цвет" widget="color" />
          <Field name="fold" label="Свёрнута в канбане" />
        </FormRow>
        <Field name="active" label="Активна" />
      </FormSection>
    </Form>
  );
}
