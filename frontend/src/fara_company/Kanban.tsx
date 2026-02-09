import { Kanban } from '@/components/Kanban';
import type { CompanyRecord } from '@/types/records';

export function ViewKanbanCompany() {
  return (
    <Kanban<CompanyRecord> model="company" fields={['id', 'name', 'active']} />
  );
}
