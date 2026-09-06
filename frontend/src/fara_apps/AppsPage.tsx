import { useMemo, useState } from 'react';
import {
  Badge,
  Box,
  Button,
  Center,
  Group,
  Loader,
  Modal,
  Paper,
  ScrollArea,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { IconPuzzle, IconSearch } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useSelector } from 'react-redux';
import { useTranslation } from 'react-i18next';
import { MenuGroups } from '@/config/menuGroups';
import {
  type CatalogApp,
  useGetAppsCatalogQuery,
  useInstallAppMutation,
  useUninstallAppMutation,
} from './api';
import classes from './AppsPage.module.css';

type Scope = 'all' | 'installed' | 'available';

/** Ставить и удалять может суперпользователь или роль system_admin —
 *  то же правило, что на бэке (/apps/{code}/install). */
function useCanManageApps(): boolean {
  const session = useSelector((state: any) => state.auth.session);
  const user = session?.user_id;
  return (
    !!user?.is_admin ||
    (user?.role_ids ?? []).some(
      (role: { code: string }) => role.code === 'system_admin',
    )
  );
}

// Иконка UI-приложения — иконка его группы меню, та же, что в лаунчере.
function appIcon(app: CatalogApp) {
  const groups = MenuGroups as Record<string, { Icon: typeof IconPuzzle }>;
  return (app.app_key && groups[app.app_key]?.Icon) || IconPuzzle;
}

interface AppCardProps {
  app: CatalogApp;
  canManage: boolean;
  busy: boolean;
  onInstall: () => void;
  onUninstall: () => void;
}

function AppCard({ app, canManage, busy, onInstall, onUninstall }: AppCardProps) {
  const { t } = useTranslation('apps');
  const Icon = appIcon(app);

  const action = app.core ? (
    <Badge variant="light" color="blue" size="sm">
      {t('badge.core')}
    </Badge>
  ) : !canManage ? (
    <Badge
      variant={app.installed ? 'dot' : 'outline'}
      color={app.installed ? 'green' : 'gray'}
      size="sm">
      {t(app.installed ? 'badge.installed' : 'badge.notInstalled')}
    </Badge>
  ) : app.installed ? (
    <Button size="xs" variant="subtle" color="red" loading={busy} onClick={onUninstall}>
      {t('actions.uninstall')}
    </Button>
  ) : (
    <Button size="xs" variant="light" loading={busy} onClick={onInstall}>
      {t('actions.install')}
    </Button>
  );

  return (
    <Paper
      withBorder
      radius="md"
      p="md"
      className={classes.card}
      data-installed={app.installed || undefined}>
      <Group align="flex-start" wrap="nowrap" gap="sm">
        <ThemeIcon
          variant="light"
          color={app.installed ? undefined : 'gray'}
          size={44}
          radius="md">
          <Icon size={24} stroke={1.5} />
        </ThemeIcon>
        <Box style={{ flex: 1, minWidth: 0 }}>
          <Group gap="xs" wrap="nowrap" justify="space-between">
            <Text fw={600} truncate title={app.code}>
              {app.name}
            </Text>
            {app.version && (
              <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
                {app.version}
              </Text>
            )}
          </Group>
          <Text size="sm" c="dimmed" lineClamp={2}>
            {app.summary || app.code}
          </Text>
        </Box>
      </Group>
      <Group justify="space-between" mt="md" wrap="nowrap" gap="xs">
        {app.category ? (
          <Badge variant="light" color="gray" size="sm">
            {app.category}
          </Badge>
        ) : (
          <span />
        )}
        {action}
      </Group>
    </Paper>
  );
}

/**
 * Страница «Приложения» (/apps): карточки реестра с установкой и удалением
 * без рестарта. После действия RTK перечитывает каталог — карточки, меню и
 * роуты обновляются сами. Что реально ставить и удалять (зависимости,
 * зависимые), решает бэкенд; результат показываем уведомлением.
 */
