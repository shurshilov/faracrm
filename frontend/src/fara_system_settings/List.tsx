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
