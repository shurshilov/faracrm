import { Menu, Button } from '@mantine/core';
import { IconChevronDown, IconSettings } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { ReactNode } from 'react';

export interface FormAction {
  key: string;
  label: string;
  icon?: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  color?: string;
}

interface FormActionsProps {
  actions: FormAction[];
}

export function FormActions({ actions }: FormActionsProps) {
  const { t } = useTranslation();

  if (!actions.length) return null;

  return (
    <Menu position="bottom-end" withArrow shadow="md">
      <Menu.Target>
        <Button
          variant="light"
          size="compact-sm"
          rightSection={<IconChevronDown size={14} />}
          leftSection={<IconSettings size={14} />}
        >
          {t('common.actions', 'Actions')}
        </Button>
      </Menu.Target>

      <Menu.Dropdown>
        {actions.map((action) => (
          <Menu.Item
            key={action.key}
            leftSection={action.icon}
            onClick={action.onClick}
            disabled={action.disabled}
            color={action.color}
          >
            {action.label}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}

export default FormActions;
