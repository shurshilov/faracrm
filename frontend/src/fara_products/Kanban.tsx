import { Kanban } from '@/components/Kanban';
import { Product } from '@/services/api/product';
import { Category } from '@/services/api/category';
import { Uom } from '@/services/api/uoms';

export function ViewKanban() {
  return (
    <Kanban<Product>
      model="products"
      fields={['id', 'name', 'type', 'default_code']}
    />
  );
}

export function ViewKanbanCategory() {
  return (
    <Kanban<Category>
      model="category"
      fields={['id', 'name']}
    />
  );
}

export function ViewKanbanUom() {
  return (
    <Kanban<Uom>
      model="uom"
      fields={['id', 'name']}
    />
  );
}
