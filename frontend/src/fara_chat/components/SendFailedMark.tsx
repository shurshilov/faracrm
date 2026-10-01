import { ThemeIcon, Tooltip } from '@mantine/core';
import { IconExclamationMark } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

/**
 * Пометка у времени сообщения: во внешний канал оно не ушло и осталось
 * только в ленте (message.send_failed). Красный кружок — виден и на синем
 * своём бабле, и на фоне чата.
 */
export function SendFailedMark() {
  const { t } = useTranslation('chat');

  return (
    <Tooltip label={t('sendFailed')} position="top" withArrow>
      <ThemeIcon color="red" size={16} radius="xl" aria-label={t('sendFailed')}>
        <IconExclamationMark size={12} />
      </ThemeIcon>
    </Tooltip>
  );
}
