import { useCallback, useState, useEffect } from 'react';
import {
  Card,
  Text,
  Group,
  Avatar,
  Badge,
  Stack,
  Box,
  Tooltip,
} from '@mantine/core';
import { IconUser, IconCrown } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useSearchQuery } from '@/services/api/crudApi';
import { SchemaUser } from '@/services/api/users';
import { GetListParams, GetListResult } from '@/services/api/crudTypes';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import { attachmentPreviewUrl } from '@/utils/attachmentUrls';
import classes from './Kanban.module.css';

interface UserCardProps {
  user: SchemaUser;
  onClick: () => void;
}

function UserCard({ user, onClick }: UserCardProps) {
  const [avatarSrc, setAvatarSrc] = useState<string | null>(null);

  const imageId = user.image?.id;
  const imageChecksum = user.image?.checksum;

  // Проверяем является ли пользователь админом
  const isAdmin = (user as any).is_admin === true;

  // Загружаем аватар как в UserMenu
  useEffect(() => {
    setAvatarSrc(null);
    if (!imageId || imageId <= 0) return;

    setAvatarSrc(attachmentPreviewUrl(imageId, 200, 200, imageChecksum));
  }, [imageId, imageChecksum]);

  // Получаем инициалы для fallback аватара
  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(part => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  // Генерируем цвет на основе имени
  const getColorFromName = (name: string) => {
    const colors = [
      'blue',
      'cyan',
      'teal',
      'green',
      'lime',
      'yellow',
      'orange',
      'red',
      'pink',
      'grape',
      'violet',
      'indigo',
    ];
    const index =
      name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0) %
      colors.length;
    return colors[index];
  };

  return (
    <Card
      className={classes.userCard}
      data-admin={isAdmin || undefined}
      shadow="sm"
      padding="lg"
      radius="md"
      withBorder
      onClick={onClick}>
      <Box className={classes.cardHeader} data-admin={isAdmin || undefined}>
        <Box className={classes.avatarWrapper}>
          <Avatar
            src={avatarSrc}
            size={80}
            radius="xl"
            color={isAdmin ? 'violet' : getColorFromName(user.name)}
            className={classes.avatar}
            data-admin={isAdmin || undefined}>
            {getInitials(user.name)}
          </Avatar>
          {isAdmin && (
            <Tooltip label="Administrator">
              <Box className={classes.adminBadge}>
                <IconCrown size={14} />
              </Box>
            </Tooltip>
          )}
        </Box>
      </Box>

      <Stack gap="xs" mt="md" align="center">
        <Text
          fw={600}
          size="lg"
          ta="center"
          lineClamp={1}
          c={isAdmin ? 'violet' : undefined}>
          {user.name}
        </Text>

        {user.login && (
          <Group gap={4} wrap="nowrap">
            <IconUser size={14} color="var(--mantine-color-dimmed)" />
            <Text size="sm" c="dimmed" lineClamp={1}>
              {user.login}
            </Text>
          </Group>
        )}

        {/* {user.email && (
          <Tooltip label={user.email}>
            <Group gap={4} wrap="nowrap" style={{ maxWidth: '100%' }}>
              <IconMail
                size={14}
                color="var(--mantine-color-dimmed)"
                style={{ flexShrink: 0 }}
              />
              <Text size="sm" c="dimmed" lineClamp={1}>
                {user.email}
              </Text>
            </Group>
          </Tooltip>
        )} */}
      </Stack>

      {user.role_ids && user.role_ids.length > 0 && (
        <Group gap={4} mt="md" justify="center" wrap="wrap">
          {user.role_ids.slice(0, 3).map(role => (
            <Badge
              key={role.id}
              size="sm"
              variant="light"
              color={
                role.name?.toLowerCase().includes('admin')
                  ? 'violet'
                  : getColorFromName(role.name)
              }>
              {role.name}
            </Badge>
          ))}
          {user.role_ids.length > 3 && (
            <Badge size="sm" variant="outline" color="gray">
              +{user.role_ids.length - 3}
            </Badge>
          )}
        </Group>
      )}
    </Card>
  );
}

export default function ViewKanbanUsers() {
  const navigate = useNavigate();

  const { data: usersData } = useSearchQuery({
    model: 'users',
    fields: ['id', 'name', 'login', 'image', 'role_ids', 'is_admin'],
    limit: 100,
    order: 'asc',
    sort: 'name',
  }) as TypedUseQueryHookResult<
    GetListResult<SchemaUser>,
    GetListParams,
    BaseQueryFn
  >;

  const handleCardClick = useCallback(
    (id: number) => {
      navigate(`${id}`);
    },
    [navigate],
  );

  const users = usersData?.data || [];

  return (
    <div className={classes.usersGrid}>
      {users.map(user => (
        <UserCard
          key={user.id}
          user={user}
          onClick={() => handleCardClick(user.id)}
        />
      ))}
    </div>
  );
}
