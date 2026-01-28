import { Gantt } from '@/components/Gantt';
import { SchemaSession } from '@/services/api/sessions';

export function ViewGanttSessions() {
  return (
    <Gantt<SchemaSession>
      model="sessions"
      fields={['id', 'user_id', 'active', 'create_datetime', 'ttl']}
      dateField="create_datetime"
      durationField="ttl"
      labelField="user_id"
      defaultColor="#3498db"
      defaultScale="4hours"
      sort="create_datetime"
      order="desc"
    />
  );
}
