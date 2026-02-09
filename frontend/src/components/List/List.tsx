import { Text } from '@mantine/core';
import {
  DataTable,
  DataTableColumn,
  DataTableSortStatus,
  useDataTableColumns,
} from 'mantine-datatable';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import { Children, isValidElement, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSearchQuery } from '@/services/api/crudApi';
import {
  FaraRecord,
  GetListParams,
  GetListResult,
  FilterExpression,
} from '@/services/api/crudTypes';
import { useFilters } from '@/components/SearchFilter/FilterContext';
import { BooleanCell } from '@/components/ListCells';
import { Field } from './Field';
import { Toolbar } from './Toolbar';
import useWindowDimensions from '@/services/hooks/useWindowDimensions';
import listClasses from './List.module.css';

const PAGE_SIZES = [10, 20, 40, 500, 1000, 2000];

interface ListProps<RecordType extends FaraRecord>
  extends Omit<GetListParams, 'fields' | 'sort'> {
  children: React.ReactNode;
  /** Sort field — type-checked against RecordType */
  sort?: keyof RecordType & string;
  /** Дополнительные кнопки для тулбара */
  toolbarActions?: React.ReactNode;
  /** Функция для определения класса строки */
  rowClassName?: (record: RecordType) => string;
  /** Callback для получения refetch функции */
  onRefetch?: (refetch: () => void) => void;
}

