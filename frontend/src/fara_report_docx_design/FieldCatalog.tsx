/**
 * Каталог полей конструктора: что можно вставить в шаблон.
 *
 * Два раздела — ключи функции данных (@report_fields на бэке) и поля записи
 * модели (связи на один уровень, списки как цикл по строкам таблицы). Клик по
 * полю вставляет его в позицию курсора редактора как content control с
 * подписью; у списка — ещё кнопки начала и конца цикла (docxtpl {%tr for %}).
 */
import { useMemo, useState } from 'react';
import {
  Accordion,
  Box,
  Button,
  Group,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  UnstyledButton,
} from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import type { ReportFieldNode } from './api';

interface FieldCatalogProps {
  nodes: ReportFieldNode[];
  onInsertField: (node: ReportFieldNode) => void;
  onInsertText: (text: string) => void;
}

function matches(node: ReportFieldNode, query: string): boolean {
  return (
    node.label.toLowerCase().includes(query) ||
    node.key.toLowerCase().includes(query)
  );
}

/** Узлы, подходящие под поиск; родитель остаётся, если подходит ребёнок. */
function filterNodes(
  nodes: ReportFieldNode[],
  query: string,
): ReportFieldNode[] {
  if (!query) return nodes;
  const result: ReportFieldNode[] = [];
  for (const node of nodes) {
    if (matches(node, query)) {
      result.push(node);
      continue;
    }
    const children = node.children ? filterNodes(node.children, query) : [];
    if (children.length) result.push({ ...node, children });
  }
  return result;
}

function FieldRow({
  node,
  onClick,
}: {
  node: ReportFieldNode;
  onClick: () => void;
}) {
  return (
    <UnstyledButton
      onClick={onClick}
      // Кнопка не должна забирать каретку у редактора: вставка идёт туда,
      // где стоял курсор
      onMouseDown={e => e.preventDefault()}
      px="xs"
      py={4}
      style={{ display: 'block', width: '100%', borderRadius: 4 }}>
      <Text size="sm">{node.label}</Text>
      <Text size="xs" c="dimmed" ff="monospace" truncate>
        {node.tag ?? node.key}
      </Text>
    </UnstyledButton>
  );
}

export function FieldCatalog({
  nodes,
  onInsertField,
  onInsertText,
}: FieldCatalogProps) {
  const { t } = useTranslation('reportsDesign');
  const [search, setSearch] = useState('');
  const query = search.trim().toLowerCase();

  const visible = useMemo(() => filterNodes(nodes, query), [nodes, query]);
  const sections = [
    {
      key: 'function',
      title: t('designer.functionFields'),
      items: visible.filter(node => node.kind === 'function'),
    },
    {
      key: 'field',
      title: t('designer.recordFields'),
      items: visible.filter(node => node.kind === 'field'),
    },
  ].filter(section => section.items.length > 0);

  const renderNode = (node: ReportFieldNode) => {
    if (!node.children?.length) {
      return (
        <FieldRow
          key={node.key}
          node={node}
          onClick={() => onInsertField(node)}
        />
      );
    }
    const isList = node.type === 'list';
    return (
      <Accordion.Item key={node.key} value={node.key}>
        <Accordion.Control py={4}>
          <Text size="sm">{node.label}</Text>
          <Text size="xs" c="dimmed" ff="monospace">
            {node.key}
          </Text>
        </Accordion.Control>
        <Accordion.Panel>
          <Stack gap={2}>
            {isList ? (
              <Group gap="xs" px="xs" pb={4}>
                <Button
                  size="compact-xs"
                  variant="light"
                  onMouseDown={e => e.preventDefault()}
                  onClick={() =>
                    node.loop_start && onInsertText(node.loop_start)
                  }>
                  {t('designer.loopStart')}
                </Button>
                <Button
                  size="compact-xs"
                  variant="light"
                  onMouseDown={e => e.preventDefault()}
                  onClick={() => node.loop_end && onInsertText(node.loop_end)}>
                  {t('designer.loopEnd')}
                </Button>
              </Group>
            ) : (
              node.tag && (
                <FieldRow
                  node={{ ...node, label: t('designer.relationName') }}
                  onClick={() => onInsertField(node)}
                />
              )
            )}
            {node.children!.map(child => (
              <FieldRow
                key={child.key}
                node={child}
                onClick={() => onInsertField(child)}
              />
            ))}
          </Stack>
        </Accordion.Panel>
      </Accordion.Item>
    );
  };

  return (
    <Stack gap="xs" h="100%" style={{ minHeight: 0 }}>
      <Box px="xs" pt="xs">
        <TextInput
          size="xs"
          value={search}
          onChange={e => setSearch(e.currentTarget.value)}
          placeholder={t('designer.search')}
          leftSection={<IconSearch size={14} />}
        />
        <Text size="xs" c="dimmed" mt={4}>
          {t('designer.insertHint')}
        </Text>
      </Box>
      <ScrollArea style={{ flex: 1, minHeight: 0 }} px={4}>
        {sections.length === 0 && (
          <Text size="sm" c="dimmed" ta="center" py="md">
            {t('designer.noFields')}
          </Text>
        )}
        {sections.map(section => (
          <Box key={section.key} mb="sm">
            <Text size="xs" fw={600} c="dimmed" tt="uppercase" px="xs" py={4}>
              {section.title}
            </Text>
            <Accordion multiple chevronPosition="left" variant="default">
              {section.items.map(renderNode)}
            </Accordion>
          </Box>
        ))}
      </ScrollArea>
    </Stack>
  );
}
