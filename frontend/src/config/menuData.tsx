/**
 * Дерево меню навигации. Единственный источник правды.
 *
 * Как пользоваться:
 *   { model: 'contact' }                        — ссылка на модель из modelsConfig
 *   { to: '/chat', id, labelKey, label? }       — произвольная ссылка
 *   { id, Icon, labelKey, submenus: [...] }     — подкатегория (вложенный список)
 *   { group: 'communication', submenus: [...] } — корневая группа (из MenuGroups)
 *
 * Чтобы добавить пункт — впишите в нужную группу/категорию.
 * Чтобы перенести — переставьте строку.
 * Чтобы скрыть — удалите строку.
 *
 * Вся инфраструктура (типы, резолверы, buildMenu, getVisibleMenuItems)
 * вынесена в menuHelpers.tsx — здесь только конфигурация.
 */

import {
  IconShieldLock,
  IconSettings,
  IconUsers,
  IconComponents,
  IconMessage,
  IconWorld,
} from '@tabler/icons-react';

import {
  buildMenu,
  getVisibleMenuItems as _getVisibleMenuItems,
  type GroupConfig,
  type MenuGroup,
  type MenuCategory,
  type MenuSimple,
} from '../components/NavbarMenu/menuHelpers';

import { RoleRecord } from '@/types/records';

// Реэкспорт типов и type-guards — чтобы существующие импорты из menuData
// продолжали работать без изменений.
export type { MenuGroup, MenuCategory, MenuSimple };
export {
  isMenuGroup,
  isMenuCategory,
  isMenuSimple,
} from '../components/NavbarMenu/menuHelpers';

/* ============================================================
 * ДЕРЕВО МЕНЮ
 * ============================================================ */

const menuTree: GroupConfig[] = [
  {
    group: 'communication',
    submenus: [
      {
        id: 'category_chat_internal',
        Icon: IconMessage,
        label: 'Внутренние',
        labelKey: 'chat:menu.internal',
        submenus: [
          {
            id: 'menu_chat_internal_all',
            to: '/chat?is_internal=true',
            label: 'Все',
            labelKey: 'chat:menu.all',
          },
          {
            id: 'menu_chat_internal_direct',
            to: '/chat?is_internal=true&chat_type=direct',
            label: 'Личные',
            labelKey: 'chat:menu.direct',
          },
          {
            id: 'menu_chat_internal_groups',
            to: '/chat?is_internal=true&chat_type=group',
            label: 'Группы',
            labelKey: 'chat:menu.groups',
          },
        ],
      },
      {
        id: 'category_chat_external',
        Icon: IconWorld,
        label: 'Внешние',
        labelKey: 'chat:menu.external',
        submenus: [
          {
            id: 'menu_chat_external_all',
            to: '/chat?is_internal=false',
            label: 'Все',
            labelKey: 'chat:menu.all',
          },
          {
            id: 'menu_chat_telegram',
            to: '/chat?is_internal=false&connector_type=telegram',
            label: 'Telegram',
            labelKey: 'chat:menu.telegram',
          },
          {
            id: 'menu_chat_whatsapp',
            to: '/chat?is_internal=false&connector_type=whatsapp',
            label: 'WhatsApp',
            labelKey: 'chat:menu.whatsapp',
          },
          {
            id: 'menu_chat_email',
            to: '/chat?is_internal=false&connector_type=email',
            label: 'Email',
            labelKey: 'chat:menu.email',
          },
        ],
      },
      // Контакты — прямой доступ из раздела "Общение".
      {
        id: 'category_comm_settings',
        Icon: IconSettings,
        label: 'Настройки',
        labelKey: 'chat:menu.settings',
        defaultCollapsed: true,
        submenus: [
          { model: 'chat_connector' },
          { model: 'chat_external_account' },
          { model: 'chat_external_chat' },
          { model: 'chat_external_message' },
        ],
      },
    ],
  },

  {
    group: 'stock',
    submenus: [{ model: 'products' }, { model: 'category' }, { model: 'uom' }],
  },

  {
    group: 'contacts',
    submenus: [
      { model: 'partners' },
      { model: 'contact' },
      { model: 'contact_type' },
    ],
  },

  {
    group: 'crm',
    submenus: [
      { model: 'leads' },
      { model: 'lead_stage' },
      { model: 'team_crm' },
    ],
  },

  {
    group: 'projects',
    submenus: [
      { model: 'tasks' },
      { model: 'project' },
      {
        id: 'category_proj_settings',
        Icon: IconSettings,
        label: 'Настройки',
        labelKey: 'tasks:menu.task_stage',
        defaultCollapsed: true,
        submenus: [{ model: 'task_stage' }, { model: 'task_tag' }],
      },
    ],
  },

  {
    group: 'activity',
    submenus: [
      { model: 'activity' },
      {
        id: 'category_activity_settings',
        Icon: IconSettings,
        label: 'Настройки',
        labelKey: 'common:menu.settings',
        defaultCollapsed: true,
        submenus: [{ model: 'activity_type' }],
      },
    ],
  },

  {
    group: 'sales',
    submenus: [
      { model: 'sales' },
      // { model: 'sale_line' },
      { model: 'sale_stage' },
      { model: 'tax' },
      { model: 'contract' },
    ],
  },

  {
    group: 'telephony',
    submenus: [
      {
        id: 'menu_calls',
        to: '/calls',
        label: 'Звонки',
        labelKey: 'common:menu.calls',
      },
      {
        id: 'menu_phone_numbers',
        to: '/phone_numbers',
        label: 'Номера',
        labelKey: 'common:menu.phoneNumbers',
      },
      {
        id: 'menu_call_events',
        to: '/call_events',
        label: 'События',
        labelKey: 'common:menu.callEvents',
      },
      {
        id: 'menu_call_sources',
        to: '/call_sources',
        label: 'Источники',
        labelKey: 'common:menu.callSources',
      },
    ],
  },

  {
    group: 'files',
    submenus: [
      { model: 'attachments' },
      { model: 'attachments_storage' },
      { model: 'attachments_route' },
      { model: 'attachments_cache' },
    ],
  },

  {
    group: 'settings',
    submenus: [
      {
        id: 'category_users',
        Icon: IconUsers,
        label: 'Пользователи',
        labelKey: 'users:menu.users',
        submenus: [{ model: 'users' }, { model: 'company' }],
      },
      {
        id: 'category_security',
        Icon: IconShieldLock,
        label: 'Безопасность',
        labelKey: 'security:menu.security',
        submenus: [
          { model: 'roles' },
          { model: 'rules' },
          { model: 'access_list' },
          { model: 'sessions' },
        ],
      },
      {
        id: 'category_other',
        Icon: IconComponents,
        label: 'Прочее',
        labelKey: 'security:menu.other',
        submenus: [
          { model: 'apps' },
          { model: 'language' },
          { model: 'models' },
          { model: 'cron_job' },
          { model: 'saved_filters' },
          { model: 'system_settings' },
          { model: 'report_template' },
        ],
      },
    ],
  },
];

/* ============================================================
 * ЭКСПОРТЫ
 * ============================================================ */

export const items: MenuGroup[] = buildMenu(menuTree);

// Обёртка: сохраняем прежнюю сигнатуру (userRoles, isAdmin) для совместимости
// с существующими вызывающими компонентами.
export function getVisibleMenuItems(
  userRoles: RoleRecord[] = [],
  isAdmin: boolean = false,
): MenuGroup[] {
  return _getVisibleMenuItems(items, userRoles, isAdmin);
}
