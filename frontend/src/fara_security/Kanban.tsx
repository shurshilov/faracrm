import { useCallback, useState } from 'react';
import { Card, Text, Group, Badge, Stack, Box, Tooltip, ThemeIcon, SimpleGrid, Image } from '@mantine/core';
import { 
  IconShield, 
  IconShieldCheck, 
  IconUser,
  IconClock,
  IconDeviceDesktop,
  IconLock,
  IconLockOpen,
  IconDatabase,
  IconApps,
  IconCode,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useSearchQuery } from '@/services/api/crudApi';
import { GetListParams, GetListResult } from '@/services/api/crudTypes';
import { useFilters } from '@/components/SearchFilter/FilterContext';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import { PermissionsBadges } from '@/components/PermissionsBadges';
import { API_BASE_URL } from '@/services/baseQueryWithReauth';
import classes from './Kanban.module.css';

// ==================== RULES KANBAN ====================

interface RuleData {
  id: number;
  name: string;
  active: boolean;
  model_id?: { id: number; name: string } | null;
  role_id?: { id: number; name: string } | null;
  perm_create: boolean;
  perm_read: boolean;
  perm_update: boolean;
  perm_delete: boolean;
  domain?: any;
}

function RuleCard({ rule, onClick }: { rule: RuleData; onClick: () => void }) {
  return (
    <Card
      className={classes.card}
      data-inactive={!rule.active || undefined}
      shadow="sm"
      padding="md"
      radius="md"
      withBorder
      onClick={onClick}
    >
      <Group justify="space-between" mb="xs">
        <Group gap="xs">
          <ThemeIcon 
            size="md" 
            radius="md" 
            variant="light"
            color={rule.active ? 'blue' : 'gray'}
          >
            <IconShield size={16} />
          </ThemeIcon>
          <Text fw={600} size="sm" lineClamp={1}>
            {rule.name}
          </Text>
        </Group>
        <Badge size="sm" variant="dot" color={rule.active ? 'green' : 'gray'}>
          {rule.active ? 'Активно' : 'Выкл'}
        </Badge>
      </Group>

      <Stack gap={6}>
        {rule.model_id && (
          <Group gap={6}>
            <IconDatabase size={14} color="var(--mantine-color-dimmed)" />
            <Text size="xs" c="dimmed">{rule.model_id.name}</Text>
          </Group>
        )}
        
        {rule.role_id && (
          <Group gap={6}>
            <IconUser size={14} color="var(--mantine-color-dimmed)" />
            <Text size="xs" c="dimmed">{rule.role_id.name}</Text>
          </Group>
        )}
        
        {!rule.role_id && (
          <Text size="xs" c="dimmed" fs="italic">Для всех ролей</Text>
        )}
      </Stack>

      <Group gap={4} mt="sm" justify="space-between">
        <PermissionsBadges
          create={rule.perm_create}
          read={rule.perm_read}
          update={rule.perm_update}
          delete={rule.perm_delete}
        />
        
        {rule.domain && (
          <Tooltip label="Есть domain-фильтр">
            <Badge size="xs" variant="outline" color="violet">
              <IconCode size={10} />
            </Badge>
          </Tooltip>
        )}
      </Group>
    </Card>
  );
}

export function ViewKanbanRules() {
  const navigate = useNavigate();
  const contextFilters = useFilters();

  const { data } = useSearchQuery({
    model: 'rules',
    fields: ['id', 'name', 'active', 'model_id', 'role_id', 'perm_create', 'perm_read', 'perm_update', 'perm_delete', 'domain'],
    limit: 100,
    order: 'asc',
    sort: 'name',
    filter: contextFilters,
  }) as TypedUseQueryHookResult<GetListResult<RuleData>, GetListParams, BaseQueryFn>;

  const handleClick = useCallback((id: number) => navigate(`${id}`), [navigate]);
  const rules = data?.data || [];

  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="md" p="md">
      {rules.map(rule => (
        <RuleCard key={rule.id} rule={rule} onClick={() => handleClick(rule.id)} />
      ))}
    </SimpleGrid>
  );
}

