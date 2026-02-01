import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { FaraRecord } from '@/services/api/crudTypes';
import { useTranslation } from 'react-i18next';

// ==================== Task ====================

export interface Task extends FaraRecord {
  name: string;
  active: boolean;
  sequence: number;
  description: string;
  project_id: FaraRecord | null;
  stage_id: FaraRecord | null;
  parent_id: FaraRecord | null;
  user_id: FaraRecord | null;
  priority: string;
  tag_ids: FaraRecord[];
  date_start: string | null;
  date_end: string | null;
  date_deadline: string | null;
  planned_hours: number;
  effective_hours: number;
  progress: number;
  color: string;
}

export function ViewListTasks() {
  const { t } = useTranslation('tasks');
  return (
    <List<Task> model="task" order="desc" sort="id">
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

export interface ProjectRecord extends FaraRecord {
  name: string;
  active: boolean;
  status: string;
  manager_id: FaraRecord | null;
  date_start: string | null;
  date_end: string | null;
  color: string;
}

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
    <List<FaraRecord> model="task_stage" order="asc" sort="sequence">
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
    <List<FaraRecord> model="task_tag" order="asc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="color" label={t('fields.color')} />
      <Field name="active" label={t('fields.active')} />
    </List>
  );
}
