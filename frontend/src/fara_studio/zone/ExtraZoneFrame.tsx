/**
 * Рамка зоны «Дополнительно» по её месту: под формой — секция, сбоку —
 * сворачиваемая колонка, во вкладке — без рамки (заголовок даёт
 * вкладка). Её берут и обычная зона, и редактор студии.
 */
import { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { ActionIcon, Box, Paper, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconLayoutSidebarRightCollapse,
  IconLayoutSidebarRightExpand,
} from '@tabler/icons-react';
import { FormSection } from '@/components/Form/Layout';
import layoutClasses from '@/components/Form/Layout/FormLayout.module.css';
import type { ExtraPlacement } from './zoneGrid';
import classes from './ExtraZone.module.css';

interface FrameProps {
  title: string;
  icon: ReactNode;
  children: ReactNode;
}

/** Колонка справа: стрелка на краю сворачивает её до одной кнопки. */
function ExtraZoneSide({ title, icon, children }: FrameProps) {
  const { t } = useTranslation('studio');
  const [opened, { toggle }] = useDisclosure(true);
  const toggleLabel = t(opened ? 'zone.collapse' : 'zone.expand');

  return (
    <Paper
      withBorder
      radius="md"
      p={opened ? 'md' : 'xs'}
      className={opened ? classes.side : classes.sideCollapsed}>
      <div className={classes.sideHeader}>
        {opened && (
          <>
            <Box className={layoutClasses.sectionIcon}>{icon}</Box>
            <Title order={5} className={layoutClasses.sectionTitle}>
              {title}
            </Title>
          </>
        )}
        <ActionIcon
          variant="subtle"
          color="gray"
          ml="auto"
          aria-label={toggleLabel}
          title={toggleLabel}
          onClick={toggle}>
          {opened ? (
            <IconLayoutSidebarRightCollapse size={18} />
          ) : (
            <IconLayoutSidebarRightExpand size={18} />
          )}
        </ActionIcon>
      </div>
      <Box hidden={!opened} mt="md">
        {children}
      </Box>
    </Paper>
  );
}

export function ExtraZoneFrame({
  placement,
  ...props
}: FrameProps & { placement: ExtraPlacement }) {
  if (placement === 'side') return <ExtraZoneSide {...props} />;
  if (placement === 'tab') return <>{props.children}</>;
  return (
    <FormSection title={props.title} icon={props.icon}>
      {props.children}
    </FormSection>
  );
}
