import { ActionIcon, Tooltip } from '@mantine/core';
import { IconArrowLeft } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useBackToList } from './useRecordNav';

/** «К списку» в шапке формы: назад к виду модели с его фильтрами/страницей. */
export function BackToListButton({ model }: { model: string }) {
  const { t } = useTranslation('common');
  const backToList = useBackToList(model);

  return (
    <Tooltip label={t('recordNav.backToList')} position="bottom" withArrow>
      <ActionIcon
        variant="subtle"
        color="gray"
        size="md"
        onClick={backToList}
        aria-label={t('recordNav.backToList')}>
        <IconArrowLeft size={18} />
      </ActionIcon>
    </Tooltip>
  );
}
