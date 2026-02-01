import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';
import { FaraRecord } from '@/services/api/crudTypes';
import {
  FormSection,
  FormRow,
} from '@/components/Form/Layout';
import {
  IconSubtask,
  IconCalendar,
  IconClock,
  IconUser,
  IconTag,
  IconProgress,
  IconPalette,
  IconListDetails,
  IconFolder,
  IconAlignBoxLeftTop,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Task, ProjectRecord } from './List';

// ==================== Task Form ====================

export function ViewFormTask(props: ViewFormProps) {
  const { t } = useTranslation('tasks');
  return (
    <Form<Task> model="task" {...props}>
      {/* Основная информация */}
      <FormSection title={t('sections.general')} icon={<IconListDetails size={18} />}>
        <Field name="name" label={t('fields.name')} />
        <FormRow cols={2}>
          <Field name="project_id" label={t('fields.project_id')} />
          <Field name="stage_id" label={t('fields.stage_id')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="priority" label={t('fields.priority')} />
          <Field name="active" label={t('fields.active')} />
        </FormRow>
      </FormSection>

      {/* Описание */}
      <FormSection title={t('sections.description')} icon={<IconAlignBoxLeftTop size={18} />}>
        <Field name="description" label={t('fields.description')} />
      </FormSection>

      {/* Назначение */}
      <FormSection title={t('sections.assignment')} icon={<IconUser size={18} />}>
        <FormRow cols={2}>
          <Field name="user_id" label={t('fields.user_id')} />
          <Field name="tag_ids" label={t('fields.tag_ids')} />
        </FormRow>
      </FormSection>

      {/* Даты */}
      <FormSection title={t('sections.dates')} icon={<IconCalendar size={18} />}>
        <FormRow cols={3}>
          <Field name="date_start" label={t('fields.date_start')} />
          <Field name="date_end" label={t('fields.date_end')} />
          <Field name="date_deadline" label={t('fields.date_deadline')} />
        </FormRow>
      </FormSection>

      {/* Трекинг времени */}
      <FormSection title={t('sections.time')} icon={<IconClock size={18} />}>
        <FormRow cols={3}>
          <Field name="planned_hours" label={t('fields.planned_hours')} />
          <Field name="effective_hours" label={t('fields.effective_hours')} />
          <Field name="progress" label={t('fields.progress')} />
        </FormRow>
      </FormSection>

      {/* Подзадачи */}
      <FormSection title={t('sections.subtasks')} icon={<IconSubtask size={18} />}>
        <Field name="parent_id" label={t('fields.parent_id')} />
        <Field name="child_ids" label={t('fields.child_ids')} />
      </FormSection>

      {/* Оформление */}
      <FormSection title={t('sections.appearance')} icon={<IconPalette size={18} />}>
        <FormRow cols={2}>
          <Field name="color" label={t('fields.color')} />
          <Field name="sequence" label={t('fields.sequence')} />
        </FormRow>
      </FormSection>
    </Form>
  );
}

// ==================== Project Form ====================

export function ViewFormProject(props: ViewFormProps) {
  const { t } = useTranslation('tasks');
  return (
    <Form<ProjectRecord> model="project" {...props}>
      <FormSection title={t('sections.general')} icon={<IconFolder size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label={t('fields.name')} />
          <Field name="status" label={t('fields.status')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="manager_id" label={t('fields.manager_id')} />
          <Field name="active" label={t('fields.active')} />
        </FormRow>
      </FormSection>

      <FormSection title={t('sections.description')} icon={<IconAlignBoxLeftTop size={18} />}>
        <Field name="description" label={t('fields.description')} />
      </FormSection>

      <FormSection title={t('sections.dates')} icon={<IconCalendar size={18} />}>
        <FormRow cols={2}>
          <Field name="date_start" label={t('fields.date_start')} />
          <Field name="date_end" label={t('fields.date_end')} />
        </FormRow>
      </FormSection>

      <FormSection title={t('sections.appearance')} icon={<IconPalette size={18} />}>
        <Field name="color" label={t('fields.color')} />
      </FormSection>

      <FormSection title={t('sections.tasks')} icon={<IconListDetails size={18} />}>
        <Field name="task_ids" label={t('fields.task_ids')} />
      </FormSection>
    </Form>
  );
}

// ==================== Task Stage Form ====================

export function ViewFormTaskStage(props: ViewFormProps) {
  const { t } = useTranslation('tasks');
  return (
    <Form<FaraRecord> model="task_stage" {...props}>
      <FormSection title={t('sections.stage')} icon={<IconProgress size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label={t('fields.name')} />
          <Field name="sequence" label={t('fields.sequence')} />
        </FormRow>
        <FormRow cols={3}>
          <Field name="color" label={t('fields.color')} />
          <Field name="is_closed" label={t('fields.is_closed')} />
          <Field name="fold" label={t('fields.fold')} />
        </FormRow>
        <Field name="active" label={t('fields.active')} />
      </FormSection>
    </Form>
  );
}

// ==================== Task Tag Form ====================

export function ViewFormTaskTag(props: ViewFormProps) {
  const { t } = useTranslation('tasks');
  return (
    <Form<FaraRecord> model="task_tag" {...props}>
      <FormSection title={t('sections.tag')} icon={<IconTag size={18} />}>
        <FormRow cols={2}>
          <Field name="name" label={t('fields.name')} />
          <Field name="color" label={t('fields.color')} />
        </FormRow>
        <Field name="active" label={t('fields.active')} />
      </FormSection>
    </Form>
  );
}
