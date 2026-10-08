/**
 * StudioPanel — боковая панель режима студии в колонке приложения справа
 * (LayoutAside): форма сужается на её ширину, ни разметка, ни зона
 * «сбоку», ни шапка под панелью не прячутся. Как панель Odoo Studio:
 *   «Добавить»     — новые поля по типам и существующие поля модели,
 *                    перетаскиваются в клетку зоны «Дополнительно»;
 *   «Свойства»     — выбранное поле: подпись и варианты (у полей
 *                    студии), техническое имя, тип, размер в клетках,
 *                    обязательность, «Убрать с формы», «Удалить поле»;
 *   «Поля формы»   — обязательность полей разметки (саму разметку не
 *                    трогаем). Обязательное по модели — включено всегда.
 */
import { useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Badge,
  Box,
  Button,
  Checkbox,
  CloseButton,
  Group,
  NumberInput,
  Paper,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import {
  IconAlignLeft,
  IconCalendar,
  IconClock,
  IconDecimal,
  IconHash,
  IconLetterCase,
  IconLink,
  IconList,
  IconSearch,
  IconSparkles,
  IconSquareCheck,
} from '@tabler/icons-react';
import { useDraggable } from '@dnd-kit/core';
import { FormFieldsContext } from '@/components/Form/FormContext';
import type { ExtraCell } from './zone/zoneGrid';
import type { FieldInfoResponse } from '@/services/api/crudApi';
import { LayoutAside } from '@/shared/extensions/layoutAside';
import { STUDIO_FIELD_TYPES, StudioFieldDTO, StudioFieldType } from './api';
import type { DragData } from './dnd';
import type { StudioEditor } from './useStudioEditor';

const PANEL_WIDTH = 340;

/** Поля-таблицы в зону не идут: без разметки колонок форма их не нарисует. */
const TABLE_TYPES = new Set([
  'One2many',
  'Many2many',
  'PolymorphicOne2many',
  'One2one',
]);

const TYPE_ICONS: Record<StudioFieldType, typeof IconLetterCase> = {
  char: IconLetterCase,
  text: IconAlignLeft,
  integer: IconHash,
  float: IconDecimal,
  boolean: IconSquareCheck,
  date: IconCalendar,
  datetime: IconClock,
  selection: IconList,
  many2one: IconLink,
};

/** Варианты из текста: по одному в строке, «значение=подпись» или просто
 *  «подпись» (тогда значение — она же). */
function parseOptions(text: string): [string, string][] {
  return text
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => {
      const eq = line.indexOf('=');
      if (eq < 0) return [line, line];
      return [line.slice(0, eq).trim(), line.slice(eq + 1).trim()];
    });
}

function optionsText(options: [string, string][] | null): string {
  return (options ?? [])
    .map(([value, label]) => (value === label ? value : `${value}=${label}`))
    .join('\n');
}

function typeBadge(type: string) {
  return (
    <Badge
      size="xs"
      variant="light"
      color="gray"
      style={{ textTransform: 'none' }}>
      {type}
    </Badge>
  );
}

/** Новое поле в палитре — перетаскивается в зону. */
function PaletteItem({
  type,
  label,
}: {
  type: StudioFieldType;
  label: string;
}) {
  // Сам элемент остаётся на месте: перетаскиваемую копию рисует
  // DragOverlay (StudioExtraFields) — поверх всего, панель её не режет.
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `new:${type}`,
    data: { kind: 'new', type } satisfies DragData,
  });
  const Icon = TYPE_ICONS[type];
  return (
    <Paper
      ref={setNodeRef}
      withBorder
      p={6}
      radius="md"
      style={{ cursor: 'grab', opacity: isDragging ? 0.4 : 1 }}
      {...attributes}
      {...listeners}>
      <Group gap={6} wrap="nowrap">
        <Icon size={14} />
        <Text size="xs" truncate>
          {label}
        </Text>
      </Group>
    </Paper>
  );
}

/** Существующее поле модели — перетаскивается в зону. */
function ExistingItem({
  name,
  label,
  type,
}: {
  name: string;
  label: string;
  type: string;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `existing:${name}`,
    data: { kind: 'existing', name } satisfies DragData,
  });
  return (
    <Paper
      ref={setNodeRef}
      withBorder
      p={6}
      radius="md"
      style={{ cursor: 'grab', opacity: isDragging ? 0.4 : 1 }}
      {...attributes}
      {...listeners}>
      <Group gap={6} wrap="nowrap" justify="space-between">
        <Text size="xs" truncate>
          {label}
        </Text>
        {typeBadge(type)}
      </Group>
    </Paper>
  );
}

