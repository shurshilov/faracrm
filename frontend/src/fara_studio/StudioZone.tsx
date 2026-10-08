/**
 * StudioZone — зона «Дополнительно» в режиме студии: сверху её место
 * (под формой / сбоку / вкладкой) и сетка (колонки × строки), ниже —
 * сама сетка. Пустые клетки видны пунктиром, в них бросают поля из
 * панели и из зоны; бросок на поле — обмен местами (zoneGrid.placeAt).
 * Подсветка клетки под курсором: фиолетовая — примет, красная — нет.
 *
 * Внутри клетки — настоящий компонент поля формы, но без ввода
 * (pointer-events: none): в режиме редактирования значения не правят.
 */
import { useContext } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ActionIcon,
  Box,
  Group,
  NumberInput,
  Paper,
  SegmentedControl,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core';
import { IconGripVertical, IconSparkles, IconX } from '@tabler/icons-react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { FormFieldsContext } from '@/components/Form/FormContext';
import { FieldComponents } from '@/components/Form/Fields/Field';
import { ExtraGrid, ExtraGridCell } from './zone/ExtraGrid';
import { ExtraZoneFrame } from './zone/ExtraZoneFrame';
import {
  EXTRA_PLACEMENTS,
  ExtraCell,
  ExtraGridSize,
  ExtraPlacement,
} from './zone/zoneGrid';
import type { CellTarget, DragData } from './dnd';
import type { StudioEditor } from './useStudioEditor';

const MAX_COLUMNS = 12;

/** Строк в редакторе: заданные (больше, если поля не влезли); при ∞ —
 *  занятые и одна пустая снизу, куда добавлять. */
function editorRows(cells: ExtraCell[], grid: ExtraGridSize): number {
  const used = Math.max(0, ...cells.map(cell => cell.y + cell.h - 1));
  return grid.rows ? Math.max(grid.rows, used) : used + 1;
}

function emptyTargets(cells: ExtraCell[], grid: ExtraGridSize): CellTarget[] {
  const rows = editorRows(cells, grid);
  const targets: CellTarget[] = [];
  for (let y = 1; y <= rows; y += 1) {
    for (let x = 1; x <= grid.columns; x += 1) {
      const covered = cells.some(
        cell =>
          x >= cell.x &&
          x < cell.x + cell.w &&
          y >= cell.y &&
          y < cell.y + cell.h,
      );
      if (!covered) targets.push({ x, y });
    }
  }
  return targets;
}

/** Клетка-цель броска и цвет её рамки под курсором. */
function useCellDrop(id: string, target: CellTarget, editor: StudioEditor) {
  const { setNodeRef, isOver, active } = useDroppable({ id, data: target });
  const drag = active?.data.current as DragData | undefined;
  const name = drag?.kind === 'existing' ? drag.name : null;
  let borderColor: string | undefined;
  if (isOver) {
    borderColor = editor.canPlace(name, target.x, target.y)
      ? 'var(--mantine-color-violet-5)'
      : 'var(--mantine-color-red-5)';
  }
  return { setNodeRef, borderColor };
}

function EmptyCell({ x, y, editor }: CellTarget & { editor: StudioEditor }) {
  const { setNodeRef, borderColor } = useCellDrop(
    `drop:${x}:${y}`,
    { x, y },
    editor,
  );
  return (
    <ExtraGridCell
      ref={setNodeRef}
      cell={{ x, y, w: 1, h: 1 }}
      style={{
        minHeight: 56,
        borderRadius: 'var(--mantine-radius-md)',
        border: '2px dashed',
        borderColor: borderColor ?? 'var(--mantine-color-gray-4)',
        transition: 'border-color 0.15s ease',
      }}
    />
  );
}

