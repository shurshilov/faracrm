/**
 * Карточка лида в канбане (позиция 'after:KanbanCard' модели leads): под
 * стандартным заголовком — прогресс по воронке (Lead.progress, считается
 * от стадии на бэке), партнёр, ответственный и дата создания.
 *
 * Поля объявлены в registerExtension — так они попадают в запрос канбана
 * (см. KanbanCardBody в components/Kanban). Подключение: fara_leads/index.ts
 * (side-effect импорт) + config/models.ts (modelsConfig.leads.extensions).
 */

import { Stack, Text } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { ProgressView } from '@/components/Form/Fields/FieldProgress';
import { DateTimeCell } from '@/components/ListCells';
import { registerExtension } from '@/shared/extensions';
import type { KanbanCardExtensionProps } from '@/shared/extensions';
import type { LeadRecord } from '@/types/records';

export function KanbanCardLead({
  record,
}: KanbanCardExtensionProps<LeadRecord>) {
  const { t } = useTranslation('leads');

  return (
    <Stack gap={4} mt={6}>
      <ProgressView
        value={record.progress}
        size="sm"
        label={t('leads.progress')}
      />
      {record.partner_id && (
        <Text size="sm" c="dimmed" truncate>
          {t('leads.partner_id')}: {record.partner_id.name}
        </Text>
      )}
      {record.user_id && (
        <Text size="sm" c="dimmed" truncate>
          {t('leads.user_id')}: {record.user_id.name}
        </Text>
      )}
      <DateTimeCell value={record.create_datetime} format="date" showIcon />
    </Stack>
  );
}

registerExtension('leads', KanbanCardLead, 'after:KanbanCard', [
  'progress',
  'partner_id',
  'user_id',
  'create_datetime',
]);