/** Ширина и высота поля в клетках сетки зоны; не влезает — не меняется. */
function CellSize({ cell, editor }: { cell: ExtraCell; editor: StudioEditor }) {
  const { t } = useTranslation('studio');
  const { columns, rows } = editor.grid;
  return (
    <Group grow gap="xs">
      <NumberInput
        label={t('width')}
        min={1}
        max={columns - cell.x + 1}
        value={cell.w}
        onChange={value => {
          if (typeof value === 'number' && value >= 1) {
            editor.resize(cell.name, value, cell.h);
          }
        }}
      />
      <NumberInput
        label={t('height')}
        min={1}
        max={rows ? rows - cell.y + 1 : undefined}
        value={cell.h}
        onChange={value => {
          if (typeof value === 'number' && value >= 1) {
            editor.resize(cell.name, cell.w, value);
          }
        }}
      />
    </Group>
  );
}

interface FieldPropertiesProps {
  name: string;
  info: FieldInfoResponse | undefined;
  row: StudioFieldDTO | undefined;
  editor: StudioEditor;
}

/** Свойства выбранного поля; ключ по имени поля — состояние своё. */
function FieldProperties({ name, info, row, editor }: FieldPropertiesProps) {
  const { t } = useTranslation('studio');
  const [labelDraft, setLabelDraft] = useState(
    row?.label ?? editor.label(name),
  );
  const [optionsDraft, setOptionsDraft] = useState(
    optionsText(row?.options ?? null),
  );
  const [confirm, setConfirm] = useState(false);
  const fixed = !!info?.required;
  const cell = editor.cells.find(item => item.name === name);

  const saveLabel = () => {
    const next = labelDraft.trim();
    if (row && next && next !== row.label) editor.setLabel(row.id, next);
  };
  const saveOptions = () => {
    const pairs = parseOptions(optionsDraft);
    if (row && pairs.length && optionsDraft !== optionsText(row.options)) {
      editor.setOptions(row.id, pairs);
    }
  };

  return (
    <Stack gap="sm">
      <TextInput
        label={t('label')}
        value={labelDraft}
        readOnly={!row}
        onChange={e => setLabelDraft(e.currentTarget.value)}
        onBlur={saveLabel}
      />
      <TextInput label={t('name')} value={name} readOnly />
      <Group gap="xs">
        <Text size="sm">{t('type')}</Text>
        {info && typeBadge(info.type)}
      </Group>
      {row?.field_type === 'selection' && (
        <Textarea
          label={t('options')}
          description={t('optionsHint')}
          autosize
          minRows={3}
          value={optionsDraft}
          onChange={e => setOptionsDraft(e.currentTarget.value)}
          onBlur={saveOptions}
        />
      )}
      {cell && <CellSize cell={cell} editor={editor} />}
      <Checkbox
        label={t('required')}
        checked={fixed || editor.required.includes(name)}
        disabled={fixed}
        onChange={e => editor.setRequired(name, e.currentTarget.checked)}
      />
      {cell && (
        <Button variant="default" onClick={() => editor.removeFromForm(name)}>
          {t('removeFromForm')}
        </Button>
      )}
      {row &&
        (confirm ? (
          <Stack gap="xs">
            <Text size="xs" c="red">
              {t('deleteConfirm')}
            </Text>
            <Group gap="xs">
              <Button
                size="compact-sm"
                color="red"
                onClick={() => editor.deleteField(row.id)}>
                {t('yes')}
              </Button>
              <Button
                size="compact-sm"
                variant="default"
                onClick={() => setConfirm(false)}>
                {t('no')}
              </Button>
            </Group>
          </Stack>
        ) : (
          <Button variant="subtle" color="red" onClick={() => setConfirm(true)}>
            {t('deleteField')}
          </Button>
        ))}
    </Stack>
  );
}

interface StudioPanelProps {
  editor: StudioEditor;
  /** Поля разметки и расширений формы. */
  layoutFields: string[];
  onClose: () => void;
}

