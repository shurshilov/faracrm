// Contact type configurations
// Should match backend CONTACT_TYPE_CONFIG

import { ContactType, ContactTypeConfig } from './types';

export const CONTACT_TYPE_CONFIG: Record<ContactType, Omit<ContactTypeConfig, 'name'>> = {
  phone: {
    label: 'Телефон',
    icon: 'phone',
    placeholder: '+7 999 123-45-67',
    pattern: '^[\\+]?[0-9\\s\\-\\(\\)]{10,20}$',
    sequence: 1,
    connectorTypes: ['whatsapp', 'viber', 'sms'],
  },
  email: {
    label: 'Email',
    icon: 'mail',
    placeholder: 'example@mail.com',
    pattern: '^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$',
    sequence: 2,
    connectorTypes: ['email'],
  },
  telegram: {
    label: 'Telegram',
    icon: 'send',
    placeholder: '@username',
    pattern: '^@?[a-zA-Z][a-zA-Z0-9_]{4,31}$',
    sequence: 3,
    connectorTypes: ['telegram'],
  },
  avito: {
    label: 'Avito',
    icon: 'shopping-bag',
    placeholder: 'ID пользователя',
    pattern: '^\\d+$',
    sequence: 4,
    connectorTypes: ['avito'],
  },
  vk: {
    label: 'ВКонтакте',
    icon: 'message-circle',
    placeholder: 'vk.com/username',
    pattern: '^(vk\\.com\\/)?[a-zA-Z0-9_\\.]+$',
    sequence: 5,
    connectorTypes: ['vk'],
  },
  instagram: {
    label: 'Instagram',
    icon: 'camera',
    placeholder: '@username',
    pattern: '^@?[a-zA-Z0-9_\\.]{1,30}$',
    sequence: 6,
    connectorTypes: ['instagram'],
  },
};

/**
 * Определить тип контакта по значению
 */
export function detectContactType(value: string): ContactType | null {
  const trimmed = value.trim();
  
  // Сортируем по sequence
  const sortedTypes = (Object.entries(CONTACT_TYPE_CONFIG) as [ContactType, Omit<ContactTypeConfig, 'name'>][])
    .sort((a, b) => a[1].sequence - b[1].sequence);
  
  for (const [type, config] of sortedTypes) {
    try {
      const regex = new RegExp(config.pattern);
      if (regex.test(trimmed)) {
        return type;
      }
    } catch {
      // Invalid regex, skip
    }
  }
  
  return null;
}

/**
 * Получить конфиг типа контакта
 */
export function getContactTypeConfig(type: ContactType): ContactTypeConfig {
  const config = CONTACT_TYPE_CONFIG[type];
  return {
    name: type,
    ...config,
  };
}

/**
 * Получить все типы контактов отсортированные по sequence
 */
export function getAllContactTypes(): ContactTypeConfig[] {
  return (Object.entries(CONTACT_TYPE_CONFIG) as [ContactType, Omit<ContactTypeConfig, 'name'>][])
    .sort((a, b) => a[1].sequence - b[1].sequence)
    .map(([name, config]) => ({ name, ...config }));
}
