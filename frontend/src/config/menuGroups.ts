import {
  IconChartBar,
  IconUsers,
  IconGridScan,
  IconSettings,
  IconFiles,
  IconHeartHandshake,
  IconMessage,
  IconPhoneCall,
} from '@tabler/icons-react';

export const MenuGroups = {
  communication: {
    id: 'category_communication',
    label: 'Общение',
    labelKey: 'common:menu.communication',
    Icon: IconMessage,
    order: 10,
  },
  stock: {
    id: 'category_stock',
    label: 'Склад',
    labelKey: 'common:menu.stock',
    Icon: IconGridScan,
    order: 20,
  },
  contacts: {
    id: 'category_contacts',
    label: 'Партнеры',
    labelKey: 'common:menu.contacts',
    Icon: IconUsers,
    order: 30,
  },
  crm: {
    id: 'category_crm',
    label: 'CRM',
    labelKey: 'common:menu.crm',
    Icon: IconHeartHandshake,
    order: 40,
  },
  sales: {
    id: 'category_sales',
    label: 'Продажи',
    labelKey: 'common:menu.sales',
    Icon: IconChartBar,
    order: 50,
  },
  telephony: {
    id: 'category_telephony',
    label: 'Телефония',
    labelKey: 'common:menu.telephony',
    Icon: IconPhoneCall,
    order: 60,
  },
  files: {
    id: 'category_files',
    label: 'Файлы',
    labelKey: 'common:menu.files',
    Icon: IconFiles,
    order: 70,
  },
  settings: {
    id: 'category_settings',
    label: 'Настройки',
    labelKey: 'common:menu.settings',
    Icon: IconSettings,
    order: 90,
  },
} as const;

export type MenuGroup = (typeof MenuGroups)[keyof typeof MenuGroups];
