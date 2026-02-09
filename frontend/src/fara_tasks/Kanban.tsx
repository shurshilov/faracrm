import { Kanban } from '@/components/Kanban';
import type {
  TaskRecord as Task,
  ProjectRecord,
  TaskStageRecord,
  TaskTagRecord,
} from '@/types/records';

export function ViewKanbanTasks() {
  return (
    <Kanban<Task>
      model="task"
      fields={[
        'id',
        'name',
        'priority',
        'user_id',
        'project_id',
        'date_deadline',
        'tag_ids',
        'progress',
        'color',
      ]}
      groupByField="stage_id"
      groupByModel="task_stage"
    />
  );
}

export function ViewKanbanProjects() {
  return (
    <Kanban<ProjectRecord>
      model="project"
      fields={[
        'id',
        'name',
        'status',
        'manager_id',
        'date_start',
        'date_end',
        'color',
      ]}
    />
  );
}

export function ViewKanbanTaskStages() {
  return (
    <Kanban<TaskStageRecord>
      model="task_stage"
      fields={['id', 'name', 'sequence', 'color', 'is_closed']}
    />
  );
}

export function ViewKanbanTaskTags() {
  return (
    <Kanban<TaskTagRecord> model="task_tag" fields={['id', 'name', 'color']} />
  );
}
