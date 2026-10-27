/**
 * ExportModal — выгрузка записей списка в Excel.
 *
 * Поля: по умолчанию видимые колонки списка (в их порядке), любое поле
 * модели можно добавить или снять; в окне поля подписаны как в меню колонок
 * (fieldLabel + техническое имя), заголовки файла — имена полей. Что
 * выгружать, решает вызывающий: выбранные записи (ids) или вся текущая
 * выборка (query — фильтр и сортировка списка, как ушли в /search).
 */
import { useEffect, useMemo, useState } from 'react';
import {
  Badge,
  Button,
  Checkbox,
  Divider,
  Group,
  Modal,
  ScrollArea,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconSearch } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useGetFieldsQuery } from '@/services/api/crudApi';
import { fieldLabel } from '@/components/Form/fieldLabel';
import { ExcelQuery, useExcelExport } from './api';

// Байты в ячейку не положить (вложения выгружаются как id).
const SKIP_TYPES = new Set(['Binary']);

interface ExportModalProps {
  opened: boolean;
  onClose: () => void;
  model: string;
  /** Видимые колонки списка — стартовый набор. */
  columns: string[];
  /** Выборка списка (фильтр, сортировка) — когда ids не заданы. */
  query: ExcelQuery;
  /** Выбранные записи; без них выгружается вся выборка. */
  ids?: number[];
  /** Размер выборки — для подписи. */
  total?: number;
}

export function ExportModal({
  opened,
  onClose,
  model,
  columns,
  query,
  ids,
  total,
}: ExportModalProps) {
  const { t } = useTranslation(['excel', 'common']);
  const { data: allFields } = useGetFieldsQuery(model, { skip: !opened });
  const exportExcel = useExcelExport();
  const [selected, setSelected] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);

  // При каждом открытии — колонки списка.
  useEffect(() => {
    if (opened) {
      setSelected(columns);
      setSearch('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened]);

  const fieldByName = useMemo(
    () =>
      new Map(
        (allFields ?? [])
          .filter(field => !SKIP_TYPES.has(field.type))
          .map(field => [field.name, field]),
      ),
    [allFields],
  );

  // Колонки вью могут содержать то, что в файл не выгружается (или поля
  // ещё не загружены) — наружу уходят только известные выгружаемые.
  const chosen = selected.filter(name => fieldByName.has(name));
  const rest = Array.from(fieldByName.keys()).filter(
    name => !selected.includes(name),
  );
  // Подпись поля — как в меню колонок (перевод модуля / Field.string).
  const labelOf = (name: string) => {
    const info = fieldByName.get(name);
    return info ? fieldLabel(t, model, info) : name;
  };
  const q = search.trim().toLowerCase();
  const matches = (name: string) =>
    !q ||
    name.toLowerCase().includes(q) ||
    labelOf(name).toLowerCase().includes(q);

  const toggle = (name: string, checked: boolean) =>
    setSelected(prev =>
      checked ? [...prev, name] : prev.filter(item => item !== name),
    );

  // Подпись, техническое имя (если отличается) и тип поля.
  const fieldTitle = (name: string) => {
    const label = labelOf(name);
    return (
      <Group gap={6} wrap="nowrap">
        <Text size="xs">{label}</Text>
        {label !== name && (
          <Text size="xs" c="dimmed" fs="italic">
            {name}
          </Text>
        )}
        <Badge
          size="xs"
          variant="light"
          color="gray"
          style={{ textTransform: 'none' }}>
          {fieldByName.get(name)?.type}
        </Badge>
      </Group>
    );
  };

  const handleExport = async () => {
    setLoading(true);
    try {
      await exportExcel(model, { ...query, ids, fields: chosen });
      onClose();
    } catch (error) {
      notifications.show({
        color: 'red',
        message: error instanceof Error ? error.message : t('exportFailed'),
      });
    } finally {
      setLoading(false);
    }
  };

  const scope = ids
    ? t('scopeSelected', { count: ids.length })
    : total !== undefined
      ? t('scopeAll', { count: total })
      : t('scopeAllUnknown');

  return (
    <Modal opened={opened} onClose={onClose} title={t('exportTitle')} centered>
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {scope}
        </Text>

        <TextInput
          size="xs"
          placeholder={t('searchField')}
          leftSection={<IconSearch size={14} />}
          value={search}
          onChange={event => setSearch(event.currentTarget.value)}
        />

        <ScrollArea.Autosize mah={360} type="auto" offsetScrollbars="y">
          <Stack gap={4}>
            {chosen.filter(matches).map(name => (
              <Checkbox
                key={name}
                size="xs"
                checked
                onChange={event => toggle(name, event.currentTarget.checked)}
                label={fieldTitle(name)}
              />
            ))}
            {rest.some(matches) && (
              <Divider my={4} label={t('otherFields')} labelPosition="center" />
            )}
            {rest.filter(matches).map(name => (
              <Checkbox
                key={name}
                size="xs"
                checked={false}
                onChange={event => toggle(name, event.currentTarget.checked)}
                label={fieldTitle(name)}
              />
            ))}
          </Stack>
        </ScrollArea.Autosize>

        <Group justify="flex-end" gap="xs">
          <Button variant="default" onClick={onClose}>
            {t('common:cancel')}
          </Button>
          <Button
            onClick={handleExport}
            loading={loading}
            disabled={chosen.length === 0}>
            {t('download')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
