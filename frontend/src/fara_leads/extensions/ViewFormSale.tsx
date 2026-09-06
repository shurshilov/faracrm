/**
 * Расширение формы Sale из модуля leads: блок «Исходный лид».
 *
 * Backend-сторона — SaleLeadMixin (backend/base/crm/leads/models/sale_ext.py),
 * @extend(Sale) добавляет FK lead_id в sales. Здесь по значению lead_id
 * рисуем ссылку на лид и сворачиваемые «Данные из лида» (SaleLeadBlock).
 *
 * Позиция — перед контентом таба «Позиции заказа»: он открыт по умолчанию,
 * менеджер продаж видит источник сразу. Без lead_id блок не рендерится
 * (продажа создана не из лида).
 *
 * Подключение: fara_leads/index.ts (side-effect импорт) и
 * config/models.ts (modelsConfig.sales.extensions), как у fara_contract.
 */

import { useFormContext } from '@/components/Form/FormContext';
import { registerExtension } from '@/shared/extensions';
import type { RelationRecord } from '@/types/records';
import { SaleLeadBlock } from '../SaleLeadBlock';

export function ViewFormSaleLead() {
  const form = useFormContext();
  const lead = form.getValues().lead_id as RelationRecord | null | undefined;
  if (!lead?.id) return null;
  return <SaleLeadBlock leadId={lead.id} leadName={lead.name} />;
}

// Список fields обязателен: иначе lead_id не попадёт в запрос /sales/{id}
// (см. комментарий в fara_contract/extensions/ViewFormSale.tsx).
registerExtension('sales', ViewFormSaleLead, 'before:FormTab:lines', [
  'lead_id',
]);
