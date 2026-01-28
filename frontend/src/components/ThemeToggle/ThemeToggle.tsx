import {
  ActionIcon,
  useMantineColorScheme,
  useComputedColorScheme,
  Tooltip,
} from '@mantine/core';
import { IconSun, IconMoon } from '@tabler/icons-react';
import classes from './ThemeToggle.module.css';

function ThemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const computedColorScheme = useComputedColorScheme('light', {
    getInitialValueInEffect: true,
  });

  const isDark = computedColorScheme === 'dark';

  return (
    <Tooltip
      label={isDark ? 'Светлая тема' : 'Тёмная тема'}
      position="bottom"
      withArrow
    >
      <ActionIcon
        onClick={() => setColorScheme(isDark ? 'light' : 'dark')}
        variant="subtle"
        size="lg"
        radius="md"
        aria-label="Переключить тему"
        className={classes.toggle}
      >
        <IconSun className={classes.light} stroke={1.5} />
        <IconMoon className={classes.dark} stroke={1.5} />
      </ActionIcon>
    </Tooltip>
  );
}

export default ThemeToggle;
