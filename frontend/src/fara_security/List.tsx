import { useState, useCallback } from 'react';
import { Button, Modal, Text, Group } from '@mantine/core';
import { IconLogout } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { Field } from '@/components/List/Field';
import { List } from '@/components/List/List';
import { PermissionsBadges } from '@/components/PermissionsBadges';
import {
  BooleanCell,
  RelationCell,
  DateTimeCell,
} from '@/components/ListCells';
import { SchemaAccessList, SchemaModel } from '@/services/api/access_list';
import { SchemaRole } from '@/services/api/roles';
import { SchemaRule } from '@/services/api/rules';
import {
  SchemaSession,
  useRouteSessionsTerminateAllMutation,
} from '@/services/api/sessions';
import { SchemaApp } from '@/services/api/apps';
import classes from './List.module.css';

export function ViewListApps() {
  const { t } = useTranslation('security');
  
  return (
    <List<SchemaApp> model="apps" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="code" label={t('fields.code')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="active" label={t('fields.active')} render={value => <BooleanCell value={value} />} />
    </List>
  );
}

export function ViewListAccessList() {
  const { t } = useTranslation('security');
  
  return (
    <List<SchemaAccessList> model="access_list" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field
        name="model_id"
        label={t('fields.model_id')}
        render={value => <RelationCell value={value} model="models" />}
      />
      <Field
        name="role_id"
        label={t('fields.role_id')}
        render={value => <RelationCell value={value} model="roles" />}
      />
      <Field
        name="permissions"
        label={t('fields.permissions')}
        virtual
        fields={['perm_create', 'perm_read', 'perm_update', 'perm_delete']}
        render={(_, record) => (
          <PermissionsBadges
            create={record.perm_create}
            read={record.perm_read}
            update={record.perm_update}
            delete={record.perm_delete}
            compact
          />
        )}
      />
    </List>
  );
}

export function ViewListRoles() {
  const { t } = useTranslation('security');
  
  return (
    <List<SchemaRole> model="roles" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field
        name="model_id"
        label={t('fields.model_id')}
        render={value => <RelationCell value={value} model="models" />}
      />
      <Field name="acl_ids" label={t('fields.acl_ids')} />
      <Field name="rule_ids" label={t('fields.rule_ids')} />
      <Field name="user_ids" label={t('fields.user_ids')} />
    </List>
  );
}

export function ViewListRules() {
  const { t } = useTranslation('security');
  
  return (
    <List<SchemaRule> model="rules" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
      <Field name="active" label={t('fields.active')} render={value => <BooleanCell value={value} />} />
      <Field
        name="model_id"
        label={t('fields.model_id')}
        render={value => <RelationCell value={value} model="models" />}
      />
      <Field
        name="role_id"
        label={t('fields.role_id')}
        render={value => <RelationCell value={value} model="roles" />}
      />
      <Field
        name="permissions"
        label={t('fields.permissions')}
        virtual
        fields={['perm_create', 'perm_read', 'perm_update', 'perm_delete']}
        render={(_, record) => (
          <PermissionsBadges
            create={record.perm_create}
            read={record.perm_read}
            update={record.perm_update}
            delete={record.perm_delete}
            compact
          />
        )}
      />
    </List>
  );
}

export function ViewListModels() {
  const { t } = useTranslation('security');
  
  return (
    <List<SchemaModel> model="models" order="desc" sort="id">
      <Field name="id" label={t('fields.id')} />
      <Field name="name" label={t('fields.name')} />
    </List>
  );
}

export function ViewListSessions() {
  const { t } = useTranslation('security');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [refetchFn, setRefetchFn] = useState<(() => void) | null>(null);

  const [terminateAll, { isLoading: isTerminating }] =
    useRouteSessionsTerminateAllMutation();

  const handleTerminateAll = async () => {
    try {
      await terminateAll({ excludeCurrent: true }).unwrap();
      setConfirmOpen(false);
      refetchFn?.();
    } catch (error) {
      console.error('Failed to terminate sessions:', error);
    }
  };

  // Функция для определения класса неактивных строк
  const getRowClassName = useCallback(
    (record: SchemaSession) =>
      record.active === false ? classes.inactiveRow : '',
    [],
  );

  // Callback для получения refetch
  const handleRefetch = useCallback((refetch: () => void) => {
    setRefetchFn(() => refetch);
  }, []);

  // Кнопка для тулбара
  const TerminateButton = (
    <Button
      color="red"
      variant="light"
      leftSection={<IconLogout size={16} />}
      onClick={() => setConfirmOpen(true)}
      loading={isTerminating}>
      {t('security:terminateAllSessions', 'Завершить все сессии')}
    </Button>
  );

  return (
    <>
      <List<SchemaSession>
        model="sessions"
        order="desc"
        sort="id"
        toolbarActions={TerminateButton}
        rowClassName={getRowClassName}
        onRefetch={handleRefetch}>
        <Field name="id" label={t('fields.id')} />
        <Field name="active" label={t('fields.active')} render={value => <BooleanCell value={value} />} />
        <Field
          name="user_id"
          label={t('fields.user_id')}
          render={value => <RelationCell value={value} model="users" />}
        />
        {/* <Field name="token" />
        <Field name="ttl" /> */}
        <Field
          name="expired_datetime"
          label={t('fields.expired_datetime')}
          render={value => (
            <DateTimeCell showIcon value={value} format="compact" />
          )}
        />
        <Field
          name="create_user_id"
          label={t('fields.create_user_id')}
          render={value => <RelationCell value={value} model="users" />}
        />
        <Field
          name="create_datetime"
          label={t('fields.create_datetime')}
          render={value => <DateTimeCell value={value} format="relative" />}
        />
        {/* <Field
          name="update_user_id"
          render={value => <RelationCell value={value} model="users" />}
        />
        <Field
          name="update_datetime"
          render={value => <DateTimeCell value={value} format="relative" />}
        /> */}
      </List>

      <Modal
        opened={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title={t('security:confirmTerminate', 'Подтверждение')}
        centered>
        <Text mb="lg">
          {t(
            'security:terminateAllConfirmText',
            'Вы уверены, что хотите завершить все активные сессии кроме текущей?',
          )}
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={() => setConfirmOpen(false)}>
            {t('common:cancel', 'Отмена')}
          </Button>
          <Button
            color="red"
            onClick={handleTerminateAll}
            loading={isTerminating}>
            {t('security:terminate', 'Завершить')}
          </Button>
        </Group>
      </Modal>
    </>
  );
}
