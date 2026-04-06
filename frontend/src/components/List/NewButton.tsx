import { Button } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

export function NewButton() {
  const navigate = useNavigate();
  const { t } = useTranslation('common');
  return (
    <Button variant="filled" onClick={() => navigate('create')}>
      {t('create')}
    </Button>
  );
}
