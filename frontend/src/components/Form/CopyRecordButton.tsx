/**
 * «Копировать» в тулбаре формы: POST /auto/{model}/{id}/copy → переход в
 * дубликат. Что именно копируется, решает бэк (copy_record автокруда по
 * Field.copy: позиции заказа — да, аудит, уникальные и вычисляемые — нет).
 *
 * Тулбар не рендерит actions в режиме создания, поэтому id из маршрута
 * здесь всегда есть; модель — из контекста формы. Подключение:
 * <Form actions={<CopyRecordButton />}> (лид, заказ, партнёр).
 */

import { useContext } from 'react';
import { Button } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconCopy } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { useCopyMutation } from '@/services/api/crudApi';
import { FormFieldsContext } from './FormContext';

export function CopyRecordButton() {
  const { t } = useTranslation('common');
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { model } = useContext(FormFieldsContext);
  const [copyRecord, { isLoading }] = useCopyMutation();

  const handleClick = async () => {
    try {
      const { id: newId } = await copyRecord({
        model,
        id: Number(id),
      }).unwrap();
      navigate(`/${model}/${newId}`);
    } catch {
      notifications.show({
        color: 'red',
        message: t('copyFailed', 'Не удалось скопировать'),
      });
    }
  };

  return (
    <Button
      variant="light"
      leftSection={<IconCopy size={16} />}
      onClick={handleClick}
      loading={isLoading}>
      {t('copy', 'Копировать')}
    </Button>
  );
}
