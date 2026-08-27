import { useState, useEffect, useMemo } from 'react';
import {
  AppShell,
  Badge,
  Box,
  Flex,
  Group,
  ScrollArea,
  ActionIcon,
} from '@mantine/core';
import { useLocation } from 'react-router-dom';
import { useMediaQuery } from '@mantine/hooks';
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react';

import FaraRouters from '@/route/Routers';
import Logo from '@/components/Logo';
import UserMenu from '@/components/UserMenu';
import { ChatNotification } from '@/components/ChatNotification';
import { ActivityNotification } from '@/fara_activity/ActivityNotification';
import { ChatWebSocketProvider } from '@/fara_chat/context';
import { CallProvider } from '@/fara_chat/context/CallContext';
import { CallWidget } from '@/fara_chat/components/CallWidget';
import { IncomingCallCard } from '@/fara_telephony/IncomingCallCard';
import { SipErrorBoundary, SipPhoneButton } from '@/fara_sip_phone';
import { NotificationListener } from '@/components/NotificationToast/NotificationToast';
import { AppLauncher } from './AppLauncher';
import { HorizontalMenu } from './HorizontalMenu';
import { MobileSubmenuDrawer } from './MobileSubmenuDrawer';
import { ChatSidebar } from './ChatSidebar';
import classes from './ModernLayout.module.css';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import type { MenuGroup } from '@config/menuData';
import { getVisibleMenuItems } from '@config/menuData';

export function ModernLayout() {
  const [activeGroup, setActiveGroup] = useState<MenuGroup | null>(null);
  const [chatSidebarCollapsed, setChatSidebarCollapsed] = useState(false);
  const location = useLocation();
  const isMobile = useMediaQuery('(max-width: 768px)');
  const { t } = useTranslation('workspace');

  const session = useSelector((state: any) => state.auth.session);
  const menuItems = useMemo(
    () =>
      getVisibleMenuItems(
        session?.user_id?.role_ids || [],
        session?.user_id?.is_admin || false,
        session?.user_id?.workspace_id?.app_keys ?? null,
      ),
    [
      session?.user_id?.role_ids,
      session?.user_id?.is_admin,
      session?.user_id?.workspace_id,
    ],
  );

  // Определяем активную группу по текущему URL
  useEffect(() => {
    const currentPath = location.pathname;

    // Находим группу, которая содержит текущий путь
    for (const group of menuItems) {
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

  // Проверяем, находимся ли мы в чате (нужен боковой sidebar).
  //
  // Сравнение точное, а не по префиксу: под startsWith('/chat') попадали и
  // справочники — /chat_connector, /chat_folder, /chat_external_*. Из-за
  // этого сайдбар с чатами оставался на одних пунктах меню настроек и
  // пропадал на других (например на «Релее звонков») — соседние страницы
  // одного раздела вели себя по-разному.
  const isInChat =
    location.pathname === '/chat' || location.pathname.startsWith('/chat/');

  const chatNavbarWidth = chatSidebarCollapsed ? 0 : 280;

  // На мобильном AppShell.Navbar (ChatSidebar с фильтрами) всегда скрыт —
  // навигация по фильтрам на мобильном происходит через боковую панель
  // внутри самого ChatPage (styles.sidebar / styles.hidden)
  const mobileNavbarCollapsed = !!isMobile || chatSidebarCollapsed;

  return (
    <ChatWebSocketProvider>
      <CallProvider>
        <NotificationListener />
        <AppShell
        header={{ height: { base: 48, sm: 60 } }}
        navbar={
          isInChat
            ? {
                width: chatNavbarWidth,
                breakpoint: 'sm',
                collapsed: {
                  mobile: mobileNavbarCollapsed,
                  desktop: chatSidebarCollapsed,
                },
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
              <AppLauncher items={menuItems} onSelectGroup={setActiveGroup} />
            </Group>

            {/* Логотип — скрываем на маленьких mobile чтобы дать место меню */}
            <Box
              visibleFrom="xs"
              style={{
                display: 'flex',
                alignItems: 'center',
                flexShrink: 1,
                minWidth: 0,
              }}>
              <Logo />
            </Box>

            {/* Активное «Рабочее место» пользователя — бейдж, только desktop */}
            {session?.user_id?.workspace_id?.name && (
              <Box visibleFrom="md" style={{ flexShrink: 0 }}>
                <Badge
                  variant="light"
                  color="gray"
                  radius="sm"
                  title={t('badge')}
                  style={{ textTransform: 'none' }}>
                  {session.user_id.workspace_id.name}
                </Badge>
              </Box>
            )}

            {/* Горизонтальное меню — только tablet+ */}
            <Box
              visibleFrom="md"
              style={{ flex: 1, overflow: 'hidden', minWidth: 0 }}>
              <HorizontalMenu activeGroup={activeGroup} />
            </Box>

            {/* Спейсер для mobile (когда нет HorizontalMenu) */}
            <Box hiddenFrom="md" style={{ flex: 1 }} />

            {/* Правая часть */}
            <Group
              h="100%"
              px={{ base: 'xs', sm: 'md' }}
              gap={{ base: 4, sm: 'sm' } as any}
              style={{ flexShrink: 0 }}>
              {/* Кнопка подменю активной группы — только мобила
                  (на десктопе подменю показывается в HorizontalMenu) */}
              <Box hiddenFrom="md">
                <MobileSubmenuDrawer activeGroup={activeGroup} />
              </Box>
              {/* В шапке — только то, что сообщает о СОБЫТИЯХ: активности,
                  чаты, звонки. Тема и документация переехали в меню
                  пользователя: они нужны редко и не требуют внимания. */}
              <Box visibleFrom="lg">
                <ActivityNotification />
              </Box>
              <ChatNotification />
              {/* Звонилка: лист в шапке и под своей границей ошибок — упасть
                  может только она сама, история и карточки живут на бэкенде. */}
              <SipErrorBoundary>
                <SipPhoneButton />
              </SipErrorBoundary>
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
      <CallWidget />
      {/* Карточка разговора телефонии — прилетает по WS на любом экране. */}
      <IncomingCallCard />
      </CallProvider>
    </ChatWebSocketProvider>
  );
}
