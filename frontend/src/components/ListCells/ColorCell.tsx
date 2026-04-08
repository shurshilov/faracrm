import { Group, Text, ColorSwatch } from '@mantine/core';

export interface ColorCellProps {
  value: string | null | undefined;
  /** Показывать ли текстовый код цвета рядом с квадратиком */
  showText?: boolean;
}

/**
 * Компонент для отображения цвета в таблице/списке
 *
 * @example
 * <ColorCell value="#228be6" />
 * <ColorCell value="#fab005" showText />
 */
export function ColorCell({ value, showText = true }: ColorCellProps) {
  // Если значения нет, можно вернуть пустую ячейку или прочерк
  if (!value)
    return (
      <Text size="sm" c="dimmed">
        —
      </Text>
    );

  return (
    <Group gap={8} wrap="nowrap">
      <ColorSwatch color={value} size={14} withShadow={false} />
      {showText && (
        <Text size="sm" style={{ fontFamily: 'monospace' }}>
          {value.toUpperCase()}
        </Text>
      )}
    </Group>
  );
}

export default ColorCell;
