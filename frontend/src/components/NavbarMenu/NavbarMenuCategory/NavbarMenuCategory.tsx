import { Text, UnstyledButton, Collapse } from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { Icon as IconType, IconChevronRight } from '@tabler/icons-react';
import { useState } from 'react';
import classes from './NavbarMenuCategory.module.css';
import { MenuSimple } from '../menuData';
import { NavbarMenuSimple } from '../NavbarMenuSimple/NavbarMenuSimple';

interface NavbarMenuCategoryProps {
  label: string;
  labelKey?: string;
  submenus: MenuSimple[];
  Icon: IconType;
  defaultCollapsed?: boolean;
}

function MenuItems({ menus }: { menus: MenuSimple[] }) {
  const { t } = useTranslation();

  return (
    <>
      {menus.map(menu => (
        <NavbarMenuSimple key={menu.id} to={menu.to || ''}>
          {menu.labelKey
            ? t(menu.labelKey, { defaultValue: menu.label })
            : menu.label}
        </NavbarMenuSimple>
      ))}
    </>
  );
}

export function NavbarMenuCategory({
  label,
  labelKey,
  submenus,
  Icon,
  defaultCollapsed = false,
}: NavbarMenuCategoryProps) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(!defaultCollapsed);
  const displayLabel = labelKey ? t(labelKey, { defaultValue: label }) : label;

  return (
    <div className={classes.category}>
      <UnstyledButton
        className={classes.categoryTitle}
        onClick={() => setOpened(o => !o)}>
        <Icon className={classes.categoryIcon} />
        <Text className={classes.categoryLabel}>{displayLabel}</Text>
        <IconChevronRight
          className={classes.chevron}
          style={{
            transform: opened ? 'rotate(90deg)' : 'none',
            transition: 'transform 200ms ease',
          }}
          size={14}
        />
      </UnstyledButton>
      <Collapse in={opened}>
        <MenuItems menus={submenus} />
      </Collapse>
    </div>
  );
}
