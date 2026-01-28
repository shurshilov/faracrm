import { Kanban } from '@/components/Kanban';
import { FaraRecord } from '@/services/api/crudTypes';

export function ViewKanbanCompany() {
  return (
    <Kanban<FaraRecord>
      model="company"
      fields={['id', 'name', 'active']}
    />
  );
}
