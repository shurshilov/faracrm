import { useState } from 'react';
import { Group, Menu, UnstyledButton, Text } from '@mantine/core';
import { IconChevronDown } from '@tabler/icons-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  MenuGroup,
  MenuCategory,
  MenuSimple,
  isMenuCategory,
} from '@/components/NavbarMenu/menuData';
import classes from './HorizontalMenu.module.css';

interface HorizontalMenuProps {
  activeGroup: MenuGroup | null;
  /** Показывать только эти категории (по id). Если не указано - показывать все */
  filterCategories?: string[];
}

export function HorizontalMenu({
  activeGroup,
  filterCategories,
}: HorizontalMenuProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  if (!activeGroup || !activeGroup.submenus) {
    return null;
  }

  // Фильтруем подменю если указан filterCategories
  const filteredSubmenus = filterCategories
    ? activeGroup.submenus.filter(item => filterCategories.includes(item.id))
    : activeGroup.submenus;

  if (filteredSubmenus.length === 0) {
    return null;
  }

  return (
    <Group gap="xs" className={classes.menuContainer}>
      {filteredSubmenus.map(item => {
        if (isMenuCategory(item)) {
          return (
            <CategoryDropdown
              key={item.id}
              category={item}
              t={t}
              navigate={navigate}
              currentPath={location.pathname + location.search}
            />
          );
        }
        return (
          <SimpleMenuItem
            key={item.id}
            item={item}
            t={t}
            navigate={navigate}
            isActive={location.pathname + location.search === item.to}
          />
        );
      })}
    </Group>
  );
}

// Простой пункт меню
interface SimpleMenuItemProps {
  item: MenuSimple;
  t: (key: string, options?: { defaultValue: string }) => string;
  navigate: (path: string) => void;
  isActive: boolean;
}

function SimpleMenuItem({ item, t, navigate, isActive }: SimpleMenuItemProps) {
  const label = item.labelKey
    ? t(item.labelKey, { defaultValue: item.label })
    : item.label;

  return (
    <UnstyledButton
      className={classes.menuItem}
      data-active={isActive || undefined}
      onClick={() => navigate(item.to)}>
      <Text size="sm" fw={500}>
        {label}
      </Text>
    </UnstyledButton>
  );
}

// Выпадающее меню для категории
interface CategoryDropdownProps {
  category: MenuCategory;
  t: (key: string, options?: { defaultValue: string }) => string;
  navigate: (path: string) => void;
  currentPath: string;
}

function CategoryDropdown({
  category,
  t,
  navigate,
  currentPath,
}: CategoryDropdownProps) {
  const [opened, setOpened] = useState(false);

  const hasActiveChild = category.submenus.some(sub => currentPath === sub.to);

  const categoryLabel = category.labelKey
    ? t(category.labelKey, { defaultValue: category.label })
    : category.label;

  return (
    <Menu
      opened={opened}
      onChange={setOpened}
      position="bottom-start"
      offset={4}
      withinPortal>
      <Menu.Target>
        <UnstyledButton
          className={classes.menuItem}
          data-active={hasActiveChild || undefined}>
          <Group gap={4}>
            <Text size="sm" fw={500}>
              {categoryLabel}
            </Text>
            <IconChevronDown
              size={14}
              className={classes.chevron}
              data-opened={opened || undefined}
            />
          </Group>
        </UnstyledButton>
      </Menu.Target>

      <Menu.Dropdown className={classes.dropdown}>
        {category.submenus.map(subItem => {
          const subLabel = subItem.labelKey
            ? t(subItem.labelKey, { defaultValue: subItem.label })
            : subItem.label;

          return (
            <Menu.Item
              key={subItem.id}
              className={classes.dropdownItem}
              data-active={currentPath === subItem.to || undefined}
              onClick={() => {
                navigate(subItem.to);
                setOpened(false);
              }}>
              {subLabel}
            </Menu.Item>
          );
        })}
      </Menu.Dropdown>
    </Menu>
  );
}
