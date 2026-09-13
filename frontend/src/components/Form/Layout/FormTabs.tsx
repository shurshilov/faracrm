import { ReactNode, ReactElement, Children, isValidElement } from 'react';
import { Tabs, Box, Badge } from '@mantine/core';
import classes from './FormLayout.module.css';
import { useFormTabExtensions, useTabExtensions } from '@/shared/extensions';

interface FormTabProps {
  name: string;
  label: string;
  icon?: ReactNode;
  badge?: number | string;
  children?: ReactNode;
}

/**
 * Одна вкладка внутри FormTabs
 */
export function FormTab({ children }: FormTabProps) {
  return <>{children}</>;
}

/**
 * Контент таба с расширениями.
 * Поддерживает позиции: before, after, replace
 */
function TabContent({ name, children }: { name: string; children: ReactNode }) {
  const { before, after, replace } = useTabExtensions(name);

  // Если есть replace - рендерим только его
  if (replace) {
    const Replace = replace;
    return <Replace />;
  }

  return (
    <>
      {before.map((Before, i) => (
        <Before key={`before-${i}`} />
      ))}
      {children}
      {after.map((After, i) => (
        <After key={`after-${i}`} />
      ))}
    </>
  );
}

interface FormTabsProps {
  children: ReactElement<FormTabProps> | ReactElement<FormTabProps>[];
  defaultTab?: string;
  variant?: 'default' | 'outline' | 'pills';
  orientation?: 'horizontal' | 'vertical';
}

/**
 * Вкладки для группировки связанных данных
 *
 * После вкладок из разметки идут вкладки модулей-расширений
 * (registerFormTab для модели формы), например «Реквизиты» партнёра
 * из fara_contract.
 *
 * @example
 * <FormTabs defaultTab="general">
 *   <FormTab name="general" label="Основное" icon={<IconUser />}>
 *     <Field name="name" />
 *   </FormTab>
 *   <FormTab name="files" label="Файлы" badge={5}>
 *     <Field name="image_ids" />
 *   </FormTab>
 * </FormTabs>
 */
export function FormTabs({
  children,
  defaultTab,
  variant = 'default',
  orientation = 'horizontal',
}: FormTabsProps) {
  const extensionTabs = useFormTabExtensions();

  // Извлекаем props из детей FormTab
  const tabs: FormTabProps[] = Children.toArray(children)
    .filter(
      (child): child is ReactElement<FormTabProps> =>
        isValidElement(child) && (child.type as any) === FormTab,
    )
    .map(child => child.props);

  for (const tab of extensionTabs) {
    const Content = tab.component;
    tabs.push({
      name: tab.name,
      label: tab.label,
      icon: tab.icon,
      children: <Content />,
    });
  }

  const firstTabName = tabs[0]?.name;
  const defaultValue = defaultTab || firstTabName;

  return (
    <Box className={classes.tabsContainer}>
      <Tabs
        defaultValue={defaultValue}
        variant={variant}
        orientation={orientation}
        classNames={{
          root: classes.tabsRoot,
          list: classes.tabsList,
          tab: classes.tab,
          panel: classes.tabPanel,
        }}>
        <Tabs.List>
          {tabs.map(tab => (
            <Tabs.Tab
              key={tab.name}
              value={tab.name}
              leftSection={tab.icon}
              rightSection={
                tab.badge !== undefined ? (
                  <Badge size="sm" variant="filled" radius="xl">
                    {tab.badge}
                  </Badge>
                ) : undefined
              }>
              {tab.label}
            </Tabs.Tab>
          ))}
        </Tabs.List>

        {tabs.map(tab => (
          <Tabs.Panel key={tab.name} value={tab.name} pt="md">
            <TabContent name={tab.name}>{tab.children}</TabContent>
          </Tabs.Panel>
        ))}
      </Tabs>
    </Box>
  );
}

FormTab.displayName = 'FormTab';
FormTabs.displayName = 'FormTabs';
