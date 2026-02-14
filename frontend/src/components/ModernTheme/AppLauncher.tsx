import { useState } from 'react';
import { Box, Text, SimpleGrid, UnstyledButton, Portal } from '@mantine/core';
import { IconApps } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  MenuGroup,
  MenuCategory,
  MenuSimple,
} from '@/components/NavbarMenu/menuData';
import classes from './AppLauncher.module.css';

interface AppLauncherProps {
  items: MenuGroup[];
  onSelectGroup: (group: MenuGroup) => void;
}

export function AppLauncher({ items, onSelectGroup }: AppLauncherProps) {
  const [opened, setOpened] = useState(false);
  const { t } = useTranslation();
  const navigate = useNavigate();

  // Рекурсивный поиск первого simple элемента
  const findFirstSimple = (
    menuItems: (MenuSimple | MenuCategory)[],
  ): MenuSimple | undefined => {
    for (const item of menuItems) {
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

  const handleGroupClick = (group: MenuGroup) => {
    // Выбираем группу для отображения подменю в хедере
    onSelectGroup(group);

    // Если у группы есть прямой роут, переходим туда
    if (group.to) {
      navigate(group.to);
    } else if (group.submenus && group.submenus.length > 0) {
      // Иначе переходим на первый пункт подменю
      const firstSimple = findFirstSimple(group.submenus);
      if (firstSimple) {
        navigate(firstSimple.to);
      }
    }

    setOpened(false);
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    // Закрываем только если кликнули на backdrop, а не на контент
    if (e.target === e.currentTarget) {
      setOpened(false);
    }
  };

  return (
    <>
      {/* Кнопка открытия лаунчера */}
      <UnstyledButton
        className={classes.launcherButton}
        onClick={() => setOpened(true)}
        aria-label="Open app launcher">
        <IconApps size={24} />
      </UnstyledButton>

      {/* Fullscreen overlay с приложениями */}
      {opened && (
        <Portal>
          <Box className={classes.overlay} onClick={handleBackdropClick}>
            {/* Та же иконка-кнопка для закрытия — в верхнем левом углу поверх overlay */}
            <UnstyledButton
              className={classes.overlayToggle}
              onClick={() => setOpened(false)}
              aria-label="Close app launcher">
              <IconApps size={24} />
            </UnstyledButton>

            <Box className={classes.content} onClick={e => e.stopPropagation()}>
              <Text className={classes.title}>
                {t('common:applications', 'Приложения')}
              </Text>
              <SimpleGrid
                cols={{ base: 2, xs: 3, sm: 4, md: 5, lg: 6 }}
                spacing="xl"
                className={classes.grid}>
                {items.map(group => {
                  const Icon = group.Icon;
                  const displayLabel = group.labelKey
                    ? t(group.labelKey, { defaultValue: group.label })
                    : group.label;

                  return (
                    <UnstyledButton
                      key={group.id}
                      className={classes.appCard}
                      onClick={() => handleGroupClick(group)}>
                      <Box className={classes.iconWrapper}>
                        <Icon size={56} stroke={1.5} />
                      </Box>
                      <Text className={classes.appLabel}>{displayLabel}</Text>
                    </UnstyledButton>
                  );
                })}
              </SimpleGrid>
            </Box>
          </Box>
        </Portal>
      )}
    </>
  );
}
