import { Form } from '@/components/Form/Form';
import { Field } from '@/components/List/Field';
import { ViewFormProps } from '@/route/type';

import {
  FormRow,
  FormTabs,
  FormTab,
  FormSheet,
} from '@/components/Form/Layout';
import {
  IconSubtask,
  IconClock,
  IconTag,
  IconListDetails,
  IconAlignBoxLeftTop,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import type {
  TaskRecord as Task,
  ProjectRecord,
  TaskStageRecord,
  TaskTagRecord,
} from '@/types/records';

// ==================== Task Form ====================

export function ViewFormTask(props: ViewFormProps) {
  const { t } = useTranslation('tasks');
  return (
    <Form<Task> model="tasks" {...props}>
      {/* Основные поля — Sheet (без рамки, компактно сверху) */}
      <FormSheet>
        <FormRow cols={2}>
          <Field name="name" label={t('fields.name')} />
          <Field name="stage_id" label={t('fields.stage_id')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="project_id" label={t('fields.project_id')} />
          <Field name="user_id" label={t('fields.user_id')} />
        </FormRow>
        <FormRow cols={4}>
          <Field name="priority" label={t('fields.priority')} />
          <Field name="date_start" label={t('fields.date_start')} />
          <Field name="date_end" label={t('fields.date_end')} />
          <Field name="date_deadline" label={t('fields.date_deadline')} />
        </FormRow>
        <FormRow cols={4}>
          <Field name="color" label={t('fields.color')} />
          <Field name="sequence" label={t('fields.sequence')} />
          <Field name="parent_id" label={t('fields.parent_id')} />
          <Field name="active" label={t('fields.active')} />
        </FormRow>
      </FormSheet>

      {/* Вкладки */}
      <FormTabs defaultTab="description">
        {/* Описание */}
        <FormTab
          name="description"
          label={t('sections.description')}
          icon={<IconAlignBoxLeftTop size={16} />}>
          <Field name="description" label={t('fields.description')} />
        </FormTab>

        {/* Теги */}
        <FormTab
          name="tags"
          label={t('sections.tags')}
          icon={<IconTag size={16} />}>
          <Field name="tag_ids" label={t('fields.tag_ids')}>
            <Field name="id" />
            <Field name="name" />
            <Field name="color" />
          </Field>
        </FormTab>

        {/* Трекинг времени */}
        <FormTab
          name="time"
          label={t('sections.time')}
          icon={<IconClock size={16} />}>
          <FormRow cols={3}>
            <Field name="planned_hours" label={t('fields.planned_hours')} />
            <Field name="effective_hours" label={t('fields.effective_hours')} />
            <Field name="progress" label={t('fields.progress')} />
          </FormRow>
        </FormTab>

        {/* Подзадачи */}
        <FormTab
          name="subtasks"
          label={t('sections.subtasks')}
          icon={<IconSubtask size={16} />}>
          <Field name="child_ids" label={t('fields.child_ids')}>
            <Field name="id" />
            <Field name="name" />
            <Field name="stage_id" />
            <Field name="user_id" />
            <Field name="priority" />
            <Field name="progress" />
          </Field>
        </FormTab>
      </FormTabs>
    </Form>
  );
}

// ==================== Project Form ====================

export function ViewFormProject(props: ViewFormProps) {
  const { t } = useTranslation('tasks');
  return (
    <Form<ProjectRecord> model="project" {...props}>
      {/* Основные поля — Sheet */}
      <FormSheet>
        <FormRow cols={2}>
          <Field name="name" label={t('fields.name')} />
          <Field name="status" label={t('fields.status')} />
        </FormRow>
        <FormRow cols={2}>
          <Field name="manager_id" label={t('fields.manager_id')} />
          <Field name="active" label={t('fields.active')} />
        </FormRow>
        <FormRow cols={3}>
          <Field name="date_start" label={t('fields.date_start')} />
          <Field name="date_end" label={t('fields.date_end')} />
          <Field name="color" label={t('fields.color')} />
        </FormRow>
      </FormSheet>

      {/* Вкладки */}
      <FormTabs defaultTab="description">
        {/* Описание */}
        <FormTab
          name="description"
          label={t('sections.description')}
          icon={<IconAlignBoxLeftTop size={16} />}>
          <Field name="description" label={t('fields.description')} />
        </FormTab>

        {/* Задачи */}
        <FormTab
          name="tasks"
          label={t('sections.tasks')}
          icon={<IconListDetails size={16} />}>
          <Field name="task_ids" label={t('fields.task_ids')}>
            <Field name="id" />
            <Field name="name" />
            <Field name="stage_id" />
            <Field name="user_id" />
            <Field name="priority" />
            <Field name="date_deadline" />
            <Field name="progress" />
          </Field>
        </FormTab>
      </FormTabs>
    </Form>
  );
}

// ==================== Task Stage Form ====================

export function ViewFormTaskStage(props: ViewFormProps) {
  const { t } = useTranslation('tasks');
  return (
    <Form<TaskStageRecord> model="task_stage" {...props}>
      <FormSheet>
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
      </FormSheet>
    </Form>
  );
}

// ==================== Task Tag Form ====================

export function ViewFormTaskTag(props: ViewFormProps) {
  const { t } = useTranslation('tasks');
  return (
    <Form<TaskTagRecord> model="task_tag" {...props}>
      <FormSheet>
        <FormRow cols={2}>
          <Field name="name" label={t('fields.name')} />
          <Field name="color" label={t('fields.color')} />
        </FormRow>
        <Field name="active" label={t('fields.active')} />
      </FormSheet>
    </Form>
  );
}
