import { useState, useMemo } from 'react';
import { AppShell, Flex, Group, ScrollArea } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';

import ThemeToggle from '@/components/ThemeToggle';
import FaraRouters from '@/route/Routers';
import Logo from '@/components/Logo';
import { NavbarMenu } from '@/components/NavbarMenu/NavbarMenu';
import { items } from '@/components/NavbarMenu/menuData';
import {
  SidebarContext,
  SidebarState,
} from '@/components/NavbarMenu/SidebarContext';
import { SidebarToggle } from '@/components/NavbarMenu/SidebarToggle';
import classes from './ProtectedLayout.module.css';
import UserMenu from '@/components/UserMenu';
import { ChatNotification } from '@/components/ChatNotification';
import { ChatWebSocketProvider } from '@/fara_chat/context';

// Ширина сайдбара для каждого состояния
const SIDEBAR_WIDTH: Record<SidebarState, number> = {
  expanded: 250,
  collapsed: 70,
  hidden: 0,
};

// Порядок переключения состояний
const STATE_CYCLE: SidebarState[] = ['expanded', 'collapsed', 'hidden'];

export default function CollapseSideBar() {
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure();
  const [sidebarState, setSidebarState] = useState<SidebarState>('expanded');

  // Циклическое переключение состояний
  const toggleSidebar = () => {
    const currentIndex = STATE_CYCLE.indexOf(sidebarState);
    const nextIndex = (currentIndex + 1) % STATE_CYCLE.length;
    setSidebarState(STATE_CYCLE[nextIndex]);
  };

  // Контекст для дочерних компонентов
  const sidebarContext = useMemo(
    () => ({
      state: sidebarState,
      setState: setSidebarState,
      toggle: toggleSidebar,
    }),
    [sidebarState],
  );

  const navbarWidth = SIDEBAR_WIDTH[sidebarState];
  const isHidden = sidebarState === 'hidden';

  return (
    <ChatWebSocketProvider>
      <SidebarContext.Provider value={sidebarContext}>
        <AppShell
        header={{ height: 50 }}
        navbar={{
          width: navbarWidth,
          breakpoint: 'sm',
          collapsed: { mobile: !mobileOpened, desktop: isHidden },
        }}
        padding="md"
        transitionDuration={200}
        transitionTimingFunction="ease">
        <AppShell.Header className={classes.navbar}>
          <Flex justify="space-between" align="center" h="100%">
            <Group h="100%" px="md">
              {/* Мобильная кнопка бургер */}
              <Group hiddenFrom="sm">
                <SidebarToggle
                  state={mobileOpened ? 'expanded' : 'hidden'}
                  onToggle={toggleMobile}
                />
              </Group>
              {/* Десктопная кнопка переключения */}
              <Group visibleFrom="sm">
                <SidebarToggle state={sidebarState} onToggle={toggleSidebar} />
              </Group>
            </Group>
            <Logo />
            <Group h="100%" px="md">
              <ThemeToggle />
              <ChatNotification />
              <UserMenu />
            </Group>
          </Flex>
        </AppShell.Header>

        <AppShell.Navbar
          withBorder={false}
          className={classes.navbar}
          data-collapsed={sidebarState === 'collapsed' || undefined}>
          <ScrollArea
            className={classes.scrollarea}
            scrollHideDelay={0}
            type="hover"
            offsetScrollbars={false}
            scrollbarSize={5}>
            <div
              className={classes.body}
              data-collapsed={sidebarState === 'collapsed' || undefined}>
              <NavbarMenu items={items} />
            </div>
          </ScrollArea>
        </AppShell.Navbar>

        <AppShell.Main className={classes.main}>
          <FaraRouters></FaraRouters>
        </AppShell.Main>
      </AppShell>
    </SidebarContext.Provider>
    </ChatWebSocketProvider>
  );
}
