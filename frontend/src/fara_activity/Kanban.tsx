import { Kanban } from '@/components/Kanban/Kanban';
import { ViewKanbanProps } from '@/route/type';

export function ViewKanbanActivity(props: ViewKanbanProps) {
  return (
    <Kanban
      model="activity"
      {...props}
      fields={[
        'id',
        'summary',
        'activity_type_id',
        'user_id',
        'date_deadline',
        'state',
        'done',
      ]}
    />
  );
}

export function ViewKanbanActivityType(props: ViewKanbanProps) {
  return (
    <Kanban
      model="activity_type"
      {...props}
      fields={['id', 'name', 'icon', 'color', 'default_days']}
    />
  );
}
