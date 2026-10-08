/**
 * Выбор модели для нового поля «Ссылка на запись»: тип поля не меняется
 * после создания, поэтому модель спрашиваем до него. Список — реестр
 * моделей (таблица = имя в адресе формы).
 */
import { useState } from 'react';
import { Button, Group, Modal, Select, Stack } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useSearchQuery } from '@/services/api/crudApi';

interface RelationPickModalProps {
  opened: boolean;
  onClose: () => void;
  onPick: (table: string) => void;
}

export function RelationPickModal({
  opened,
  onClose,
  onPick,
}: RelationPickModalProps) {
  const { t } = useTranslation('studio');
  const [value, setValue] = useState<string | null>(null);
  const { data } = useSearchQuery(
    {
      model: 'models',
      fields: ['id', 'name', 'table_name'],
      limit: 200,
      sort: 'name',
      order: 'asc',
    },
    { skip: !opened },
  );

  return (
    <Modal opened={opened} onClose={onClose} title={t('relationPick')}>
      <Stack gap="md">
        <Select
          label={t('relationModel')}
          searchable
          data={(data?.data ?? []).map(row => ({
            value: String(row.table_name),
            label: String(row.name),
          }))}
          value={value}
          onChange={setValue}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('cancel')}
          </Button>
          <Button disabled={!value} onClick={() => value && onPick(value)}>
            {t('add')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
