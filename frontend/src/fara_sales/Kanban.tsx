import { Kanban } from '@/components/Kanban';
import { Sale } from '@/services/api/sale';
import { FaraRecord } from '@/services/api/crudTypes';

export function ViewKanbanSales() {
  return (
    <Kanban<Sale>
      model="sale"
      fields={['id', 'name', 'parent_id', 'user_id', 'date_order']}
      groupByField="stage_id"
      groupByModel="sale_stage"
    />
  );
}

export function ViewKanbanSaleStage() {
  return (
    <Kanban<FaraRecord>
      model="sale_stage"
      fields={['id', 'name', 'sequence', 'color']}
    />
  );
}

export function ViewKanbanTax() {
  return (
    <Kanban<FaraRecord>
      model="tax"
      fields={['id', 'name']}
    />
  );
}
