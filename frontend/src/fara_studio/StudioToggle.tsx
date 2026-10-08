/**
 * Переключатель режима студии в шапке (registerHeaderAction) — как иконка
 * Studio в Odoo. Виден, когда открыта форма модели, модуль studio
 * установлен и пользователь — администратор настроек.
 */
import { ActionIcon, Tooltip } from '@mantine/core';
import { IconSparkles } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useAppInstalled } from '@/hooks/useInstalledApps';
import { useIsSystemAdmin } from '@/hooks/useIsSystemAdmin';
import { setStudioOn, useStudioMode } from './studioMode';

export function StudioToggle() {
  const { t } = useTranslation('studio');
  const installed = useAppInstalled('studio');
  const isSystemAdmin = useIsSystemAdmin();
  const { on, model } = useStudioMode();

  if (!model || !isSystemAdmin || !installed) return null;

  return (
    <Tooltip label={t('toggle')}>
      <ActionIcon
        variant={on ? 'filled' : 'subtle'}
        color={on ? 'violet' : 'gray'}
        size="md"
        aria-label={t('toggle')}
        onClick={() => setStudioOn(!on)}>
        <IconSparkles size={18} />
      </ActionIcon>
    </Tooltip>
  );
}
