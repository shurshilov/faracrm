import { useState } from 'react';
import {
  Drawer,
  UnstyledButton,
  Text,
  Stack,
  Box,
  Group,
} from '@mantine/core';
import { IconMenu2 } from '@tabler/icons-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  MenuGroup,
  MenuCategory,
  MenuSimple,
  isMenuCategory,
} from '@config/menuData';
import classes from './MobileSubmenuDrawer.module.css';

interface MobileSubmenuDrawerProps {
  activeGroup: MenuGroup | null;
}

/**
 * Кнопка + Drawer для подменю активной группы на мобиле.
 * На десктопе подменю показывает HorizontalMenu, на мобиле этот компонент.
 */
export function MobileSubmenuDrawer({ activeGroup }: MobileSubmenuDrawerProps) {
  const [opened, setOpened] = useState(false);
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  // Если активной группы нет или у неё нет подменю — кнопку не показываем.
  if (!activeGroup || !activeGroup.submenus?.length) {
    return null;
  }

  const handlePick = (item: MenuSimple) => {
    navigate(item.to);
    setOpened(false);
  };

  const groupLabel = activeGroup.labelKey
    ? t(activeGroup.labelKey, { defaultValue: activeGroup.label })
    : activeGroup.label;

  const currentPath = location.pathname + location.search;

  return (
    <>
      <UnstyledButton
        className={classes.button}
        onClick={() => setOpened(true)}
        aria-label="Open submenu">
        <IconMenu2 size={22} />
      </UnstyledButton>

      <Drawer
        opened={opened}
        onClose={() => setOpened(false)}
        position="right"
        size="80%"
        title={groupLabel}
        padding="md"
        classNames={{ title: classes.drawerTitle }}>
        <Stack gap="xs">
          {activeGroup.submenus.map(item =>
            isMenuCategory(item) ? (
              <CategoryBlock
                key={item.id}
                category={item}
                onPick={handlePick}
                t={t}
                currentPath={currentPath}
              />
            ) : (
              <SubmenuRow
                key={item.id}
                item={item}
                onPick={handlePick}
                t={t}
                isActive={currentPath === item.to}
              />
            ),
          )}
        </Stack>
      </Drawer>
    </>
  );
}

// ── Подкомпоненты ─────────────────────────────────────────────────

interface SubmenuRowProps {
  item: MenuSimple;
  onPick: (item: MenuSimple) => void;
  t: (key: string, options?: { defaultValue: string }) => string;
  isActive: boolean;
}

function SubmenuRow({ item, onPick, t, isActive }: SubmenuRowProps) {
  const label = item.labelKey
    ? t(item.labelKey, { defaultValue: item.label })
    : item.label;
  return (
    <UnstyledButton
      className={classes.row}
      data-active={isActive || undefined}
      onClick={() => onPick(item)}>
      <Text size="md" fw={500}>
        {label}
      </Text>
    </UnstyledButton>
  );
}

interface CategoryBlockProps {
  category: MenuCategory;
  onPick: (item: MenuSimple) => void;
  t: (key: string, options?: { defaultValue: string }) => string;
  currentPath: string;
}

function CategoryBlock({
  category,
  onPick,
  t,
  currentPath,
}: CategoryBlockProps) {
  const label = category.labelKey
    ? t(category.labelKey, { defaultValue: category.label })
    : category.label;
  return (
    <Box className={classes.categoryBlock}>
      <Text className={classes.categoryHeader}>{label}</Text>
      <Stack gap={4}>
        {category.submenus.map(sub => (
          <SubmenuRow
            key={sub.id}
            item={sub}
            onPick={onPick}
            t={t}
            isActive={currentPath === sub.to}
          />
        ))}
      </Stack>
    </Box>
  );
}