// ==================== SESSIONS KANBAN ====================

interface SessionData {
  id: number;
  active: boolean;
  user_id?: { id: number; name: string } | null;
  token?: string;
  create_datetime?: string;
  ttl?: number;
}

function SessionCard({ session, onClick }: { session: SessionData; onClick: () => void }) {
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    return date.toLocaleString('ru-RU', { 
      day: '2-digit', 
      month: '2-digit', 
      year: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatTTL = (seconds?: number) => {
    if (!seconds) return '—';
    const hours = Math.floor(seconds / 3600);
    if (hours >= 24) return `${Math.floor(hours / 24)}д`;
    return `${hours}ч`;
  };

  return (
    <Card
      className={classes.card}
      data-inactive={!session.active || undefined}
      shadow="sm"
      padding="md"
      radius="md"
      withBorder
      onClick={onClick}
    >
      <Group justify="space-between" mb="xs">
        <Group gap="xs">
          <ThemeIcon 
            size="md" 
            radius="md" 
            variant="light"
            color={session.active ? 'green' : 'gray'}
          >
            {session.active ? <IconLockOpen size={16} /> : <IconLock size={16} />}
          </ThemeIcon>
          <Text fw={600} size="sm">
            #{session.id}
          </Text>
        </Group>
        <Badge size="sm" variant="dot" color={session.active ? 'green' : 'red'}>
          {session.active ? 'Активна' : 'Истекла'}
        </Badge>
      </Group>

      <Stack gap={6}>
        {session.user_id && (
          <Group gap={6}>
            <IconUser size={14} color="var(--mantine-color-dimmed)" />
            <Text size="sm" fw={500}>{session.user_id.name}</Text>
          </Group>
        )}
        
        <Group gap={6}>
          <IconClock size={14} color="var(--mantine-color-dimmed)" />
          <Text size="xs" c="dimmed">{formatDate(session.create_datetime)}</Text>
        </Group>

        {session.ttl && (
          <Group gap={6}>
            <IconDeviceDesktop size={14} color="var(--mantine-color-dimmed)" />
            <Text size="xs" c="dimmed">TTL: {formatTTL(session.ttl)}</Text>
          </Group>
        )}
      </Stack>

      {session.token && (
        <Tooltip label={session.token}>
          <Text size="xs" c="dimmed" mt="xs" lineClamp={1} ff="monospace">
            {session.token.substring(0, 20)}...
          </Text>
        </Tooltip>
      )}
    </Card>
  );
}

export function ViewKanbanSessions() {
  const navigate = useNavigate();
  const contextFilters = useFilters();

  const { data } = useSearchQuery({
    model: 'sessions',
    fields: ['id', 'active', 'user_id', 'token', 'create_datetime', 'ttl'],
    limit: 100,
    order: 'desc',
    sort: 'id',
    filter: contextFilters,
  }) as TypedUseQueryHookResult<GetListResult<SessionData>, GetListParams, BaseQueryFn>;

  const handleClick = useCallback((id: number) => navigate(`${id}`), [navigate]);
  const sessions = data?.data || [];

  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="md" p="md">
      {sessions.map(session => (
        <SessionCard key={session.id} session={session} onClick={() => handleClick(session.id)} />
      ))}
    </SimpleGrid>
  );
}

// ==================== APPS KANBAN ====================

interface AppData {
  id: number;
  code: string;
  name: string;
  active: boolean;
}

function AppCard({ app, onClick }: { app: AppData; onClick: () => void }) {
  const [imgError, setImgError] = useState(false);
  const iconUrl = `${API_BASE_URL}/static/app-icons/${app.code}.svg`;

  return (
    <Card
      className={classes.card}
      data-inactive={!app.active || undefined}
      shadow="sm"
      padding="md"
      radius="md"
      withBorder
      onClick={onClick}
    >
      <Stack gap="sm">
        {/* Иконка по центру */}
        <Group justify="center">
          <Box className={classes.appIconWrapper}>
            {!imgError ? (
              <Image
                src={iconUrl}
                alt={app.name}
                w={48}
                h={48}
                fit="contain"
                onError={() => setImgError(true)}
              />
            ) : (
              <ThemeIcon 
                size={48} 
                radius="md" 
                variant="gradient"
                gradient={app.active ? { from: 'blue', to: 'cyan' } : { from: 'gray', to: 'dark' }}
              >
                <IconApps size={28} />
              </ThemeIcon>
            )}
          </Box>
        </Group>

        {/* Название и код */}
        <Box ta="center">
          <Tooltip label={app.name} disabled={app.name.length < 20}>
            <Text fw={600} size="sm" lineClamp={1}>
              {app.name}
            </Text>
          </Tooltip>
          <Text size="xs" c="dimmed" ff="monospace" lineClamp={1}>
            {app.code}
          </Text>
        </Box>

        {/* Статус */}
        <Badge 
          size="sm" 
          variant="light" 
          color={app.active ? 'green' : 'gray'}
          fullWidth
        >
          {app.active ? 'Активно' : 'Отключено'}
        </Badge>
      </Stack>
    </Card>
  );
}

export function ViewKanbanApps() {
  const navigate = useNavigate();
  const contextFilters = useFilters();

  const { data } = useSearchQuery({
    model: 'apps',
    fields: ['id', 'code', 'name', 'active'],
    limit: 100,
    order: 'asc',
    sort: 'name',
    filter: contextFilters,
  }) as TypedUseQueryHookResult<GetListResult<AppData>, GetListParams, BaseQueryFn>;

  const handleClick = useCallback((id: number) => navigate(`${id}`), [navigate]);
  const apps = data?.data || [];

  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4, xl: 5 }} spacing="md" p="md">
      {apps.map(app => (
        <AppCard key={app.id} app={app} onClick={() => handleClick(app.id)} />
      ))}
    </SimpleGrid>
  );
}

