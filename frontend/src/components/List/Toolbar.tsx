import { useState, useRef } from 'react';
import { Flex, Group, Loader, Text, ThemeIcon, Button } from '@mantine/core';
import { IconCheck, IconX, IconArrowBackUp } from '@tabler/icons-react';
import { Actions } from './Actions';
import { NewButton } from './NewButton';
import { FaraRecord, GetListField } from '@/services/api/crudTypes';

type DeleteStatus = 'idle' | 'loading' | 'success' | 'error';

export const Toolbar = <RecordType extends FaraRecord>({
  model,
  selectedRecords,
  fields,
  massActions,
  extraActions,
  onClearSelection,
  onExportSelected,
  columnsControl,
}: {
  model: string;
  selectedRecords: RecordType[];
  fields?: GetListField[];
  massActions?: boolean;
  extraActions?: React.ReactNode;
  onClearSelection?: () => void;
  /** Экспорт выбранных строк в Excel (пункт меню Actions). */
  onExportSelected?: () => void;
  /** Меню «⋮» списка (колонки, Excel); рядом с «Создать», если нет слота. */
  columnsControl?: React.ReactNode;
}) => {
  const [deleteStatus, setDeleteStatus] = useState<DeleteStatus>('idle');
  const [deletedCount, setDeletedCount] = useState(0);
  const undoRef = useRef<(() => void) | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleDeleteStart = () => {
    setDeleteStatus('loading');
  };

  const handleDeleteSuccess = (count: number, undo?: () => void) => {
    setDeletedCount(count);
    setDeleteStatus('success');
    undoRef.current = undo || null;
    
    // Очищаем предыдущий таймаут
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    // Скрываем через 5 секунд (даём время на undo)
    timeoutRef.current = setTimeout(() => {
      setDeleteStatus('idle');
      undoRef.current = null;
    }, 5000);
  };

  const handleDeleteError = () => {
    setDeleteStatus('error');
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => setDeleteStatus('idle'), 3000);
  };

  const handleUndo = () => {
    if (undoRef.current) {
      undoRef.current();
      undoRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setDeleteStatus('idle');
  };

  return (
    <>
      <Flex
        mih={50}
        gap="xs"
        justify="space-between"
        align="center"
        direction="row"
        wrap="nowrap">
        <Flex gap="xs" align="center">
          <NewButton />
          {columnsControl}
          {extraActions}
        </Flex>
        <Group gap="xs">
          {deleteStatus === 'loading' && (
            <Group gap={4}>
              <Loader size="xs" />
              <Text size="sm" c="dimmed">Удаление...</Text>
            </Group>
          )}
          {deleteStatus === 'success' && (
            <Group gap={8}>
              <Group gap={4}>
                <ThemeIcon size="xs" color="green" variant="light">
                  <IconCheck size={12} />
                </ThemeIcon>
                <Text size="sm" c="green">Удалено {deletedCount}</Text>
              </Group>
              {undoRef.current && (
                <Button
                  size="xs"
                  variant="subtle"
                  color="gray"
                  leftSection={<IconArrowBackUp size={14} />}
                  onClick={handleUndo}
                >
                  Отменить
                </Button>
              )}
            </Group>
          )}
          {deleteStatus === 'error' && (
            <Group gap={4}>
              <ThemeIcon size="xs" color="red" variant="light">
                <IconX size={12} />
              </ThemeIcon>
              <Text size="sm" c="red">Ошибка</Text>
            </Group>
          )}
          {!!selectedRecords.length && (
            <Actions
              resource={model}
              selectedIds={selectedRecords}
              fields={fields}
              massActions={massActions}
              onClearSelection={onClearSelection}
              onExport={onExportSelected}
              onDeleteStart={handleDeleteStart}
              onDeleteSuccess={handleDeleteSuccess}
              onDeleteError={handleDeleteError}
            />
          )}
        </Group>
      </Flex>
    </>
  );
};
