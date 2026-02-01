import {
  IconShieldLock,
  IconSettings,
  IconUsers,
  IconComponents,
  IconMessage,
  IconWorld,
  Icon as IconType,
} from '@tabler/icons-react';
import { modelsConfig } from '@/config/models';
import { MenuGroups } from '@/config/menuGroups';

export interface MenuGroup {
  type: 'group';
  label: string;
  labelKey?: string;
  id: string;
  Icon: IconType;
  submenus?: (MenuSimple | MenuCategory)[];
  to?: string;
  order?: number;
}

export interface MenuCategory {
  type: 'category';
  label: string;
  labelKey?: string;
  id: string;
  Icon: IconType;
  submenus: MenuSimple[];
  defaultCollapsed?: boolean;
}

export interface MenuSimple {
  type: 'simple';
  label: string;
  labelKey?: string;
  id: string;
  to: string;
}

// Функции-предикаты
export const isMenuGroup = (menu: MenuGroup): menu is MenuGroup =>
  menu.type === 'group';

export const isMenuCategory = (
  menu: MenuCategory | MenuSimple,
): menu is MenuCategory => menu.type === 'category';

export const isMenuSimple = (
  menu: MenuCategory | MenuSimple,
): menu is MenuSimple => menu.type === 'simple';

// Хелпер: капитализация имени модели
function formatModelName(modelName: string): string {
  return modelName
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

// Маппинг модели на namespace i18n
const modelToNamespace: Record<string, string> = {
  // Chat
  chat_connector: 'chat',
  chat_external_account: 'chat',
  chat_external_chat: 'chat',
  chat_external_message: 'chat',
  // Products
  products: 'products',
  category: 'products',
  uom: 'products',
  // Partners
  partners: 'partners',
  contact: 'partners',
  contact_type: 'partners',
  // Sales
  sale: 'sales',
  sale_line: 'sales',
  sale_stage: 'sales',
  tax: 'sales',
  // CRM/Leads
  lead: 'leads',
  lead_stage: 'leads',
  team_crm: 'leads',
  // Company
  company: 'company',
  // Attachments
  attachments: 'attachments',
  attachments_storage: 'attachments',
  attachments_route: 'attachments',
  // Users
  users: 'users',
  // Security
  roles: 'security',
  rules: 'security',
  access_list: 'security',
  sessions: 'security',
  models: 'security',
  apps: 'security',
  // Languages
  language: 'languages',
  // Cron
  cron_job: 'cron',
  // Saved Filters
  saved_filters: 'saved_filters',
  // System Settings
  system_settings: 'system_settings',
  // Tasks & Projects
  task: 'tasks',
  project: 'tasks',
  task_stage: 'tasks',
  task_tag: 'tasks',
  // Activity
  activity: 'activity',
  activity_type: 'activity',
};

// Кастомные лейблы для моделей (вместо автогенерации)
const modelLabels: Record<string, string> = {
  contact: 'Контакты',
  contact_type: 'Типы контактов',
  partners: 'Партнёры',
};

function getMenuLabelKey(modelName: string): string {
  const namespace = modelToNamespace[modelName] || modelName;
  return `${namespace}:menu.${modelName}`;
}

function getModelLabel(modelName: string): string {
  return modelLabels[modelName] || formatModelName(modelName);
}

// Модели которые идут в категории Settings (вложенные подменю)
const settingsCategories: Record<
  string,
  { label: string; labelKey: string; Icon: IconType; models: string[] }
> = {
  users: {
    label: 'Пользователи',
    labelKey: 'users:menu.users',
    Icon: IconUsers,
    models: ['users', 'company'],
  },
  security: {
    label: 'Безопасность',
    labelKey: 'security:menu.security',
    Icon: IconShieldLock,
    models: ['roles', 'rules', 'access_list', 'sessions'],
  },
  other: {
    label: 'Прочее',
    labelKey: 'security:menu.other',
    Icon: IconComponents,
    models: [
      'apps',
      'language',
      'models',
      'cron_job',
      'saved_filters',
      'system_settings',
    ],
  },
};

// Категории для Communication (вложенные подменю)
const communicationCategories: Record<
  string,
  {
    label: string;
    labelKey: string;
    Icon: IconType;
    models: string[];
    defaultCollapsed?: boolean;
  }
> = {
  settings: {
    label: 'Настройки',
    labelKey: 'chat:menu.settings',
    Icon: IconSettings,
    models: [
      'chat_connector',
      'chat_external_account',
      'chat_external_chat',
      'chat_external_message',
    ],
    defaultCollapsed: true,
  },
};

// Категории для Projects (вложенные подменю)
const projectsCategories: Record<
  string,
  {
    label: string;
    labelKey: string;
    Icon: IconType;
    models: string[];
    defaultCollapsed?: boolean;
  }
> = {
  settings: {
    label: 'Настройки',
    labelKey: 'tasks:menu.task_stage',
    Icon: IconSettings,
    models: ['task_stage', 'task_tag'],
    defaultCollapsed: true,
  },
};

// Категории для Activity (вложенные подменю)
const activityCategories: Record<
  string,
  {
    label: string;
    labelKey: string;
    Icon: IconType;
    models: string[];
    defaultCollapsed?: boolean;
  }
> = {
  settings: {
    label: 'Настройки',
    labelKey: 'common:menu.settings',
    Icon: IconSettings,
    models: ['activity_type'],
    defaultCollapsed: true,
  },
};

// Статические пункты меню (не привязаны к моделям)
// Комбо-архитектура: Internal (Личные, Группы) / External (Telegram, WhatsApp, Email)
const staticMenuItems: Record<string, (MenuSimple | MenuCategory)[]> = {
  [MenuGroups.communication.id]: [
    // Internal чаты
    {
      type: 'category',
      label: 'Внутренние',
      labelKey: 'chat:menu.internal',
      id: 'category_chat_internal',
      Icon: IconMessage,
      submenus: [
        {
          type: 'simple',
          to: '/chat?is_internal=true',
          label: 'Все',
          labelKey: 'chat:menu.all',
          id: 'menu_chat_internal_all',
        },
        {
          type: 'simple',
          to: '/chat?is_internal=true&chat_type=direct',
          label: 'Личные',
          labelKey: 'chat:menu.direct',
          id: 'menu_chat_internal_direct',
        },
        {
          type: 'simple',
          to: '/chat?is_internal=true&chat_type=group',
          label: 'Группы',
          labelKey: 'chat:menu.groups',
          id: 'menu_chat_internal_groups',
        },
      ],
    },
    // External чаты
    {
      type: 'category',
      label: 'Внешние',
      labelKey: 'chat:menu.external',
      id: 'category_chat_external',
      Icon: IconWorld,
      submenus: [
        {
          type: 'simple',
          to: '/chat?is_internal=false',
          label: 'Все',
          labelKey: 'chat:menu.all',
          id: 'menu_chat_external_all',
        },
        {
          type: 'simple',
          to: '/chat?is_internal=false&connector_type=telegram',
          label: 'Telegram',
          labelKey: 'chat:menu.telegram',
          id: 'menu_chat_telegram',
        },
        {
          type: 'simple',
          to: '/chat?is_internal=false&connector_type=whatsapp',
          label: 'WhatsApp',
          labelKey: 'chat:menu.whatsapp',
          id: 'menu_chat_whatsapp',
        },
        {
          type: 'simple',
          to: '/chat?is_internal=false&connector_type=email',
          label: 'Email',
          labelKey: 'chat:menu.email',
          id: 'menu_chat_email',
        },
      ],
    },
  ],
  [MenuGroups.telephony.id]: [
    {
      type: 'simple',
      to: '/calls',
      label: 'Звонки',
      labelKey: 'common:menu.calls',
      id: 'menu_calls',
    },
    {
      type: 'simple',
      to: '/phone_numbers',
      label: 'Номера',
      labelKey: 'common:menu.phoneNumbers',
      id: 'menu_phone_numbers',
    },
    {
      type: 'simple',
      to: '/call_events',
      label: 'События',
      labelKey: 'common:menu.callEvents',
      id: 'menu_call_events',
    },
    {
      type: 'simple',
      to: '/call_sources',
      label: 'Источники',
      labelKey: 'common:menu.callSources',
      id: 'menu_call_sources',
    },
  ],
};

// Генерируем меню из modelsConfig
function generateMenuItems(): MenuGroup[] {
  const groupsMap = new Map<string, MenuGroup>();

  // Инициализируем группы из MenuGroups
  Object.values(MenuGroups).forEach(group => {
    groupsMap.set(group.id, {
      type: 'group',
      label: group.label,
      labelKey: group.labelKey,
      id: group.id,
      Icon: group.Icon,
      order: group.order,
      submenus: [],
    });
  });

  // Добавляем статические пункты меню
  Object.entries(staticMenuItems).forEach(([groupId, items]) => {
    const group = groupsMap.get(groupId);
    if (group) {
      group.submenus = [...(group.submenus || []), ...items];
    }
  });

  // Собираем модели Settings отдельно
  const settingsModels = new Set(
    Object.values(settingsCategories).flatMap(cat => cat.models),
  );

  // Собираем модели Communication settings отдельно
  const communicationModels = new Set(
    Object.values(communicationCategories).flatMap(cat => cat.models),
  );

  // Собираем модели Projects settings отдельно
  const projectsSettingsModels = new Set(
    Object.values(projectsCategories).flatMap(cat => cat.models),
  );

  // Собираем модели Activity settings отдельно
  const activityModels = new Set(
    Object.values(activityCategories).flatMap(cat => cat.models),
  );

  // Добавляем модели в группы
  Object.entries(modelsConfig).forEach(([modelName, config]) => {
    if (!config.menu) return;

    // Settings обрабатываем отдельно
    if (config.menu.id === MenuGroups.settings.id) {
      return;
    }

    // Communication модели из категорий пропускаем - добавим их через категории
    if (
      config.menu.id === MenuGroups.communication.id &&
      communicationModels.has(modelName)
    ) {
      return;
    }

    // Projects settings модели пропускаем - добавим через категории
    if (
      config.menu.id === MenuGroups.projects.id &&
      projectsSettingsModels.has(modelName)
    ) {
      return;
    }

    // Activity модели из категорий пропускаем - добавим их через категории
    if (
      config.menu.id === MenuGroups.activity.id &&
      activityModels.has(modelName)
    ) {
      return;
    }

    const group = groupsMap.get(config.menu.id);
    if (!group) return;

    group.submenus = group.submenus || [];
    group.submenus.push({
      type: 'simple',
      label: getModelLabel(modelName),
      labelKey: getMenuLabelKey(modelName),
      id: `menu_${modelName}`,
      to: `/${modelName}`,
    });
  });

  // Формируем Settings с категориями
  const settingsGroup = groupsMap.get(MenuGroups.settings.id);
  if (settingsGroup) {
    settingsGroup.submenus = Object.entries(settingsCategories).map(
      ([catId, catConfig]) => ({
        type: 'category' as const,
        label: catConfig.label,
        labelKey: catConfig.labelKey,
        id: `category_${catId}`,
        Icon: catConfig.Icon,
        submenus: catConfig.models
          .filter(modelName => modelsConfig[modelName]) // только существующие модели
          .map(modelName => ({
            type: 'simple' as const,
            label: getModelLabel(modelName),
            labelKey: getMenuLabelKey(modelName),
            id: `menu_${modelName}`,
            to: `/${modelName}`,
          })),
      }),
    );
  }

  // Формируем Communication с категориями (добавляем в конец)
  const communicationGroup = groupsMap.get(MenuGroups.communication.id);
  if (communicationGroup) {
    const categories = Object.entries(communicationCategories).map(
      ([catId, catConfig]) => ({
        type: 'category' as const,
        label: catConfig.label,
        labelKey: catConfig.labelKey,
        id: `category_comm_${catId}`,
        Icon: catConfig.Icon,
        defaultCollapsed: catConfig.defaultCollapsed,
        submenus: catConfig.models
          .filter(modelName => modelsConfig[modelName])
          .map(modelName => ({
            type: 'simple' as const,
            label: getModelLabel(modelName),
            labelKey: getMenuLabelKey(modelName),
            id: `menu_${modelName}`,
            to: `/${modelName}`,
          })),
      }),
    );
    // Добавляем категории в конец списка
    communicationGroup.submenus = [
      ...(communicationGroup.submenus || []),
      ...categories,
    ];
  }

  // Формируем Projects с категориями (task_stage, task_tag в свёрнутом подменю)
  const projectsGroup = groupsMap.get(MenuGroups.projects.id);
  if (projectsGroup) {
    const projectCategories = Object.entries(projectsCategories).map(
      ([catId, catConfig]) => ({
        type: 'category' as const,
        label: catConfig.label,
        labelKey: catConfig.labelKey,
        id: `category_proj_${catId}`,
        Icon: catConfig.Icon,
        defaultCollapsed: catConfig.defaultCollapsed,
        submenus: catConfig.models
          .filter(modelName => modelsConfig[modelName])
          .map(modelName => ({
            type: 'simple' as const,
            label: getModelLabel(modelName),
            labelKey: getMenuLabelKey(modelName),
            id: `menu_${modelName}`,
            to: `/${modelName}`,
          })),
      }),
    );
    projectsGroup.submenus = [
      ...(projectsGroup.submenus || []),
      ...projectCategories,
    ];
  }

  // Формируем Activity с категориями (добавляем в конец)
  const activityGroup = groupsMap.get(MenuGroups.activity.id);
  if (activityGroup) {
    const categories = Object.entries(activityCategories).map(
      ([catId, catConfig]) => ({
        type: 'category' as const,
        label: catConfig.label,
        labelKey: catConfig.labelKey,
        id: `category_activity_${catId}`,
        Icon: catConfig.Icon,
        defaultCollapsed: catConfig.defaultCollapsed,
        submenus: catConfig.models
          .filter(modelName => modelsConfig[modelName])
          .map(modelName => ({
            type: 'simple' as const,
            label: getModelLabel(modelName),
            labelKey: getMenuLabelKey(modelName),
            id: `menu_${modelName}`,
            to: `/${modelName}`,
          })),
      }),
    );
    activityGroup.submenus = [...(activityGroup.submenus || []), ...categories];
  }

  // Фильтруем пустые группы и сортируем
  return Array.from(groupsMap.values())
    .filter(group => group.submenus && group.submenus.length > 0)
    .sort((a, b) => (a.order || 0) - (b.order || 0));
}

export const items: MenuGroup[] = generateMenuItems();
