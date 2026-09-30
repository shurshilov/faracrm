/**
 * «Копировать» в тулбаре формы: подтверждение → POST /auto/{model}/{id}/copy
 * → переход в дубликат. Что именно копируется, решает бэк (copy_record
 * автокруда по Field.copy: позиции заказа — да, аудит, уникальные и
 * вычисляемые — нет).
 *
 * Тулбар не рендерит actions в режиме создания, поэтому id из маршрута
 * здесь всегда есть; модель — из контекста формы. Подключение:
 * <Form actions={<CopyRecordButton />}> (лид, заказ, партнёр).
 */

import { useContext } from 'react';
import { ActionIcon, Button, Group, Modal, Text } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
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
  // Копия создаётся сразу, отменить её нельзя — спрашиваем перед запросом
  const [opened, { open, close }] = useDisclosure(false);

  const handleCopy = async () => {
    try {
      const { id: newId } = await copyRecord({
        model,
        id: Number(id),
      }).unwrap();
      close();
      navigate(`/${model}/${newId}`);
    } catch {
      notifications.show({
        color: 'red',
        message: t('copyFailed', 'Не удалось скопировать'),
      });
    }
  };

  // Иконка как у соседей по тулбару (печать, панели, вид): subtle md,
  // подпись — во всплывающей подсказке
  const label = t('copy', 'Копировать');
  return (
    <>
      <ActionIcon
        variant="subtle"
        color="blue"
        size="md"
        title={label}
        aria-label={label}
        onClick={open}>
        <IconCopy size={18} />
      </ActionIcon>

      <Modal
        opened={opened}
        onClose={close}
        title={t('copyConfirmTitle', 'Копировать запись?')}
        size="sm"
        centered>
        <Text size="sm">
          {t(
            'copyConfirmText',
            'Будет создана копия этой записи, и вы перейдёте в неё.',
          )}
        </Text>
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={close} disabled={isLoading}>
            {t('cancel')}
          </Button>
          <Button
            leftSection={<IconCopy size={16} />}
            onClick={handleCopy}
            loading={isLoading}>
            {label}
          </Button>
        </Group>
      </Modal>
    </>
  );
}
