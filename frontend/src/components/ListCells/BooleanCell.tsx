import { Group, Text } from '@mantine/core';
import classes from './ListCells.module.css';

export interface BooleanCellProps {
  value: boolean | null | undefined;
  /** Показывать текст рядом с точкой */
  showText?: boolean;
  /** Кастомные тексты */
  trueText?: string;
  falseText?: string;
}

/**
 * Компонент для отображения boolean в таблице
 * 
 * @example
 * <BooleanCell value={true} />
 * <BooleanCell value={false} showText />
 * <BooleanCell value={active} trueText="Активен" falseText="Неактивен" showText />
 */
export function BooleanCell({ 
  value, 
  showText = false,
  trueText = 'Да',
  falseText = 'Нет',
}: BooleanCellProps) {
  const isTrue = value === true;
  
  return (
    <Group gap={6} wrap="nowrap">
      <span 
        className={classes.booleanDot} 
        data-active={isTrue || undefined}
      />
      {showText && (
        <Text size="sm" c={isTrue ? undefined : 'dimmed'}>
          {isTrue ? trueText : falseText}
        </Text>
      )}
    </Group>
  );
}

export default BooleanCell;
