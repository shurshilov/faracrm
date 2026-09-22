/**
 * ListMenu — кнопка «⋮» в шапке списка. Внутри — настройка колонок и, если
 * установлен модуль excel, экспорт текущей выборки и импорт из файла
 * (экспорт выбранных строк — в меню Actions). Поповер колонок якорится на
 * эту же кнопку: ColumnsMenu оборачивает меню, пункт лишь открывает его.
 */
import { ActionIcon, Menu, Tooltip } from '@mantine/core';
import {
  IconAdjustments,
  IconDotsVertical,
  IconFileExport,
  IconFileImport,
} from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

interface ListMenuProps {
  onColumns: () => void;
  /** Пункты Excel; нет — модуль не установлен. */
  excel?: { export: () => void; import: () => void };
}

export function ListMenu({ onColumns, excel }: ListMenuProps) {
  const { t } = useTranslation('excel');

  return (
    <Menu shadow="md" position="bottom-end" withinPortal>
      <Menu.Target>
        <Tooltip label="Ещё">
          <ActionIcon variant="subtle" color="gray" size="md">
            <IconDotsVertical size={18} />
          </ActionIcon>
        </Tooltip>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Item
          leftSection={<IconAdjustments size={14} />}
          onClick={onColumns}>
          Колонки
        </Menu.Item>
        {excel && (
          <>
            <Menu.Divider />
            <Menu.Item
              leftSection={<IconFileExport size={14} />}
              onClick={excel.export}>
              {t('exportAll')}
            </Menu.Item>
            <Menu.Item
              leftSection={<IconFileImport size={14} />}
              onClick={excel.import}>
              {t('import')}
            </Menu.Item>
          </>
        )}
      </Menu.Dropdown>
    </Menu>
  );
}
