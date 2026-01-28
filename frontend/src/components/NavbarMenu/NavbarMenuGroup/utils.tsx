import { useTranslation } from 'react-i18next';
import { NavbarMenuCategory } from '../NavbarMenuCategory/NavbarMenuCategory';
import { NavbarMenuSimple } from '../NavbarMenuSimple/NavbarMenuSimple';
import {
  MenuCategory,
  MenuSimple,
  isMenuCategory,
  isMenuSimple,
} from '../menuData';

export const scrollToLink = (linkRef: React.RefObject<HTMLButtonElement>) => {
  const element = linkRef.current;

  if (!element) {
    return;
  }

  const height = typeof window !== 'undefined' ? window.innerHeight : 0;
  const { top, bottom } = element.getBoundingClientRect();

  if (top < 60 || bottom > height) {
    element.scrollIntoView({ block: 'center' });
  }
};

// Компонент-обёртка для перевода simple меню
function TranslatedMenuSimple({ menu }: { menu: MenuSimple }) {
  const { t } = useTranslation();
  const displayLabel = menu.labelKey
    ? t(menu.labelKey, { defaultValue: menu.label })
    : menu.label;

  return (
    <NavbarMenuSimple key={menu.id} to={menu.to}>
      {displayLabel}
    </NavbarMenuSimple>
  );
}

export function treeMenuComponents(menus: (MenuSimple | MenuCategory)[]) {
  const menuCategories = menus.filter(isMenuCategory);
  const allMenusCategory = menuCategories.map(menu => (
    <NavbarMenuCategory
      Icon={menu.Icon}
      key={menu.id}
      label={menu.label}
      labelKey={menu.labelKey}
      submenus={menu.submenus}
      defaultCollapsed={menu.defaultCollapsed}
    />
  ));

  const menuSimples = menus.filter(isMenuSimple);
  const allMenusSimple = menuSimples.map(menu => (
    <TranslatedMenuSimple key={menu.id} menu={menu} />
  ));
  return [...allMenusSimple, ...allMenusCategory];
}

export function hasActiveLink(
  submenus: (MenuSimple | MenuCategory)[],
  pathname: string,
): boolean {
  if (submenus) {
    // в каждой категории пройти по дочерним
    const menuCategories = submenus.filter(isMenuCategory);
    if (
      menuCategories.some(menuCategory =>
        hasActiveLink(menuCategory.submenus, pathname),
      )
    ) {
      return true;
    }

    // также проверить все простые меню
    const menuSimples = submenus.filter(isMenuSimple);
    if (menuSimples.some(menuSimple => pathname.includes(menuSimple.to))) {
      return true;
    }
  }
  return false;
}
