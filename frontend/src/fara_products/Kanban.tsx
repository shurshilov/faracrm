import { Kanban } from '@/components/Kanban';
import type { ProductRecord as Product } from '@/types/records';
import type { CategoryRecord as Category } from '@/types/records';
import type { UomRecord as Uom } from '@/types/records';

export function ViewKanban() {
  return (
    <Kanban<Product>
      model="products"
      fields={['id', 'name', 'type', 'default_code']}
    />
  );
}

export function ViewKanbanCategory() {
  return <Kanban<Category> model="category" fields={['id', 'name']} />;
}

export function ViewKanbanUom() {
  return <Kanban<Uom> model="uom" fields={['id', 'name']} />;
}
