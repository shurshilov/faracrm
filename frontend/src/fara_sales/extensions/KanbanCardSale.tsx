/**
 * Карточка заказа в канбане (позиция 'after:KanbanCard' модели sales): под
 * стандартным заголовком — прогресс по воронке (Sale.progress, считается
 * от стадии на бэке), клиент, менеджер и дата заказа.
 *
 * Поля объявлены в registerExtension — так они попадают в запрос канбана
 * (см. KanbanCardBody в components/Kanban). Подключение: fara_sales/index.ts
 * (side-effect импорт) + config/models.ts (modelsConfig.sales.extensions).
 */

import { Stack, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { ProgressView } from '@/components/Form/Fields/FieldProgress';
import { DateTimeCell } from '@/components/ListCells';
import { registerExtension } from '@/shared/extensions';
import type { KanbanCardExtensionProps } from '@/shared/extensions';
import type { SaleRecord } from '@/types/records';

export function KanbanCardSale({
  record,
}: KanbanCardExtensionProps<SaleRecord>) {
  const { t } = useTranslation('sales');

  return (
    <Stack gap={4} mt={6}>
      <ProgressView
        value={record.progress}
        size="sm"
        label={t('sales.progress')}
      />
      {record.partner_id && (
        <Text size="sm" c="dimmed" truncate>
          {t('sales.partner_id')}: {record.partner_id.name}
        </Text>
      )}
      {record.user_id && (
        <Text size="sm" c="dimmed" truncate>
          {t('sales.user_id')}: {record.user_id.name}
        </Text>
      )}
      <DateTimeCell value={record.date_order} format="date" showIcon />
    </Stack>
  );
}

registerExtension('sales', KanbanCardSale, 'after:KanbanCard', [
  'progress',
  'partner_id',
  'user_id',
  'date_order',
]);
