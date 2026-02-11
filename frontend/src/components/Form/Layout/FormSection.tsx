import { ReactNode } from 'react';
import { Paper, Title, Stack, Divider, Box, Collapse } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import classes from './FormLayout.module.css';

interface FormSectionProps {
  title?: string;
  icon?: ReactNode;
  children: ReactNode;
  collapsible?: boolean;
  defaultOpened?: boolean;
  withBorder?: boolean;
  withPadding?: boolean;
}

/**
 * Секция формы с заголовком и группировкой полей
 * 
 * @example
 * <FormSection title="Основная информация" icon={<IconUser />}>
 *   <Field name="name" />
 *   <Field name="email" />
 * </FormSection>
 */
export function FormSection({
  title,
  icon,
  children,
  collapsible = false,
  defaultOpened = true,
  withBorder = true,
  withPadding = true,
}: FormSectionProps) {
  const [opened, { toggle }] = useDisclosure(defaultOpened);

  const content = (
    <Stack gap="md">
      {children}
    </Stack>
  );

  if (!title && !withBorder) {
    return <Box className={classes.section}>{content}</Box>;
  }

  return (
    <Paper
      className={classes.sectionPaper}
      withBorder={withBorder}
      p={withPadding ? 'md' : 0}
      radius="md"
    >
      {title && (
        <>
          <Box
            className={classes.sectionHeader}
            onClick={collapsible ? toggle : undefined}
            style={{ cursor: collapsible ? 'pointer' : 'default' }}
          >
            {collapsible && (
              <Box className={classes.collapseIcon}>
                {opened ? <IconChevronDown size={18} /> : <IconChevronRight size={18} />}
              </Box>
            )}
            {icon && <Box className={classes.sectionIcon}>{icon}</Box>}
            <Title order={5} className={classes.sectionTitle}>
              {title}
            </Title>
          </Box>
          <Divider my="sm" />
        </>
      )}
      
      {collapsible ? (
        <Collapse in={opened}>
          {content}
        </Collapse>
      ) : (
        content
      )}
    </Paper>
  );
}

FormSection.displayName = 'FormSection';
