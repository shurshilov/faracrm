import { useState, useEffect } from 'react';
import {
  AppShell,
  Box,
  Flex,
  Group,
  ScrollArea,
  ActionIcon,
} from '@mantine/core';
import { useLocation } from 'react-router-dom';
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react';

import ThemeToggle from '@/components/ThemeToggle';
import FaraRouters from '@/route/Routers';
import Logo from '@/components/Logo';
import { items, MenuGroup } from '@/components/NavbarMenu/menuData';
import UserMenu from '@/components/UserMenu';
import { ChatNotification } from '@/components/ChatNotification';
import { ActivityNotification } from '@/fara_activity/ActivityNotification';
import { ChatWebSocketProvider } from '@/fara_chat/context';
import { NotificationListener } from '@/components/NotificationToast/NotificationToast';
import { AppLauncher } from './AppLauncher';
import { HorizontalMenu } from './HorizontalMenu';
import { ChatSidebar } from './ChatSidebar';
import classes from './ModernLayout.module.css';

export function ModernLayout() {
  const [activeGroup, setActiveGroup] = useState<MenuGroup | null>(null);
  const [chatSidebarCollapsed, setChatSidebarCollapsed] = useState(false);
  const location = useLocation();

  // Определяем активную группу по текущему URL
  useEffect(() => {
    const currentPath = location.pathname;

    // Находим группу, которая содержит текущий путь
    for (const group of items) {
      if (group.to && currentPath.startsWith(group.to)) {
        setActiveGroup(group);
        return;
      }
      if (group.submenus) {
        for (const submenu of group.submenus) {
          if (
            'to' in submenu &&
            currentPath.startsWith(submenu.to.split('?')[0])
          ) {
            setActiveGroup(group);
            return;
          }
          if ('submenus' in submenu) {
            for (const sub of submenu.submenus) {
              if (currentPath.startsWith(sub.to.split('?')[0])) {
                setActiveGroup(group);
                return;
              }
            }
          }
        }
      }
    }
  }, [location.pathname]);

  // Проверяем, находимся ли мы в чате (нужен боковой sidebar)
  const isInChat = location.pathname.startsWith('/chat');

  const chatNavbarWidth = chatSidebarCollapsed ? 0 : 280;

  return (
    <ChatWebSocketProvider>
      <NotificationListener />
      <AppShell
        header={{ height: { base: 48, sm: 60 } }}
        navbar={
          isInChat
            ? {
                width: chatNavbarWidth,
                breakpoint: 'sm',
                collapsed: { mobile: chatSidebarCollapsed, desktop: chatSidebarCollapsed },
              }
            : undefined
        }
        padding={{ base: 'xs', sm: 'md' }}
        transitionDuration={200}
        transitionTimingFunction="ease">
        <AppShell.Header className={classes.header}>
          <Flex align="center" h="100%" gap={{ base: 'xs', sm: 'md' }}>
            {/* Кнопка App Launcher */}
            <Group px={{ base: 'xs', sm: 'md' }}>
              <AppLauncher items={items} onSelectGroup={setActiveGroup} />
            </Group>

            {/* Логотип — скрываем на маленьких mobile чтобы дать место меню */}
            <Box visibleFrom="xs" style={{ display: 'flex', alignItems: 'center', flexShrink: 1, minWidth: 0 }}>
              <Logo />
            </Box>

            {/* Горизонтальное меню — только tablet+ */}
            <Box visibleFrom="md" style={{ flex: 1, overflow: 'hidden', minWidth: 0 }}>
              {isInChat ? (
                <HorizontalMenu
                  activeGroup={activeGroup}
                  filterCategories={['category_comm_settings']}
                />
              ) : (
                <HorizontalMenu activeGroup={activeGroup} />
              )}
            </Box>

            {/* Спейсер для mobile (когда нет HorizontalMenu) */}
            <Box hiddenFrom="md" style={{ flex: 1 }} />

            {/* Правая часть */}
            <Group h="100%" px={{ base: 'xs', sm: 'md' }} gap={{ base: 4, sm: 'sm' }} style={{ flexShrink: 0 }}>
              <Box visibleFrom="sm">
                <ThemeToggle />
              </Box>
              <Box visibleFrom="lg">
                <ActivityNotification />
              </Box>
              <ChatNotification />
              <UserMenu />
            </Group>
          </Flex>
        </AppShell.Header>

        {/* Боковая панель только для чатов */}
        {isInChat && (
          <>
            <AppShell.Navbar withBorder={false} className={classes.chatNavbar}>
              <ScrollArea className={classes.scrollarea}>
                <ChatSidebar />
              </ScrollArea>
            </AppShell.Navbar>

            {/* Кнопка сворачивания сайдбара — только desktop */}
            <Box visibleFrom="sm">
              <ActionIcon
                className={classes.collapseButton}
                variant="default"
                size="sm"
                radius="xl"
                onClick={() => setChatSidebarCollapsed(!chatSidebarCollapsed)}
                style={{
                  left: chatSidebarCollapsed ? 4 : 268,
                }}>
                {chatSidebarCollapsed ? (
                  <IconChevronRight size={14} />
                ) : (
                  <IconChevronLeft size={14} />
                )}
              </ActionIcon>
            </Box>
          </>
        )}

        <AppShell.Main className={classes.main}>
          <FaraRouters />
        </AppShell.Main>
      </AppShell>
    </ChatWebSocketProvider>
  );
}
