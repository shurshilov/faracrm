import { Gantt } from '@/components/Gantt';
import type { TaskRecord as Task, ProjectRecord } from '@/types/records';

export function ViewGanttTasks() {
  return (
    <Gantt<Task>
      model="task"
      fields={[
        'id',
        'name',
        'date_start',
        'date_end',
        'user_id',
        'project_id',
        'priority',
        'progress',
        'color',
        'stage_id',
      ]}
      startField="date_start"
      endField="date_end"
      labelField="name"
      colorField="color"
      defaultColor="#1c7ed6"
      defaultScale="day"
      sort="date_start"
      order="asc"
    />
  );
}

export function ViewGanttProjects() {
  return (
    <Gantt<ProjectRecord>
      model="project"
      fields={[
        'id',
        'name',
        'date_start',
        'date_end',
        'manager_id',
        'status',
        'color',
      ]}
      startField="date_start"
      endField="date_end"
      labelField="name"
      colorField="color"
      defaultColor="#1c7ed6"
      defaultScale="week"
      sort="date_start"
      order="asc"
    />
  );
}
