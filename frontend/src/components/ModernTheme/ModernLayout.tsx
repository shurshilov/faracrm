import { useState, useEffect } from 'react';
import {
  AppShell,
  Flex,
  Group,
  ScrollArea,
  ActionIcon,
  Box,
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
      <AppShell
        header={{ height: 60 }}
        navbar={
          isInChat
            ? {
                width: chatNavbarWidth,
                breakpoint: 'sm',
                collapsed: { desktop: chatSidebarCollapsed },
              }
            : undefined
        }
        padding="md"
        transitionDuration={200}
        transitionTimingFunction="ease">
        <AppShell.Header className={classes.header}>
          <Flex align="center" h="100%" gap="md">
            {/* Кнопка App Launcher */}
            <Group px="md">
              <AppLauncher items={items} onSelectGroup={setActiveGroup} />
            </Group>

            {/* Логотип */}
            <Logo />

            {/* Горизонтальное меню */}
            {/* В чатах показываем только "Настройки", остальное в ChatSidebar */}
            {isInChat ? (
              <HorizontalMenu
                activeGroup={activeGroup}
                filterCategories={['category_comm_settings']}
              />
            ) : (
              <HorizontalMenu activeGroup={activeGroup} />
            )}

            {/* Правая часть */}
            <Group h="100%" px="md" gap="sm" style={{ marginLeft: 'auto' }}>
              <ThemeToggle />
              <ActivityNotification />
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

            {/* Кнопка сворачивания сайдбара */}
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
          </>
        )}

        <AppShell.Main className={classes.main}>
          <FaraRouters />
        </AppShell.Main>
      </AppShell>
    </ChatWebSocketProvider>
  );
}
