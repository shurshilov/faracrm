import { useState, useRef, useCallback, useEffect } from 'react';
import {
  ActionIcon,
  Indicator,
  Group,
  Text,
  Box,
  CloseButton,
  Tabs,
} from '@mantine/core';
import { IconBell, IconMessage, IconPaperclip } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useSearchQuery } from '@/services/api/crudApi';
import { ActivityPanel } from './ActivityPanel';
import { MessagesPanel } from './MessagesPanel';
import { AttachmentsPanel } from './AttachmentsPanel';

const COUNT_LIMIT = 80;
const PANEL_MIN_WIDTH = 300;
const PANEL_MAX_WIDTH = 700;
const PANEL_DEFAULT_WIDTH = 400;
const PANEL_STORAGE_KEY = 'formPanelWidth';

interface FormPanelsProps {
  resModel: string;
  resId: number;
}

export type PanelType = 'activities' | 'messages' | 'attachments' | null;

/**
 * Badge icons for toolbar.
 * Renders 3 icons with counters.
 * Does NOT render the panel itself — see FormPanelSide.
 */
export function FormPanelsBadges({
  resModel,
  resId,
  activePanel,
  onToggle,
}: FormPanelsProps & {
  activePanel: PanelType;
  onToggle: (panel: PanelType) => void;
}) {
  const { t } = useTranslation(['activity', 'common']);

  // ─── Counts ─────────────────────────────────────────────────
  // API limit:0 не возвращает пустой data, поэтому запрашиваем
  // COUNT_LIMIT+1 записей и считаем data.length

  const { data: activitiesData } = useSearchQuery({
    model: 'activity',
    fields: ['id'],
    filter: [
      ['res_model', '=', resModel],
      ['res_id', '=', resId],
      ['active', '=', true],
      ['done', '=', false],
    ],
    limit: COUNT_LIMIT + 1,
  });

  const { data: messagesData } = useSearchQuery({
    model: 'chat_message',
    fields: ['id'],
    filter: [
      ['res_model', '=', resModel],
      ['res_id', '=', resId],
      ['is_deleted', '=', false],
    ],
    limit: COUNT_LIMIT + 1,
  });

  const { data: attachmentsData } = useSearchQuery({
    model: 'attachments',
    fields: ['id'],
    filter: [
      ['res_model', '=', resModel],
      ['res_id', '=', resId],
      ['folder', '=', false],
    ],
    limit: COUNT_LIMIT + 1,
  });

  const activityCount = activitiesData?.data?.length || 0;
  const messageCount = messagesData?.data?.length || 0;
  const attachmentCount = attachmentsData?.data?.length || 0;

  const formatCount = (count: number) =>
    count > COUNT_LIMIT ? `${COUNT_LIMIT}+` : String(count);

  const panelTitle: Record<string, string> = {
    activities: t('activity:menu.activity', 'Активности'),
    messages: t('common:messages', 'Сообщения'),
    attachments: t('common:attachments', 'Вложения'),
  };

  return (
    <Group gap={4}>
      <Indicator
        label={formatCount(activityCount)}
        size={14}
        disabled={activityCount === 0}
        color="orange"
        offset={4}>
        <ActionIcon
          variant={activePanel === 'activities' ? 'filled' : 'subtle'}
          size="md"
          onClick={() => onToggle('activities')}
          title={panelTitle.activities}>
          <IconBell size={18} />
        </ActionIcon>
      </Indicator>

      <Indicator
        label={formatCount(messageCount)}
        size={14}
        disabled={messageCount === 0}
        color="blue"
        offset={4}>
        <ActionIcon
          variant={activePanel === 'messages' ? 'filled' : 'subtle'}
          size="md"
          onClick={() => onToggle('messages')}
          title={panelTitle.messages}>
          <IconMessage size={18} />
        </ActionIcon>
      </Indicator>

      <Indicator
        label={formatCount(attachmentCount)}
        size={14}
        disabled={attachmentCount === 0}
        color="green"
        offset={4}>
        <ActionIcon
          variant={activePanel === 'attachments' ? 'filled' : 'subtle'}
          size="md"
          onClick={() => onToggle('attachments')}
          title={panelTitle.attachments}>
          <IconPaperclip size={18} />
        </ActionIcon>
      </Indicator>
    </Group>
  );
}

