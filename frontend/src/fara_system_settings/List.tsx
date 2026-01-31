import { Badge, Code } from '@mantine/core';
import { IconLock } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';

interface SystemSettingsRecord {
  id: number;
  key: string;
  value: any;
  description: string;
  module: string;
  is_system: boolean;
  cache_ttl: number;
}

/**
 * Форматирует TTL в читаемый вид:
 *  0  → «—»
 * -1  → «∞»
 * 60  → «1м»
 * 3600 → «1ч»
 */
function formatTtl(seconds: number): string {
  if (seconds === 0) return '—';
  if (seconds < 0) return '∞';
  if (seconds < 60) return `${seconds}с`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return s ? `${m}м ${s}с` : `${m}м`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m ? `${h}ч ${m}м` : `${h}ч`;
}

export function ViewListSystemSettings() {
  const { t } = useTranslation('system_settings');

  return (
    <List<SystemSettingsRecord>
      model="system_settings"
      order="asc"
      sort="key">
      <Field name="id" label="ID" />
      <Field
        name="key"
        label={t('fields.key')}
        render={value => <Code>{value}</Code>}
      />
      <Field
        name="value"
        label={t('fields.value')}
        render={value => {
          if (value === null || value === undefined) {
            return <span style={{ color: '#999' }}>null</span>;
          }
          const str = typeof value === 'string' ? value : JSON.stringify(value);
          const truncated = str.length > 60 ? str.slice(0, 60) + '…' : str;
          return <Code>{truncated}</Code>;
        }}
      />
      <Field
        name="module"
        label={t('fields.module')}
        render={value => (
          <Badge size="sm" variant="light" color="blue">
            {value || 'general'}
          </Badge>
        )}
      />
      <Field name="description" label={t('fields.description')} />
      <Field
        name="cache_ttl"
        label={t('fields.cache_ttl')}
        render={(value: number) => {
          const label = formatTtl(value ?? 0);
          const color = value === 0 ? 'gray' : value < 0 ? 'green' : 'blue';
          return (
            <Badge size="sm" variant="light" color={color}>
              {label}
            </Badge>
          );
        }}
      />
      <Field
        name="is_system"
        label={t('fields.is_system')}
        render={value =>
          value ? (
            <Badge
              size="sm"
              color="red"
              variant="light"
              leftSection={<IconLock size={10} />}>
              {t('list.system')}
            </Badge>
          ) : null
        }
      />
    </List>
  );
}
