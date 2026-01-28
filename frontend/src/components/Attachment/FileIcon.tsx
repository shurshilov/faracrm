import { Box, ThemeIcon } from '@mantine/core';
import { getFileIconConfig } from './fileIcons';

interface FileIconProps {
  mimetype?: string | null;
  size?: number;
  iconSize?: number;
}

export function FileIcon({
  mimetype,
  size = 48,
  iconSize,
}: FileIconProps) {
  const { icon: Icon, color } = getFileIconConfig(mimetype);
  const computedIconSize = iconSize ?? size * 0.6;

  return (
    <ThemeIcon
      size={size}
      radius="md"
      variant="light"
      color={color}
      style={{ backgroundColor: `${color}15` }}
    >
      <Icon size={computedIconSize} stroke={1.5} color={color} />
    </ThemeIcon>
  );
}
