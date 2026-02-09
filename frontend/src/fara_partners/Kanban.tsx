import { Kanban } from '@/components/Kanban';
import type { PartnerRecord } from '@/types/records';

export function ViewKanbanPartners() {
  return <Kanban<PartnerRecord> model="partners" fields={['id', 'name']} />;
}
