import { Kanban } from '@/components/Kanban';
import { Partner } from '@/services/api/partner';

export function ViewKanbanPartners() {
  return <Kanban<Partner> model="partners" fields={['id', 'name']} />;
}
