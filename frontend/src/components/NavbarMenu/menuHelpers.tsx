/**
 * Инфраструктура для построения меню навигации.
 *
 * Здесь живут:
 * - Типы MenuGroup / MenuCategory / MenuSimple (что рендерит UI).
 * - Типы GroupConfig / CategoryConfig / MenuItemConfig (что пишется в menuTree).
 * - Хелперы формирования лейблов и labelKey для моделей.
 * - Резолверы: из конфига → в структуру для UI.
 * - buildMenu() — собирает дерево в конечный массив для items.
 * - getVisibleMenuItems() — фильтр по ролям на всех трёх уровнях
 *   (группа / категория / пункт).
 *
 * Дерево меню описывается в menuData.tsx — там только конфигурация.
 */

import { Icon as IconType } from '@tabler/icons-react';
import { modelsConfig } from '@/config/models';
import { MenuGroups } from '@/config/menuGroups';
import { RoleRecord } from '@/types/records';

/* ============================================================
 * ТИПЫ UI: что рендерит NavbarMenu
 * ============================================================ */

// Общее поле для ограничения видимости на всех уровнях.
// adminOnly: true   — только админу.
// visibleForRoles — список кодов ролей (user видит если у него хотя бы одна).
// Не заданы оба → видно всем.
interface VisibilityProps {
  visibleForRoles?: string[];
  adminOnly?: boolean;
}

export interface MenuGroup extends VisibilityProps {
  type: 'group';
  label: string;
  labelKey?: string;
  id: string;
  Icon: IconType;
  submenus?: (MenuSimple | MenuCategory)[];
  to?: string;
  order?: number;
}

export interface MenuCategory extends VisibilityProps {
  type: 'category';
  label: string;
  labelKey?: string;
  id: string;
  Icon: IconType;
  submenus: MenuSimple[];
  defaultCollapsed?: boolean;
}

export interface MenuSimple extends VisibilityProps {
  type: 'simple';
  label: string;
  labelKey?: string;
  id: string;
  to: string;
}

export const isMenuGroup = (menu: MenuGroup): menu is MenuGroup =>
  menu.type === 'group';
export const isMenuCategory = (
  menu: MenuCategory | MenuSimple,
): menu is MenuCategory => menu.type === 'category';
export const isMenuSimple = (
  menu: MenuCategory | MenuSimple,
): menu is MenuSimple => menu.type === 'simple';

/* ============================================================
 * ТИПЫ КОНФИГА: что пишется в menuTree (menuData.tsx)
 *
 * Пример:
 *   { model: 'contact' }                        → MenuSimple из modelsConfig
 *   { to: '/chat', labelKey: '...', id: '...' } → MenuSimple custom
 *   { id, Icon, submenus: [...] }               → MenuCategory
 *   { group: 'communication', submenus: [...] } → MenuGroup из MenuGroups
 *
 * На любом уровне можно добавить visibleForRoles / adminOnly.
 * ============================================================ */

export type MenuItemConfig = VisibilityProps &
  (
    | { model: string }
    | {
        to: string;
        id: string;
        labelKey?: string;
        label?: string;
      }
  );

export type CategoryConfig = VisibilityProps & {
  id: string;
  Icon: IconType;
  labelKey?: string;
  label?: string;
  defaultCollapsed?: boolean;
  submenus: MenuItemConfig[];
};

export type GroupConfig = {
  group: keyof typeof MenuGroups;
  submenus: (MenuItemConfig | CategoryConfig)[];
};

/* ============================================================
 * ЛЕЙБЛЫ И I18N NAMESPACE ДЛЯ МОДЕЛЕЙ
 * ============================================================ */

