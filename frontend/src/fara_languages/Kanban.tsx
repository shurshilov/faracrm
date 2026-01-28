import { Kanban } from '@/components/Kanban';
import { FaraRecord } from '@/services/api/crudTypes';

export function ViewKanbanLanguage() {
  return (
    <Kanban<FaraRecord>
      model="language"
      fields={['id', 'code', 'name', 'flag']}
    />
  );
}

export default ViewKanbanLanguage;