export const List = <RecordType extends FaraRecord>({
  children,
  toolbarActions,
  rowClassName,
  onRefetch,
  ...props
}: ListProps<RecordType>) => {
  const navigate = useNavigate();

  // Получаем фильтры из контекста
  const contextFilters = useFilters();

  // Объединяем фильтры из props и контекста
  const combinedFilters: FilterExpression = [
    ...(props.filter || []),
    ...contextFilters,
  ];

  // Debug
  console.log('List filters:', {
    contextFilters,
    combinedFilters,
    propsFilter: props.filter,
  });

  // pagination
  const [pageSize, setPageSize] = useState(PAGE_SIZES[1]);
  const [page, setPage] = useState(1);
  useEffect(() => {
    if (page !== 1) setPage(1);
  }, [pageSize]);

  // Сбрасываем страницу при изменении фильтров
  useEffect(() => {
    setPage(prev => (prev !== 1 ? 1 : prev));
  }, [contextFilters]);

  // height table without rows
  const { height } = useWindowDimensions();
  const [selectedRecords, setSelectedRecords] = useState<RecordType[]>([]);

  // sort
  const [sortStatus, setSortStatus] = useState<DataTableSortStatus<RecordType>>(
    {
      columnAccessor: props.sort || 'id',
      direction: props.order || 'asc',
    },
  );

  // Собираем список полей для запроса, скрытые поля и виртуальные колонки
  const hiddenFields: Set<string> = new Set();
  const virtualColumns: Array<{
    name: string;
    label?: string;
    render: (value: any, record: any) => React.ReactNode;
  }> = [];
  const fieldsList: string[] = [];

  Children.forEach(children, field => {
    if (!isValidElement(field) || field.type !== Field) {
      return;
    }
    const {
      name,
      hidden,
      fields: extraFields,
      virtual,
      label,
      render,
    } = field.props;

    // Виртуальная колонка — не добавляем name в запрос
    if (virtual) {
      if (render) {
        virtualColumns.push({ name, label, render });
      }
    } else {
      fieldsList.push(name);
      if (hidden) {
        hiddenFields.add(name);
      }
    }

    // Добавляем дополнительные поля для запроса
    if (extraFields) {
      for (const extraField of extraFields) {
        if (!fieldsList.includes(extraField)) {
          fieldsList.push(extraField);
          hiddenFields.add(extraField); // Дополнительные поля скрыты
        }
      }
    }
  });

  // Собираем кастомные render функции
  const customRenders: Record<
    string,
    (value: any, record: any) => React.ReactNode
  > = {};
  const customLabels: Record<string, string> = {};
  const customRelationDisplay: Record<string, 'badge' | 'text'> = {};
  const customBadgeColor: Record<string, string> = {};
  Children.forEach(children, field => {
    if (isValidElement(field) && field.type === Field) {
      if (field.props.render && !field.props.virtual) {
        customRenders[field.props.name] = field.props.render;
      }
      if (field.props.label) {
        customLabels[field.props.name] = field.props.label;
      }
      if (field.props.relationDisplay) {
        customRelationDisplay[field.props.name] = field.props.relationDisplay;
      }
      if (field.props.badgeColor) {
        customBadgeColor[field.props.name] = field.props.badgeColor;
      }
    }
  });

  const { data, refetch } = useSearchQuery({
    ...props,
    start: (page - 1) * pageSize,
    end: (page - 1) * pageSize + pageSize,
    sort: (sortStatus?.columnAccessor as string) || props.sort || 'id',
    order: sortStatus?.direction || props.order || 'asc',
    fields: fieldsList,
    filter: combinedFilters.length > 0 ? combinedFilters : undefined,
  }) as TypedUseQueryHookResult<
    GetListResult<RecordType>,
    GetListParams,
    BaseQueryFn
  >;

  // Передаём refetch наверх через callback (только при первом рендере)
  useEffect(() => {
    if (onRefetch) {
      onRefetch(refetch);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refetch]);

  // Dynamicly take column header
  const columns: DataTableColumn[] = [];
  const { effectiveColumns } = useDataTableColumns<RecordType>({
    // key: props.model,
    key: undefined,
    columns,
  });

  if (!data) {
    return null;
  }

  for (const field of data.fields) {
    // Пропускаем скрытые поля
    if (hiddenFields.has(field.name)) {
      continue;
    }

    const obj: DataTableColumn = {
      // accessorKey: field.name.toLowerCase(),
      accessor: field.name.toLowerCase(),
      title: customLabels[field.name] || field.name,
      sortable: true,
      resizable: true,
      sortKey: field.name.toLowerCase(),
      render: row => {
        const record = row[field.name] as RecordType;

        // Используем кастомный render если он есть
        if (customRenders[field.name]) {
          return customRenders[field.name](record, row);
        }

        // Boolean поля — зелёная светящаяся точка
        if (field.type === 'Boolean') {
          return <BooleanCell value={row[field.name] as boolean} />;
        }

        if (!record) {
          return null;
        }
        if (field.type === 'Many2many' || field.type === 'One2many') {
          const count = Array.isArray(record) ? record.length : 0;
          const display = customRelationDisplay[field.name] || 'badge';
          if (display === 'text') {
            return (
              <Text size="sm" c="dimmed">
                {count} записей
              </Text>
            );
          }
          const color = customBadgeColor[field.name];
          return (
            <span
              className={listClasses.recordsBadge}
              style={
                color
                  ? {
                      backgroundColor: `var(--mantine-color-${color}-1)`,
                      color: `var(--mantine-color-${color}-7)`,
                    }
                  : undefined
              }>
              {count} записей
            </span>
          );
        }
        if (field.type === 'Many2one') {
          return (
            <Text
              span
              onClick={event => {
                event.stopPropagation();
                navigate(`/${field.relation}/${record.id}`);
              }}>
              {`#${record.id}`}
            </Text>
          );
        }
        return <span>{`${record}`}</span>;
      },
    };
    columns.push(obj);
  }

  // Добавляем виртуальные колонки
  for (const vc of virtualColumns) {
    columns.push({
      accessor: vc.name,
      title: vc.label || vc.name,
      sortable: false,
      resizable: true,
      render: row => vc.render(null, row),
    });
  }

  return (
    <>
      <Toolbar
        selectedRecords={selectedRecords}
        model={props.model}
        extraActions={toolbarActions}
        onClearSelection={() => setSelectedRecords([])}
      />
      <DataTable
        minHeight={height * 0.82}
        withTableBorder={false}
        borderRadius="sm"
        // withColumnBorders
        striped
        highlightOnHover
        // provide data
        records={data?.data}
        noRecordsText="No records to show"
        // noRecordsIcon={
        //   <Box p={4} mb={4} className={classes.noRecordsBox}>
        //     <IconMoodSad size={36} strokeWidth={1.5} />
        //   </Box>
        // }
        // columns={columns}
        columns={effectiveColumns}
        storeColumnsKey={props.model}
        selectedRecords={selectedRecords}
        onSelectedRecordsChange={setSelectedRecords}
        onRowClick={({ record: { id } }) => navigate(`${id}`)}
        rowClassName={rowClassName as ((record: unknown) => string) | undefined}
        // pagination
        totalRecords={data.total}
        recordsPerPage={pageSize}
        page={page}
        onPageChange={p => setPage(p)}
        recordsPerPageOptions={PAGE_SIZES}
        onRecordsPerPageChange={setPageSize}
        // sort
        sortStatus={sortStatus}
        onSortStatusChange={setSortStatus}
      />
    </>
  );
};