function formatModelName(modelName: string): string {
  return modelName
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

const modelToNamespace: Record<string, string> = {
  chat_connector: 'chat',
  chat_external_account: 'chat',
  chat_external_chat: 'chat',
  chat_external_message: 'chat',
  products: 'products',
  category: 'products',
  uom: 'products',
  partners: 'partners',
  contact: 'partners',
  contact_type: 'partners',
  sales: 'sales',
  sale_line: 'sales',
  sale_stage: 'sales',
  tax: 'sales',
  contract: 'sales',
  leads: 'leads',
  lead_stage: 'leads',
  team_crm: 'leads',
  company: 'company',
  attachments: 'attachments',
  attachments_storage: 'attachments',
  attachments_route: 'attachments',
  attachments_cache: 'attachments',
  users: 'users',
  roles: 'security',
  rules: 'security',
  access_list: 'security',
  sessions: 'security',
  models: 'security',
  apps: 'security',
  language: 'languages',
  cron_job: 'cron',
  saved_filters: 'saved_filters',
  system_settings: 'system_settings',
  report_template: 'reports',
  tasks: 'tasks',
  project: 'tasks',
  task_stage: 'tasks',
  task_tag: 'tasks',
  activity: 'activity',
  activity_type: 'activity',
};

const modelLabels: Record<string, string> = {
  contact: 'Контакты',
  contact_type: 'Типы контактов',
  partners: 'Партнёры',
  contract: 'Договоры',
  report_template: 'Шаблоны отчётов',
};

/* ============================================================
 * РЕЗОЛВЕРЫ: config → UI структура
 * ============================================================ */

function extractVisibility(cfg: VisibilityProps): VisibilityProps {
  return {
    visibleForRoles: cfg.visibleForRoles,
    adminOnly: cfg.adminOnly,
  };
}

function resolveModelMenuItem(
  modelName: string,
  vis: VisibilityProps,
): MenuSimple | null {
  if (!modelsConfig[modelName]) {
    console.warn(
      `[menu] model "${modelName}" не найдена в modelsConfig — пункт пропущен`,
    );
    return null;
  }
  const namespace = modelToNamespace[modelName] || modelName;
  return {
    type: 'simple',
    id: `menu_${modelName}`,
    to: `/${modelName}`,
    label: modelLabels[modelName] || formatModelName(modelName),
    labelKey: `${namespace}:menu.${modelName}`,
    ...vis,
  };
}

function resolveMenuItem(item: MenuItemConfig): MenuSimple | null {
  const vis = extractVisibility(item);
  if ('model' in item) {
    return resolveModelMenuItem(item.model, vis);
  }
  return {
    type: 'simple',
    id: item.id,
    to: item.to,
    label: item.label || item.id,
    labelKey: item.labelKey,
    ...vis,
  };
}

function resolveCategory(cat: CategoryConfig): MenuCategory {
  return {
    type: 'category',
    id: cat.id,
    Icon: cat.Icon,
    label: cat.label || '',
    labelKey: cat.labelKey,
    defaultCollapsed: cat.defaultCollapsed,
    submenus: cat.submenus
      .map(resolveMenuItem)
      .filter((x): x is MenuSimple => x !== null),
    ...extractVisibility(cat),
  };
}

function resolveGroup(cfg: GroupConfig): MenuGroup {
  const meta = MenuGroups[cfg.group];
  return {
    type: 'group',
    id: meta.id,
    Icon: meta.Icon,
    label: meta.label,
    labelKey: meta.labelKey,
    order: meta.order,
    // visibleForRoles для группы берём из MenuGroups (как и раньше)
    visibleForRoles: (meta as any).visibleForRoles,
    submenus: cfg.submenus
      .map(sub => {
        if ('Icon' in sub && 'submenus' in sub) {
          return resolveCategory(sub as CategoryConfig);
        }
        return resolveMenuItem(sub as MenuItemConfig);
      })
      .filter((x): x is MenuSimple | MenuCategory => x !== null),
  };
}

function pruneEmpty(groups: MenuGroup[]): MenuGroup[] {
  for (const group of groups) {
    group.submenus = (group.submenus || []).filter(sub => {
      if (sub.type === 'category') {
        return sub.submenus.length > 0;
      }
      return true;
    });
  }
  return groups.filter(g => (g.submenus?.length || 0) > 0);
}

/* ============================================================
 * ПРОВЕРКА ВИДИМОСТИ
 * ============================================================ */

function isVisible(
  node: VisibilityProps,
  userRolesSet: Set<string>,
  isAdmin: boolean,
): boolean {
  // adminOnly — только админ
  if (node.adminOnly) return isAdmin;

  // Нет ограничений — видно всем авторизованным
  if (!node.visibleForRoles || node.visibleForRoles.length === 0) return true;

  // Админ видит всё
  if (isAdmin) return true;

  // Проверяем пересечение ролей
  return node.visibleForRoles.some(role => userRolesSet.has(role));
}

/* ============================================================
 * PUBLIC API
 * ============================================================ */

export function buildMenu(tree: GroupConfig[]): MenuGroup[] {
  return pruneEmpty(
    tree.map(resolveGroup).sort((a, b) => (a.order || 0) - (b.order || 0)),
  );
}

/**
 * Фильтрует меню по ролям пользователя.
 * Применяет visibleForRoles / adminOnly на всех трёх уровнях:
 * группа → категория → пункт.
 * Если после фильтрации категория/группа становится пустой — она скрывается.
 */
export function getVisibleMenuItems(
  items: MenuGroup[],
  userRoles: RoleRecord[] = [],
  isAdmin: boolean = false,
): MenuGroup[] {
  const userRolesSet = new Set(userRoles.map(item => item.code));

  const result: MenuGroup[] = [];

  for (const group of items) {
    if (!isVisible(group, userRolesSet, isAdmin)) continue;

    const filteredSubmenus = (group.submenus || [])
      .map(sub => {
        if (sub.type === 'category') {
          if (!isVisible(sub, userRolesSet, isAdmin)) return null;
          const filteredItems = sub.submenus.filter(item =>
            isVisible(item, userRolesSet, isAdmin),
          );
          if (filteredItems.length === 0) return null;
          return { ...sub, submenus: filteredItems };
        }
        // simple
        if (!isVisible(sub, userRolesSet, isAdmin)) return null;
        return sub;
      })
      .filter((x): x is MenuSimple | MenuCategory => x !== null);

    if (filteredSubmenus.length === 0) continue;

    result.push({ ...group, submenus: filteredSubmenus });
  }

  return result;
}