export default function AppsPage() {
  const { t } = useTranslation('apps');
  const canManage = useCanManageApps();
  const [scope, setScope] = useState<Scope>('all');
  const [query, setQuery] = useState('');
  const [toRemove, setToRemove] = useState<CatalogApp | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  const { data, isLoading } = useGetAppsCatalogQuery();
  const [installApp] = useInstallAppMutation();
  const [uninstallApp] = useUninstallAppMutation();

  const apps = data?.apps ?? [];
  const installedCount = apps.filter(app => app.installed).length;

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return apps.filter(app => {
      if (scope === 'installed' && !app.installed) return false;
      if (scope === 'available' && app.installed) return false;
      if (!needle) return true;
      return [app.name, app.code, app.summary, app.category ?? ''].some(
        text => text.toLowerCase().includes(needle),
      );
    });
  }, [apps, scope, query]);

  const namesOf = (codes: string[]) =>
    codes
      .map(code => apps.find(app => app.code === code)?.name ?? code)
      .join(', ');

  // Ошибки (#APP_IS_CORE и т.п.) показывает общая модалка API.
  const run = async (app: CatalogApp, action: 'install' | 'uninstall') => {
    setPending(app.code);
    try {
      if (action === 'install') {
        const result = await installApp(app.code).unwrap();
        notifications.show({
          message: t('notify.installed', { names: namesOf(result.installed) }),
        });
      } else {
        const result = await uninstallApp(app.code).unwrap();
        notifications.show({
          message: t('notify.uninstalled', {
            names: namesOf(result.uninstalled),
          }),
        });
      }
    } catch {
      /* см. выше */
    } finally {
      setPending(null);
    }
  };

  return (
    // AppShell.Main живёт с height:100dvh и overflow:hidden — страница
    // скроллится сама, как остальные кастомные страницы.
    <ScrollArea h="100%" type="auto">
      <Stack gap="md" pb="md">
        <Group justify="space-between" align="flex-end" wrap="wrap" gap="sm">
          <Box>
            <Title order={3}>{t('title')}</Title>
            <Text size="sm" c="dimmed">
              {t('subtitle', { installed: installedCount, total: apps.length })}
            </Text>
          </Box>
          <Group gap="sm" wrap="wrap">
            <TextInput
              placeholder={t('search')}
              leftSection={<IconSearch size={16} />}
              value={query}
              onChange={event => setQuery(event.currentTarget.value)}
              w={{ base: '100%', sm: 260 }}
            />
            <SegmentedControl
              value={scope}
              onChange={value => setScope(value as Scope)}
              data={[
                { label: t('scope.all'), value: 'all' },
                { label: t('scope.installed'), value: 'installed' },
                { label: t('scope.available'), value: 'available' },
              ]}
            />
          </Group>
        </Group>

        {isLoading ? (
          <Center py="xl">
            <Loader />
          </Center>
        ) : visible.length === 0 ? (
          <Center py="xl">
            <Text c="dimmed">{t('empty')}</Text>
          </Center>
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, lg: 3, xl: 4 }} spacing="md">
            {visible.map(app => (
              <AppCard
                key={app.code}
                app={app}
                canManage={canManage}
                busy={pending === app.code}
                onInstall={() => run(app, 'install')}
                onUninstall={() => setToRemove(app)}
              />
            ))}
          </SimpleGrid>
        )}

        <Modal
          opened={!!toRemove}
          onClose={() => setToRemove(null)}
          title={t('uninstall.title', { name: toRemove?.name ?? '' })}
          centered>
          <Text size="sm">{t('uninstall.text')}</Text>
          <Group justify="flex-end" mt="lg">
            <Button variant="default" onClick={() => setToRemove(null)}>
              {t('common:cancel')}
            </Button>
            <Button
              color="red"
              onClick={() => {
                const app = toRemove;
                setToRemove(null);
                if (app) run(app, 'uninstall');
              }}>
              {t('actions.uninstall')}
            </Button>
          </Group>
        </Modal>
      </Stack>
    </ScrollArea>
  );
}
