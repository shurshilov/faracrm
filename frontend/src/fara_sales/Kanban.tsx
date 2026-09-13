import { Kanban } from '@/components/Kanban';
import type { SaleRecord, SaleStageRecord, TaxRecord } from '@/types/records';

export function ViewKanbanSales() {
  // Содержимое карточки (прогресс, клиент, менеджер, дата заказа) —
  // расширение extensions/KanbanCardSale; здесь только заголовок и стадии.
  return (
    <Kanban<SaleRecord>
      model="sales"
      groupByField="stage_id"
      groupByModel="sale_stage"
      groupByFilter={[['active', '=', true]]}
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
