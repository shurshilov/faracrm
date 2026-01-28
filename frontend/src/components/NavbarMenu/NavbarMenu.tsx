import { Box } from '@mantine/core';
import { MenuGroup, isMenuGroup } from './menuData';
import { NavbarMenuGroup } from './NavbarMenuGroup/NavbarMenuGroup';
import { useSidebar } from './SidebarContext';

function treeMenuComponents(menus: MenuGroup[], collapsed: boolean) {
  const menuGroups = menus.filter(isMenuGroup);
  const allMenus = menuGroups.map(menu => (
    <NavbarMenuGroup
      Icon={menu.Icon}
      key={menu.id}
      label={menu.label}
      labelKey={menu.labelKey}
      submenus={menu.submenus || []}
      to={menu.to}
      collapsed={collapsed}
    />
  ));
  return allMenus;
}

export function NavbarMenu({ items }: { items: MenuGroup[] }) {
  const { state } = useSidebar();
  const collapsed = state === 'collapsed';

  return <Box>{treeMenuComponents(items, collapsed)}</Box>;
}