function FieldCell({
  cell,
  editor,
}: {
  cell: ExtraCell;
  editor: StudioEditor;
}) {
  const { t } = useTranslation('studio');
  const { model, fields } = useContext(FormFieldsContext);
  // Поле тянут за ручку; само поле — ещё и цель: бросок на него — обмен.
  const drag = useDraggable({
    id: `zone:${cell.name}`,
    data: { kind: 'existing', name: cell.name } satisfies DragData,
  });
  const drop = useCellDrop(`drop:${cell.name}`, cell, editor);
  const info = fields[cell.name];
  const Component = info && FieldComponents['Field' + info.type];
  const label = editor.label(cell.name);
  const selected = editor.selected === cell.name;

  return (
    <ExtraGridCell ref={drop.setNodeRef} cell={cell}>
      <Paper
        ref={drag.setNodeRef}
        withBorder
        p="xs"
        radius="md"
        h="100%"
        onClick={() => editor.select(cell.name)}
        style={{
          opacity: drag.isDragging ? 0.5 : 1,
          cursor: 'pointer',
          borderColor:
            drop.borderColor ??
            (selected ? 'var(--mantine-color-violet-5)' : undefined),
        }}>
        <Group wrap="nowrap" align="flex-start" gap="xs">
          <ActionIcon
            variant="subtle"
            color="gray"
            size="sm"
            style={{ cursor: 'grab' }}
            {...drag.attributes}
            {...drag.listeners}
            onClick={e => e.stopPropagation()}>
            <IconGripVertical size={14} />
          </ActionIcon>
          <Box style={{ flex: 1, minWidth: 0, pointerEvents: 'none' }}>
            {Component ? (
              <Component
                name={cell.name}
                model={model}
                required={info.required}
                label={label}
              />
            ) : (
              <Text size="sm">{label}</Text>
            )}
          </Box>
          <Tooltip label={t('removeFromForm')}>
            <ActionIcon
              variant="subtle"
              color="gray"
              size="sm"
              aria-label={t('removeFromForm')}
              onClick={e => {
                e.stopPropagation();
                editor.removeFromForm(cell.name);
              }}>
              <IconX size={14} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Paper>
    </ExtraGridCell>
  );
}

/** Место зоны и размер сетки. placement — где зона на деле. */
function ZoneSettings({
  editor,
  placement,
}: {
  editor: StudioEditor;
  placement: ExtraPlacement;
}) {
  const { t } = useTranslation('studio');
  const { grid } = editor;

  return (
    <Stack gap={4}>
      <Group justify="space-between" gap="xs">
        <SegmentedControl
          size="xs"
          value={editor.placement}
          onChange={value => editor.setPlacement(value as ExtraPlacement)}
          data={EXTRA_PLACEMENTS.map(value => ({
            value,
            label: t(`placement.${value}`),
          }))}
        />
        <Group gap={6} wrap="nowrap">
          <Text size="xs" c="dimmed">
            {t('grid')}
          </Text>
          <NumberInput
            size="xs"
            w={64}
            min={1}
            max={MAX_COLUMNS}
            aria-label={t('columns')}
            value={grid.columns}
            onChange={value => {
              if (typeof value === 'number' && value >= 1) {
                editor.setGrid({ ...grid, columns: value });
              }
            }}
          />
          <Text size="xs">×</Text>
          <NumberInput
            size="xs"
            w={64}
            min={1}
            placeholder="∞"
            aria-label={t('rows')}
            value={grid.rows ?? ''}
            onChange={value =>
              editor.setGrid({
                ...grid,
                rows: typeof value === 'number' && value >= 1 ? value : null,
              })
            }
          />
        </Group>
      </Group>
      {editor.placement === 'tab' && placement !== 'tab' && (
        <Text size="xs" c="dimmed">
          {t('noTabs')}
        </Text>
      )}
    </Stack>
  );
}

interface StudioZoneProps {
  editor: StudioEditor;
  placement: ExtraPlacement;
}

export function StudioZone({ editor, placement }: StudioZoneProps) {
  const { t } = useTranslation('studio');

  return (
    <ExtraZoneFrame
      placement={placement}
      title={t('zoneTitle')}
      icon={<IconSparkles size={18} />}>
      <Stack gap="sm">
        <ZoneSettings editor={editor} placement={placement} />
        <ExtraGrid columns={editor.grid.columns}>
          {emptyTargets(editor.cells, editor.grid).map(({ x, y }) => (
            <EmptyCell key={`${x}:${y}`} x={x} y={y} editor={editor} />
          ))}
          {editor.cells.map(cell => (
            <FieldCell key={cell.name} cell={cell} editor={editor} />
          ))}
        </ExtraGrid>
        {editor.cells.length === 0 && (
          <Text size="sm" c="dimmed" ta="center">
            {t('dropHere')}
          </Text>
        )}
      </Stack>
    </ExtraZoneFrame>
  );
}
