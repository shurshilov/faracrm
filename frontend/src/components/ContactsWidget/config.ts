// Contact type configurations — loaded from API (table contact_type)

import { ContactType, ContactTypeConfig } from './types';
import { useSearchQuery } from '@/services/api/crudApi';

/**
 * Hook: загрузить все типы контактов из БД
 * connector_ids — One2many на chat_connector (через contact_type_id FK)
 */
export function useContactTypes(): {
  contactTypes: ContactTypeConfig[];
  isLoading: boolean;
} {
  const { data, isLoading } = useSearchQuery({
    model: 'contact_type',
    fields: [
      'id',
      'name',
      'label',
      'icon',
      'color',
      'placeholder',
      'pattern',
      'sequence',
      'connector_ids',
    ],
    filter: [['active', '=', true]],
    sort: 'sequence',
    limit: 100,
  });

  const contactTypes: ContactTypeConfig[] = (data?.data || []).map(
    (ct: any) => {
      // connector_ids — массив объектов коннекторов
      const connectorTypes: string[] = [];
      if (Array.isArray(ct.connector_ids)) {
        for (const conn of ct.connector_ids) {
          if (conn?.type && conn?.active !== false) {
            connectorTypes.push(conn.type);
          }
        }
      }

      return {
        id: ct.id,
        name: ct.name,
        label: ct.label || ct.name,
        icon: ct.icon || '',
        color: ct.color || 'gray',
        placeholder: ct.placeholder || '',
        pattern: ct.pattern || '',
        sequence: ct.sequence || 10,
        connectorTypes,
      };
    },
  );

  return { contactTypes, isLoading };
}

/**
 * Определить тип контакта по значению (клиентская логика с regex)
 */
export function detectContactType(
  value: string,
  contactTypes: ContactTypeConfig[],
): ContactType | null {
  const trimmed = value.trim();

  const sorted = [...contactTypes].sort((a, b) => a.sequence - b.sequence);

  for (const ct of sorted) {
    if (ct.pattern) {
      try {
        const regex = new RegExp(ct.pattern);
        if (regex.test(trimmed)) {
          return ct.name;
        }
      } catch {
        // Invalid regex, skip
      }
    }
  }

  return null;
}

/**
 * Получить конфиг конкретного типа из массива
 */
export function getContactTypeConfig(
  type: ContactType,
  contactTypes: ContactTypeConfig[],
): ContactTypeConfig | undefined {
  return contactTypes.find(ct => ct.name === type);
}
