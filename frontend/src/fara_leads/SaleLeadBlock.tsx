/**
 * Блок «Исходный лид» на форме продажи: системная ссылка «Имя лида [ID]»
 * на карточку лида, из которого создана продажа (Sale.lead_id).
 */

import { Anchor, Group, Paper, Text } from '@mantine/core';
import { IconTargetArrow } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

export function SaleLeadBlock({
  leadId,
  leadName,
}: {
  leadId: number;
  leadName?: string;
}) {
  const { t } = useTranslation('leads');
  const navigate = useNavigate();

  return (
    <Paper withBorder p="sm" radius="md" mb="md">
      <Group gap="xs">
        <IconTargetArrow size={18} />
        <Text size="sm" c="dimmed">
          {t('sale_link.source_lead')}:
        </Text>
        <Anchor size="sm" onClick={() => navigate(`/leads/${leadId}`)}>
          {leadName || t('sale_link.lead')} [{leadId}]
        </Anchor>
      </Group>
    </Paper>
  );
}
