import { Kanban } from '@/components/Kanban';
import { Task, ProjectRecord } from './List';
import { FaraRecord } from '@/services/api/crudTypes';

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
    <Kanban<FaraRecord>
      model="task_stage"
      fields={['id', 'name', 'sequence', 'color', 'is_closed']}
    />
  );
}

export function ViewKanbanTaskTags() {
  return (
    <Kanban<FaraRecord>
      model="task_tag"
      fields={['id', 'name', 'color']}
    />
  );
}
