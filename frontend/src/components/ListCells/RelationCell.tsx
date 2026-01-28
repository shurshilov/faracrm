import { Badge, Group, Text, Tooltip } from '@mantine/core';
import { 
  IconDatabase, 
  IconUser, 
  IconShield, 
  IconApps,
  IconTag,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import classes from './ListCells.module.css';

export interface RelationCellProps {
  value: { id: number; name?: string } | number | null | undefined;
  /** Модель для навигации */
  model?: string;
  /** Тип иконки */
  icon?: 'database' | 'user' | 'shield' | 'app' | 'tag' | 'none';
  /** Цвет бейджа */
  color?: string;
  /** Вариант отображения */
  variant?: 'badge' | 'text' | 'link';
  /** Показывать ID рядом с именем */
  showId?: boolean;
}

const iconMap = {
  database: IconDatabase,
  user: IconUser,
  shield: IconShield,
  app: IconApps,
  tag: IconTag,
  none: null,
};

// Автоопределение иконки по модели
const modelIconMap: Record<string, keyof typeof iconMap> = {
  users: 'user',
  roles: 'shield',
  models: 'database',
  apps: 'app',
};

// Автоопределение цвета по модели
const modelColorMap: Record<string, string> = {
  users: 'blue',
  roles: 'violet',
  models: 'indigo',
  apps: 'cyan',
};

/**
 * Компонент для отображения Many2one связи в таблице
 * 
 * @example
 * <RelationCell value={user_id} model="users" />
 * <RelationCell value={role_id} model="roles" variant="badge" />
 * <RelationCell value={model_id} icon="database" color="indigo" />
 */
export function RelationCell({ 
  value, 
  model,
  icon,
  color,
  variant = 'badge',
  showId = false,
}: RelationCellProps) {
  const navigate = useNavigate();
  
  if (!value || (typeof value === 'object' && !value.id)) {
    return <Text size="sm" c="dimmed">—</Text>;
  }

  // Если value это число (не объект) - только ID
  const id = typeof value === 'object' ? value.id : value;
  const name = typeof value === 'object' ? value.name : undefined;
  
  // Показываем: имя если есть, иначе модель #ID или просто #ID
  let displayName: string;
  if (name) {
    displayName = showId ? `${name} #${id}` : name;
  } else if (model) {
    displayName = `${model} #${id}`;
  } else {
    displayName = `#${id}`;
  }
  
  // Для tooltip показываем полную инфу
  const tooltipText = name ? `#${id} — ${name}` : `ID: ${id}`;
  const autoIcon = model ? modelIconMap[model] : undefined;
  const autoColor = model ? modelColorMap[model] : 'gray';
  
  const IconComponent = iconMap[icon || autoIcon || 'none'];
  const badgeColor = color || autoColor;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (model) {
      navigate(`/${model}/${id}`);
    }
  };

  if (variant === 'text') {
    return (
      <Text 
        size="sm" 
        className={model ? classes.relationLink : undefined}
        onClick={model ? handleClick : undefined}
      >
        {displayName}
      </Text>
    );
  }

  if (variant === 'link') {
    return (
      <Group gap={4} wrap="nowrap">
        {IconComponent && <IconComponent size={14} color={`var(--mantine-color-${badgeColor}-6)`} />}
        <Text 
          size="sm" 
          c={badgeColor}
          className={model ? classes.relationLink : undefined}
          onClick={model ? handleClick : undefined}
        >
          {displayName}
        </Text>
      </Group>
    );
  }

  // variant === 'badge'
  return (
    <Tooltip label={tooltipText} disabled={!model}>
      <Badge 
        size="sm" 
        variant="light" 
        color={badgeColor}
        className={model ? classes.relationBadge : undefined}
        onClick={model ? handleClick : undefined}
        leftSection={IconComponent ? <IconComponent size={12} /> : undefined}
      >
        {displayName}
      </Badge>
    </Tooltip>
  );
}

export default RelationCell;
