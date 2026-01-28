import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Box, Flex, Tooltip, UnstyledButton } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { IconChevronDown, Icon as IconType } from '@tabler/icons-react';
import { MenuCategory, MenuSimple } from '../menuData';

import classes from './NavbarMenuGroup.module.css';
import { hasActiveLink, scrollToLink, treeMenuComponents } from './utils';

interface NavbarMenuGroupProps {
  label: string;
  labelKey?: string; // Ключ перевода (namespace:key)
  submenus: (MenuSimple | MenuCategory)[];
  Icon: IconType;
  to?: string;
  collapsed?: boolean;
}

export function NavbarMenuGroup({
  label,
  labelKey,
  submenus,
  Icon,
  to,
  collapsed = false,
}: NavbarMenuGroupProps) {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const linkRef = useRef<HTMLButtonElement>(null);
  const [opened, setOpened] = useState(
    hasActiveLink(submenus, location.pathname),
  );

  // Получаем переведённый текст или используем label как fallback
  const displayLabel = labelKey ? t(labelKey, { defaultValue: label }) : label;

  useEffect(() => {
    if (hasActiveLink(submenus, location.pathname)) {
      setOpened(true);
      setTimeout(() => scrollToLink(linkRef), 10);
    }
  }, [location.pathname]);

  // Рекурсивный поиск первого simple элемента
  const findFirstSimple = (
    items: (MenuSimple | MenuCategory)[],
  ): MenuSimple | undefined => {
    for (const item of items) {
      if (item.type === 'simple') {
        return item;
      }
      if (item.type === 'category' && item.submenus?.length) {
        const found = findFirstSimple(item.submenus);
        if (found) return found;
      }
    }
    return undefined;
  };

  const handleClick = () => {
    if (collapsed) {
      // В свернутом режиме клик по иконке переходит на первый пункт меню или to
      if (to) {
        navigate(to);
        setOpened(true);
      } else if (submenus.length > 0) {
        // Найти первый simple пункт (рекурсивно)
        const firstSimple = findFirstSimple(submenus);
        if (firstSimple) {
          navigate(firstSimple.to);
          setOpened(true);
        }
      }
    } else {
      if (!submenus.length && to) {
        navigate(to);
      }
      setOpened(!opened);
    }
  };

  // Определяем активное состояние: либо точное совпадение, либо есть активный элемент в подменю
  const isActive = location.pathname === to || hasActiveLink(submenus, location.pathname);

  const buttonContent = (
    <UnstyledButton
      className={classes.link}
      data-active={isActive ? 'true' : undefined}
      data-collapsed={collapsed || undefined}
      onClick={handleClick}
      ref={linkRef}>
      <Flex align="center" justify={collapsed ? 'center' : 'flex-start'}>
        <span className={classes.icon}>
          <Icon className={classes.groupIcon} stroke={1.5} />
        </span>
        {!collapsed && <span className={classes.label}>{displayLabel}</span>}
      </Flex>
      {!collapsed && (
        <Flex>
          {!!submenus.length && (
            <IconChevronDown
              className={classes.chevron}
              data-collapsed={!opened || undefined}
            />
          )}
        </Flex>
      )}
    </UnstyledButton>
  );

  return (
    <Box className={classes.groupBox} mod={{ opened, collapsed }}>
      {collapsed ? (
        <Tooltip
          label={displayLabel}
          position="right"
          withArrow
          transitionProps={{ duration: 200 }}>
          {buttonContent}
        </Tooltip>
      ) : (
        buttonContent
      )}
      {opened && !collapsed && (
        <div className={classes.group}>{treeMenuComponents(submenus)}</div>
      )}
    </Box>
  );
}
