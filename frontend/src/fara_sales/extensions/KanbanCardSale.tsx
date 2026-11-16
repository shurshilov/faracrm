/**
 * Карточка заказа в канбане (позиция 'after:KanbanCard' модели sales): под
 * стандартным заголовком — прогресс по воронке (Sale.progress, считается
 * от стадии на бэке), клиент, менеджер и дата заказа.
 *
 * Клиент подписан иконкой раздела «Партнёры»: слово «Партнёр» в строке не
 * нужно — иконка компактнее и оставляет место имени; подпись возвращает
 * подсказка при наведении на иконку.
 *
 * Поля объявлены в registerExtension — так они попадают в запрос канбана
 * (см. KanbanCardBody в components/Kanban). Подключение: fara_sales/index.ts
 * (side-effect импорт) + config/models.ts (modelsConfig.sales.extensions).
 */

import { Group, Stack, Tooltip } from '@mantine/core';
import { IconUsers } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { ProgressView } from '@/components/Form/Fields/FieldProgress';
import { DateTimeCell } from '@/components/ListCells';
import { TruncatedText } from '@/components/TruncatedText';
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
        <Group gap={6} wrap="nowrap">
          <Tooltip label={t('sales.partner_id')} withArrow>
            <IconUsers size={14} color="var(--mantine-color-dimmed)" />
          </Tooltip>
          <TruncatedText
            size="sm"
            c="dimmed"
            text={record.partner_id.name || `#${record.partner_id.id}`}
            style={{ flex: 1, minWidth: 0 }}
          />
        </Group>
      )}
      {record.user_id && (
        <TruncatedText
          size="sm"
          c="dimmed"
          text={`${t('sales.user_id')}: ${record.user_id.name}`}
        />
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
