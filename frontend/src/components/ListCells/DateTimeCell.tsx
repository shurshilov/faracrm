import { Group, Text, Tooltip } from '@mantine/core';
import { IconCalendar, IconClock } from '@tabler/icons-react';
import classes from './ListCells.module.css';

export interface DateTimeCellProps {
  value: string | Date | null | undefined;
  /** Формат отображения */
  format?: 'full' | 'date' | 'time' | 'relative' | 'compact';
  /** Показывать иконку */
  showIcon?: boolean;
  /** Локаль */
  locale?: string;
}

/**
 * Форматирует относительное время (например "5 минут назад")
 */
function getRelativeTime(date: Date, locale: string): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  const isRu = locale.startsWith('ru');

  if (diffSec < 60) {
    return isRu ? 'только что' : 'just now';
  }
  if (diffMin < 60) {
    return isRu ? `${diffMin} мин. назад` : `${diffMin}m ago`;
  }
  if (diffHour < 24) {
    return isRu ? `${diffHour} ч. назад` : `${diffHour}h ago`;
  }
  if (diffDay < 7) {
    return isRu ? `${diffDay} дн. назад` : `${diffDay}d ago`;
  }
  
  // Больше недели - показываем дату
  return date.toLocaleDateString(locale, { 
    day: 'numeric', 
    month: 'short' 
  });
}

/**
 * Компонент для отображения даты/времени в таблице
 * 
 * @example
 * <DateTimeCell value={create_datetime} />
 * <DateTimeCell value={create_datetime} format="relative" />
 * <DateTimeCell value={create_datetime} format="compact" showIcon />
 */
export function DateTimeCell({ 
  value, 
  format = 'compact',
  showIcon = false,
  locale = 'ru-RU',
}: DateTimeCellProps) {
  if (!value) {
    return <Text size="sm" c="dimmed">—</Text>;
  }

  const date = typeof value === 'string' ? new Date(value) : value;
  
  if (isNaN(date.getTime())) {
    return <Text size="sm" c="dimmed">—</Text>;
  }

  // Полная дата для tooltip
  const fullDateTime = date.toLocaleString(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  let displayText: string;
  let IconComponent = IconCalendar;

  switch (format) {
    case 'full':
      displayText = fullDateTime;
      break;
    case 'date':
      displayText = date.toLocaleDateString(locale, {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      });
      break;
    case 'time':
      displayText = date.toLocaleTimeString(locale, {
        hour: '2-digit',
        minute: '2-digit',
      });
      IconComponent = IconClock;
      break;
    case 'relative':
      displayText = getRelativeTime(date, locale);
      IconComponent = IconClock;
      break;
    case 'compact':
    default:
      // Компактный формат: дата + время без секунд
      displayText = date.toLocaleString(locale, {
        day: '2-digit',
        month: '2-digit',
        year: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
      break;
  }

  const content = (
    <Group gap={6} wrap="nowrap">
      {showIcon && (
        <IconComponent 
          size={14} 
          className={classes.dateIcon}
        />
      )}
      <Text size="sm" className={classes.dateText}>
        {displayText}
      </Text>
    </Group>
  );

  // Tooltip только если формат не full
  if (format !== 'full') {
    return (
      <Tooltip label={fullDateTime} withArrow>
        {content}
      </Tooltip>
    );
  }

  return content;
}

export default DateTimeCell;
