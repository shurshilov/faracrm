import { Kanban } from '@/components/Kanban';
import type { SaleRecord, SaleStageRecord, TaxRecord } from '@/types/records';

export function ViewKanbanSales() {
  return (
    <Kanban<SaleRecord>
      model="sales"
      fields={['id', 'name', 'partner_id', 'user_id', 'date_order']}
      groupByField="stage_id"
      groupByModel="sale_stage"
    />
  );
}

export function ViewKanbanSaleStage() {
  return (
    <Kanban<SaleStageRecord>
      model="sale_stage"
      fields={['id', 'name', 'sequence', 'color']}
    />
  );
}

export function ViewKanbanTax() {
  return <Kanban<TaxRecord> model="tax" fields={['id', 'name']} />;
}
