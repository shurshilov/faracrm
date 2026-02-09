import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import type {
  TaskRecord,
  ProjectRecord,
  TaskStageRecord,
  TaskTagRecord,
} from '@/types/records';
import { useTranslation } from 'react-i18next';

// ==================== Task ====================

export function ViewListTasks() {
  const { t } = useTranslation('tasks');
  return (
    <List<TaskRecord> model="task" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="project_id" label={t('fields.project_id')} />
      <Field name="stage_id" label={t('fields.stage_id')} />
      <Field name="user_id" label={t('fields.user_id')} />
      <Field name="priority" label={t('fields.priority')} />
      <Field name="date_start" label={t('fields.date_start')} />
      <Field name="date_end" label={t('fields.date_end')} />
      <Field name="date_deadline" label={t('fields.date_deadline')} />
      <Field name="progress" label={t('fields.progress')} />
      <Field name="active" label={t('fields.active')} />
    </List>
  );
}

// ==================== Project ====================

export function ViewListProjects() {
  const { t } = useTranslation('tasks');
  return (
    <List<ProjectRecord> model="project" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="status" label={t('fields.status')} />
      <Field name="manager_id" label={t('fields.manager_id')} />
      <Field name="date_start" label={t('fields.date_start')} />
      <Field name="date_end" label={t('fields.date_end')} />
      <Field name="active" label={t('fields.active')} />
    </List>
  );
}

// ==================== Task Stage ====================

export function ViewListTaskStages() {
  const { t } = useTranslation('tasks');
  return (
    <List<TaskStageRecord> model="task_stage" order="asc" sort="sequence">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="sequence" label={t('fields.sequence')} />
      <Field name="color" label={t('fields.color')} />
      <Field name="is_closed" label={t('fields.is_closed')} />
      <Field name="fold" label={t('fields.fold')} />
    </List>
  );
}

// ==================== Task Tag ====================

export function ViewListTaskTags() {
  const { t } = useTranslation('tasks');
  return (
    <List<TaskTagRecord> model="task_tag" order="asc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="color" label={t('fields.color')} />
      <Field name="active" label={t('fields.active')} />
    </List>
  );
}

// Re-export for backward compat (used by Form.tsx, Kanban.tsx, Gantt.tsx)
export type { TaskRecord as Task } from '@/types/records';
export type { ProjectRecord } from '@/types/records';