// ==================== ROLES KANBAN ====================

interface RoleData {
  id: number;
  name: string;
  app_id?: { id: number; name: string } | null;
}

function RoleCard({ role, onClick }: { role: RoleData; onClick: () => void }) {
  const isAdmin = role.name?.toLowerCase().includes('admin');
  
  return (
    <Card
      className={classes.card}
      data-admin={isAdmin || undefined}
      shadow="sm"
      padding="md"
      radius="md"
      withBorder
      onClick={onClick}
    >
      <Group gap="xs" mb="xs">
        <ThemeIcon 
          size="md" 
          radius="md" 
          variant="light"
          color={isAdmin ? 'violet' : 'blue'}
        >
          {isAdmin ? <IconShieldCheck size={16} /> : <IconShield size={16} />}
        </ThemeIcon>
        <Text fw={600} size="sm" lineClamp={1}>
          {role.name}
        </Text>
      </Group>

      {role.app_id && (
        <Group gap={6}>
          <IconApps size={14} color="var(--mantine-color-dimmed)" />
          <Text size="xs" c="dimmed">{role.app_id.name}</Text>
        </Group>
      )}
      
      {isAdmin && (
        <Badge size="xs" variant="light" color="violet" mt="sm">
          Администратор
        </Badge>
      )}
    </Card>
  );
}

export function ViewKanbanRoles() {
  const navigate = useNavigate();
  const contextFilters = useFilters();

  const { data } = useSearchQuery({
    model: 'roles',
    fields: ['id', 'name', 'app_id'],
    limit: 100,
    order: 'asc',
    sort: 'name',
    filter: contextFilters,
  }) as TypedUseQueryHookResult<GetListResult<RoleData>, GetListParams, BaseQueryFn>;

  const handleClick = useCallback((id: number) => navigate(`${id}`), [navigate]);
  const roles = data?.data || [];

  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="md" p="md">
      {roles.map(role => (
        <RoleCard key={role.id} role={role} onClick={() => handleClick(role.id)} />
      ))}
    </SimpleGrid>
  );
}

// ==================== ACCESS LIST KANBAN ====================

