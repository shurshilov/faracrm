import { Kanban } from '@/components/Kanban';
import type { LanguageRecord } from '@/types/records';

export function ViewKanbanLanguage() {
  return (
    <Kanban<LanguageRecord>
      model="language"
      fields={['id', 'code', 'name', 'flag']}
    />
  );
}

export default ViewKanbanLanguage;
