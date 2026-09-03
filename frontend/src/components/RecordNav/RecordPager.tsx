import { ActionIcon, Group, Text } from '@mantine/core';
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useRecordNav } from './useRecordNav';

/**
 * «◀ 3 из 120 ▶» в шапке формы — листание записей выборки, из которой
 * открыта форма. Без контекста (запись открыта по прямой ссылке, после
 * создания, из другой формы) не рендерится.
 */
export function RecordPager() {
  const { t } = useTranslation('common');
  const nav = useRecordNav();
  if (!nav) return null;

  return (
    <Group gap={2} wrap="nowrap">
      <ActionIcon
        variant="subtle"
        color="gray"
        size="md"
        disabled={!nav.hasPrev || nav.isFetching}
        onClick={nav.goPrev}
        title={t('recordNav.prev')}
        aria-label={t('recordNav.prev')}>
        <IconChevronLeft size={18} />
      </ActionIcon>
      <Text
        size="sm"
        c="dimmed"
        visibleFrom="xs"
        style={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
        {t('recordNav.position', { index: nav.index + 1, total: nav.total })}
      </Text>
      <ActionIcon
        variant="subtle"
        color="gray"
        size="md"
        disabled={!nav.hasNext || nav.isFetching}
        onClick={nav.goNext}
        title={t('recordNav.next')}
        aria-label={t('recordNav.next')}>
        <IconChevronRight size={18} />
      </ActionIcon>
    </Group>
  );
}