export function StudioPanel({
  editor,
  layoutFields,
  onClose,
}: StudioPanelProps) {
  const { t } = useTranslation('studio');
  const { model } = useContext(FormFieldsContext);
  const [tab, setTab] = useState<string | null>('add');
  const [search, setSearch] = useState('');

  // Выбрали поле — показываем его свойства.
  useEffect(() => {
    if (editor.selected) setTab('props');
  }, [editor.selected]);

  const fieldsByName = useMemo(() => {
    const map = new Map<string, FieldInfoResponse>();
    for (const field of editor.allFields) {
      if (!TABLE_TYPES.has(field.type)) map.set(field.name, field);
    }
    return map;
  }, [editor.allFields]);

  const q = search.trim().toLowerCase();
  const existing = [...fieldsByName.keys()].filter(
    name =>
      !layoutFields.includes(name) &&
      !editor.cells.some(cell => cell.name === name) &&
      (!q ||
        name.toLowerCase().includes(q) ||
        editor.label(name).toLowerCase().includes(q)),
  );
  const inLayout = layoutFields.filter(name => fieldsByName.has(name));

  return (
    <LayoutAside width={PANEL_WIDTH}>
      <Box p="md" style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
        <Group justify="space-between" wrap="nowrap" mb="md">
          <Group gap="xs" wrap="nowrap">
            <IconSparkles size={18} />
            <Text fw={600}>{t('title')}</Text>
            <Text size="xs" c="dimmed">
              · {model} · {editor.saving ? t('saving') : t('saved')}
            </Text>
          </Group>
          <CloseButton aria-label={t('close')} onClick={onClose} />
        </Group>
        <Tabs value={tab} onChange={setTab}>
          <Tabs.List grow>
            <Tabs.Tab value="add">{t('tabs.add')}</Tabs.Tab>
            <Tabs.Tab value="props">{t('tabs.props')}</Tabs.Tab>
            <Tabs.Tab value="form">{t('tabs.form')}</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="add" pt="sm">
            <Stack gap="sm">
              <Text size="sm" fw={600}>
                {t('newFields')}
              </Text>
              <SimpleGrid cols={2} spacing="xs">
                {STUDIO_FIELD_TYPES.map(type => (
                  <PaletteItem
                    key={type}
                    type={type}
                    label={t(`types.${type}`)}
                  />
                ))}
              </SimpleGrid>
              <Text size="sm" fw={600}>
                {t('existingFields')}
              </Text>
              <TextInput
                size="xs"
                placeholder={t('searchField')}
                leftSection={<IconSearch size={14} />}
                value={search}
                onChange={e => setSearch(e.currentTarget.value)}
              />
              <Stack gap={4}>
                {existing.map(name => (
                  <ExistingItem
                    key={name}
                    name={name}
                    label={editor.label(name)}
                    type={fieldsByName.get(name)!.type}
                  />
                ))}
                {existing.length === 0 && (
                  <Text size="xs" c="dimmed" ta="center" py="sm">
                    {t('noFields')}
                  </Text>
                )}
              </Stack>
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="props" pt="sm">
            {editor.selected ? (
              <FieldProperties
                key={editor.selected}
                name={editor.selected}
                info={fieldsByName.get(editor.selected)}
                row={editor.studioRows.find(r => r.name === editor.selected)}
                editor={editor}
              />
            ) : (
              <Text size="sm" c="dimmed">
                {t('nothingSelected')}
              </Text>
            )}
          </Tabs.Panel>

          <Tabs.Panel value="form" pt="sm">
            <Stack gap={6}>
              {inLayout.map(name => {
                const info = fieldsByName.get(name)!;
                const fixed = !!info.required;
                return (
                  <Checkbox
                    key={name}
                    size="sm"
                    label={
                      <Group gap={6} wrap="nowrap">
                        <Text size="sm">{editor.label(name)}</Text>
                        {typeBadge(info.type)}
                      </Group>
                    }
                    checked={fixed || editor.required.includes(name)}
                    disabled={fixed}
                    onChange={e =>
                      editor.setRequired(name, e.currentTarget.checked)
                    }
                  />
                );
              })}
              {inLayout.length === 0 && (
                <Text size="xs" c="dimmed" ta="center" py="sm">
                  {t('noFields')}
                </Text>
              )}
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Box>
    </LayoutAside>
  );
}