interface AccessListData {
  id: number;
  name: string;
  model_id?: { id: number; name: string } | null;
  role_id?: { id: number; name: string } | null;
  perm_create: boolean;
  perm_read: boolean;
  perm_update: boolean;
  perm_delete: boolean;
}

function AccessListCard({ acl, onClick }: { acl: AccessListData; onClick: () => void }) {
  return (
    <Card
      className={classes.card}
      shadow="sm"
      padding="md"
      radius="md"
      withBorder
      onClick={onClick}
    >
      <Group justify="space-between" mb="xs">
        <Group gap="xs">
          <ThemeIcon size="md" radius="md" variant="light" color="teal">
            <IconShieldCheck size={16} />
          </ThemeIcon>
          <Text fw={600} size="sm" lineClamp={1}>
            {acl.name}
          </Text>
        </Group>
      </Group>

      <Stack gap={6}>
        {acl.model_id && (
          <Group gap={6}>
            <IconDatabase size={14} color="var(--mantine-color-dimmed)" />
            <Text size="xs" c="dimmed">{acl.model_id.name}</Text>
          </Group>
        )}
        
        {acl.role_id && (
          <Group gap={6}>
            <IconUser size={14} color="var(--mantine-color-dimmed)" />
            <Text size="xs" c="dimmed">{acl.role_id.name}</Text>
          </Group>
        )}
      </Stack>

      <Group gap={4} mt="sm">
        <PermissionsBadges
          create={acl.perm_create}
          read={acl.perm_read}
          update={acl.perm_update}
          delete={acl.perm_delete}
        />
      </Group>
    </Card>
  );
}

export function ViewKanbanAccessList() {
  const navigate = useNavigate();
  const contextFilters = useFilters();

  const { data } = useSearchQuery({
    model: 'access_list',
    fields: ['id', 'name', 'model_id', 'role_id', 'perm_create', 'perm_read', 'perm_update', 'perm_delete'],
    limit: 100,
    order: 'asc',
    sort: 'name',
    filter: contextFilters,
  }) as TypedUseQueryHookResult<GetListResult<AccessListData>, GetListParams, BaseQueryFn>;

  const handleClick = useCallback((id: number) => navigate(`${id}`), [navigate]);
  const items = data?.data || [];

  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="md" p="md">
      {items.map(acl => (
        <AccessListCard key={acl.id} acl={acl} onClick={() => handleClick(acl.id)} />
      ))}
    </SimpleGrid>
  );
}

// ==================== MODELS KANBAN ====================

interface ModelData {
  id: number;
  name: string;
  model?: string;
}

function ModelCard({ model, onClick }: { model: ModelData; onClick: () => void }) {
  return (
    <Card
      className={classes.card}
      shadow="sm"
      padding="md"
      radius="md"
      withBorder
      onClick={onClick}
    >
      <Group gap="xs">
        <ThemeIcon size="md" radius="md" variant="light" color="indigo">
          <IconDatabase size={16} />
        </ThemeIcon>
        <Box>
          <Text fw={600} size="sm" lineClamp={1}>
            {model.name}
          </Text>
          {model.model && (
            <Text size="xs" c="dimmed" ff="monospace">
              {model.model}
            </Text>
          )}
        </Box>
      </Group>
    </Card>
  );
}

export function ViewKanbanModels() {
  const navigate = useNavigate();
  const contextFilters = useFilters();

  const { data } = useSearchQuery({
    model: 'models',
    fields: ['id', 'name', 'model'],
    limit: 100,
    order: 'asc',
    sort: 'name',
    filter: contextFilters,
  }) as TypedUseQueryHookResult<GetListResult<ModelData>, GetListParams, BaseQueryFn>;

  const handleClick = useCallback((id: number) => navigate(`${id}`), [navigate]);
  const models = data?.data || [];

  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4, xl: 5 }} spacing="md" p="md">
      {models.map(model => (
        <ModelCard key={model.id} model={model} onClick={() => handleClick(model.id)} />
      ))}
    </SimpleGrid>
  );
}
