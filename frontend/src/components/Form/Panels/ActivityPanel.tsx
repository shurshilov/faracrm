import { useState, useEffect, useMemo } from 'react';
import {
  Stack,
  Text,
  Button,
  Group,
  Badge,
  ActionIcon,
  TextInput,
  Textarea,
  Select,
  Box,
  Tooltip,
  Loader,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import {
  IconCheck,
  IconPlus,
  IconX,
  IconCalendar,
  IconUser,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import {
  useSearchQuery,
  useCreateMutation,
  useUpdateMutation,
} from '@/services/api/crudApi';
import { useSelector } from 'react-redux';
import { selectCurrentSession } from '@/slices/authSlice';

const PAGE_SIZE = 80;

interface ActivityPanelProps {
  resModel: string;
  resId: number;
}

const STATE_COLORS: Record<string, string> = {
  planned: 'blue',
  today: 'orange',
  overdue: 'red',
  done: 'green',
  cancelled: 'gray',
};

export function ActivityPanel({ resModel, resId }: ActivityPanelProps) {
  const { t } = useTranslation(['activity', 'common']);
  const session = useSelector(selectCurrentSession);
  const currentUserId = session?.user_id?.id;

  const [showCreate, setShowCreate] = useState(false);
  const [limit, setLimit] = useState(PAGE_SIZE);

  const { data: activitiesData, isLoading } = useSearchQuery({
    model: 'activity',
    fields: [
      'id',
      'summary',
      'note',
      'activity_type_id',
      'user_id',
      'date_deadline',
      'state',
      'done',
      'create_date',
    ],
    filter: [
      ['res_model', '=', resModel],
      ['res_id', '=', resId],
      ['active', '=', true],
    ],
    sort: 'date_deadline',
    order: 'asc',
    limit,
  });

  const [updateActivity] = useUpdateMutation();

  const activities = activitiesData?.data || [];
  const total = activitiesData?.total || 0;
  const hasMore = total > activities.length;

  const handleMarkDone = async (activityId: number) => {
    await updateActivity({
      model: 'activity',
      id: activityId,
      values: {
        done: true,
        state: 'done',
        done_datetime: new Date().toISOString(),
      },
    });
  };

  const handleLoadMore = () => {
    setLimit(prev => prev + PAGE_SIZE);
  };

  if (isLoading && activities.length === 0) {
    return (
      <Stack align="center" py="xl">
        <Loader size="sm" />
      </Stack>
    );
  }

  return (
    <Stack gap="sm">
      {!showCreate && (
        <Button
          variant="light"
          size="compact-sm"
          leftSection={<IconPlus size={14} />}
          onClick={() => setShowCreate(true)}
          fullWidth>
          {t('activity:scheduleActivity')}
        </Button>
      )}

      {showCreate && (
        <CreateActivityForm
          resModel={resModel}
          resId={resId}
          currentUserId={currentUserId}
          onClose={() => setShowCreate(false)}
        />
      )}

      {activities.length === 0 && !showCreate && (
        <Text size="sm" c="dimmed" ta="center" py="md">
          {t('activity:noNotifications')}
        </Text>
      )}

      {activities.map((activity: any) => (
        <ActivityItem
          key={activity.id}
          activity={activity}
          onMarkDone={handleMarkDone}
        />
      ))}

      {hasMore && (
        <Button
          variant="subtle"
          size="compact-sm"
          onClick={handleLoadMore}
          loading={isLoading}
          fullWidth>
          {t('common:loadMore', 'Загрузить ещё')} ({total - activities.length})
        </Button>
      )}
    </Stack>
  );
}

// ─── Activity item ────────────────────────────────────────────

function ActivityItem({
  activity,
  onMarkDone,
}: {
  activity: any;
  onMarkDone: (id: number) => void;
}) {
  const { t } = useTranslation('activity');
  const stateColor = STATE_COLORS[activity.state] || 'gray';

  const typeName =
    activity.activity_type_id?.name || activity.activity_type_id || '';
  const userName = activity.user_id?.name || activity.user_id || '';

  return (
    <Box
      p="xs"
      style={{
        borderRadius: 'var(--mantine-radius-sm)',
        border: '1px solid var(--mantine-color-default-border)',
      }}>
      <Group justify="space-between" wrap="nowrap" gap="xs">
        <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
          <Group gap="xs" wrap="nowrap">
            <Badge size="xs" color={stateColor} variant="light">
              {t(`state.${activity.state}`, activity.state)}
            </Badge>
            {typeName && (
              <Text size="xs" c="dimmed" truncate>
                {typeName}
              </Text>
            )}
          </Group>

          {activity.summary && (
            <Text size="sm" fw={500} lineClamp={2}>
              {activity.summary}
            </Text>
          )}

          <Group gap="xs">
            <Group gap={4}>
              <IconCalendar size={12} color="var(--mantine-color-dimmed)" />
              <Text size="xs" c="dimmed">
                {activity.date_deadline}
              </Text>
            </Group>
            {userName && (
              <Group gap={4}>
                <IconUser size={12} color="var(--mantine-color-dimmed)" />
                <Text size="xs" c="dimmed" truncate>
                  {userName}
                </Text>
              </Group>
            )}
          </Group>
        </Stack>

        {!activity.done && (
          <Tooltip label={t('state.done')}>
            <ActionIcon
              variant="light"
              color="green"
              size="sm"
              onClick={() => onMarkDone(activity.id)}>
              <IconCheck size={14} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>
    </Box>
  );
}

// ─── Create activity form ─────────────────────────────────────

function CreateActivityForm({
  resModel,
  resId,
  currentUserId,
  onClose,
}: {
  resModel: string;
  resId: number;
  currentUserId?: number;
  onClose: () => void;
}) {
  const { t } = useTranslation(['activity', 'common']);
  const [createActivity, { isLoading: isCreating }] = useCreateMutation();

  const { data: typesData } = useSearchQuery({
    model: 'activity_type',
    fields: ['id', 'name', 'default_days'],
    filter: [['active', '=', true]],
    sort: 'sequence',
    order: 'asc',
  });

  const typeOptions = useMemo(() => {
    return (
      typesData?.data?.map((t: any) => ({
        value: String(t.id),
        label: t.name,
        defaultDays: t.default_days || 1,
      })) || []
    );
  }, [typesData]);

  const [activityTypeId, setActivityTypeId] = useState<string | null>(null);
  const [summary, setSummary] = useState('');
  const [dateDeadline, setDateDeadline] = useState<Date | null>(null);
  const [note, setNote] = useState('');

  useEffect(() => {
    if (typeOptions.length > 0 && !activityTypeId) {
      const reminderType = typeOptions.find(
        (t: any) =>
          t.label.toLowerCase().includes('напоминание') ||
          t.label.toLowerCase().includes('reminder'),
      );
      const first = reminderType || typeOptions[0];
      setActivityTypeId(first.value);

      const deadline = new Date();
      deadline.setDate(deadline.getDate() + (first.defaultDays || 1));
      setDateDeadline(deadline);
    }
  }, [typeOptions]);

  const handleTypeChange = (value: string | null) => {
    setActivityTypeId(value);
    if (value) {
      const selected = typeOptions.find((t: any) => t.value === value);
      if (selected) {
        const deadline = new Date();
        deadline.setDate(deadline.getDate() + (selected.defaultDays || 1));
        setDateDeadline(deadline);
      }
    }
  };

  const handleSubmit = async () => {
    if (!activityTypeId || !dateDeadline) return;

    try {
      await createActivity({
        model: 'activity',
        values: {
          res_model: resModel,
          res_id: resId,
          activity_type_id: Number(activityTypeId),
          user_id: currentUserId,
          create_user_id: currentUserId,
          summary: summary || null,
          note: note || null,
          date_deadline: dateDeadline.toISOString().split('T')[0],
          state: 'planned',
          done: false,
          active: true,
          create_date: new Date().toISOString(),
          notification_sent: false,
        },
      }).unwrap();

      onClose();
    } catch (error) {
      console.error('Failed to create activity:', error);
    }
  };

  return (
    <Box
      p="sm"
      style={{
        borderRadius: 'var(--mantine-radius-sm)',
        border: '1px solid var(--mantine-color-default-border)',
      }}>
      <Stack gap="xs">
        <Group justify="space-between">
          <Text size="sm" fw={600}>
            {t('activity:scheduleActivity')}
          </Text>
          <ActionIcon variant="subtle" size="xs" onClick={onClose}>
            <IconX size={14} />
          </ActionIcon>
        </Group>

        <Select
          size="xs"
          data={typeOptions}
          value={activityTypeId}
          onChange={handleTypeChange}
          label={t('activity:fields.activity_type_id')}
        />

        <TextInput
          size="xs"
          value={summary}
          onChange={e => setSummary(e.currentTarget.value)}
          label={t('activity:fields.summary')}
          placeholder={t('activity:summaryPlaceholder')}
        />

        <DatePickerInput
          size="xs"
          value={dateDeadline}
          onChange={setDateDeadline}
          label={t('activity:fields.date_deadline')}
          valueFormat="YYYY-MM-DD"
        />

        <Textarea
          size="xs"
          value={note}
          onChange={e => setNote(e.currentTarget.value)}
          label={t('activity:fields.note')}
          minRows={2}
          autosize
        />

        <Group justify="flex-end" gap="xs">
          <Button variant="subtle" size="compact-xs" onClick={onClose}>
            {t('common:cancel', 'Отмена')}
          </Button>
          <Button
            size="compact-xs"
            onClick={handleSubmit}
            loading={isCreating}
            disabled={!activityTypeId || !dateDeadline}>
            {t('common:save', 'Сохранить')}
          </Button>
        </Group>
      </Stack>
    </Box>
  );
}