/**
 * Resizable side panel that renders inline as part of the layout.
 * Place next to form content in a flex container.
 */
export function FormPanelSide({
  resModel,
  resId,
  activePanel,
  onClose,
}: FormPanelsProps & {
  activePanel: PanelType;
  onClose: () => void;
}) {
  const { t } = useTranslation(['activity', 'common']);

  // Restore width from localStorage
  const [panelWidth, setPanelWidth] = useState(() => {
    const saved = localStorage.getItem(PANEL_STORAGE_KEY);
    const parsed = saved ? parseInt(saved, 10) : NaN;
    return isNaN(parsed)
      ? PANEL_DEFAULT_WIDTH
      : Math.min(Math.max(parsed, PANEL_MIN_WIDTH), PANEL_MAX_WIDTH);
  });

  const isResizing = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      isResizing.current = true;
      startX.current = e.clientX;
      startWidth.current = panelWidth;

      const handleMouseMove = (ev: MouseEvent) => {
        if (!isResizing.current) return;
        // Drag LEFT = increase width (panel is on the right)
        const delta = startX.current - ev.clientX;
        const newWidth = Math.min(
          Math.max(startWidth.current + delta, PANEL_MIN_WIDTH),
          PANEL_MAX_WIDTH,
        );
        setPanelWidth(newWidth);
      };

      const handleMouseUp = () => {
        isResizing.current = false;
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        // Persist
        localStorage.setItem(PANEL_STORAGE_KEY, String(panelWidth));
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    },
    [panelWidth],
  );

  // Save on width changes
  useEffect(() => {
    localStorage.setItem(PANEL_STORAGE_KEY, String(panelWidth));
  }, [panelWidth]);

  if (!activePanel) return null;

  const panelTitles: Record<string, string> = {
    activities: t('activity:menu.activity', 'Активности'),
    messages: t('common:messages', 'Сообщения'),
    attachments: t('common:attachments', 'Вложения'),
  };

  return (
    <Box
      style={{
        width: panelWidth,
        minWidth: PANEL_MIN_WIDTH,
        maxWidth: PANEL_MAX_WIDTH,
        display: 'flex',
        flexShrink: 0,
        position: 'relative',
      }}>
      {/* Resize handle */}
      <Box
        onMouseDown={handleMouseDown}
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          bottom: 0,
          width: 4,
          cursor: 'col-resize',
          zIndex: 10,
          background: 'transparent',
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLElement).style.background =
            'var(--mantine-color-blue-3)';
        }}
        onMouseLeave={e => {
          if (!isResizing.current) {
            (e.currentTarget as HTMLElement).style.background = 'transparent';
          }
        }}
      />

      {/* Panel content */}
      <Box
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          borderLeft: '1px solid var(--mantine-color-default-border)',
          overflow: 'hidden',
        }}>
        {/* Header */}
        <Group
          justify="space-between"
          px="sm"
          py="xs"
          style={{
            borderBottom: '1px solid var(--mantine-color-default-border)',
            flexShrink: 0,
          }}>
          <Text size="sm" fw={600}>
            {panelTitles[activePanel]}
          </Text>
          <CloseButton size="sm" onClick={onClose} />
        </Group>

        {/* Panel body */}
        <Box
          p={activePanel === 'messages' ? 0 : 'sm'}
          style={{
            flex: 1,
            overflowY: activePanel === 'messages' ? 'hidden' : 'auto',
            overflowX: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
          }}>
          {activePanel === 'activities' && (
            <ActivityPanel resModel={resModel} resId={resId} />
          )}
          {activePanel === 'messages' && (
            <MessagesPanel resModel={resModel} resId={resId} />
          )}
          {activePanel === 'attachments' && (
            <AttachmentsPanel resModel={resModel} resId={resId} />
          )}
        </Box>
      </Box>
    </Box>
  );
}
