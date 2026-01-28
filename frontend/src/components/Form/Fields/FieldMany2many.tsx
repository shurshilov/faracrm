import {
  ActionIcon,
  Anchor,
  Box,
  Group,
  InputBase,
  Text,
  Tooltip,
} from '@mantine/core';
import { FormFieldsContext, useFormContext } from '../FormContext';
import { useNavigate, useParams, Link } from 'react-router-dom';
import {
  Children,
  isValidElement,
  useContext,
  useEffect,
  useState,
} from 'react';
import {
  FaraRecord,
  GetListM2mParams,
  GetListParams,
  GetListResult,
} from '@/services/api/crudTypes';
import {
  DataTable,
  DataTableColumn,
  DataTableSortStatus,
  useDataTableColumns,
} from 'mantine-datatable';
import { useSearchMany2manyQuery } from '@/services/api/crudApi';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import { Field } from '@/components/List/Field';
import {
  IconTrash,
  IconPlus,
  IconDatabaseOff,
  IconLink,
} from '@tabler/icons-react';
import { ButtonModalCreate } from '../ButtonModalCreate';
import { ButtonModalSelect } from '../ButtonModalSelect';
import classes from './FieldRelation.module.css';

const PAGE_SIZES = [10, 20, 40, 100];

export const FieldMany2many = <RecordType extends FaraRecord>({
  name,
  label,
  children,
  showCreate = false,
  showSelect = true,
  ...props
}: {
  name: string;
  label?: string;
  children: React.ReactNode;
  showCreate?: boolean;
  showSelect?: boolean;
} & Omit<GetListParams, 'fields' | 'model'>) => {
  const [records, setRecords] = useState<RecordType[]>([]);
  const [recordsCreated, setRecordsCreated] = useState<RecordType[]>([]);
  const { model: currentModel, fields: fieldsServer } =
    useContext(FormFieldsContext);
  const form = useFormContext();
  const defaulValues = form.getValues()[name];
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const displayLabel = label ?? name;

  // Pagination
  const [pageSize, setPageSize] = useState(PAGE_SIZES[0]);
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (page !== 1) setPage(1);
  }, [pageSize]);

  const [selectedRecords, setSelectedRecords] = useState<RecordType[]>([]);

  // Sort
  const [sortStatus, setSortStatus] = useState<DataTableSortStatus<RecordType>>(
    {
      columnAccessor: props.sort || 'id',
      direction: props.order || 'asc',
    },
  );

  const fieldsList =
    Children.map(children, field => {
      if (!isValidElement(field) || field.type !== Field) {
        return [];
      }
      return field.props.name;
    }) || [];

  // Получаем все текущие записи для исключения из выбора
  const allRecords = [...records, ...recordsCreated];

  // Обработчик выбора существующих записей
  const handleSelectRecords = (selectedItems: FaraRecord[]) => {
    // Добавляем в форму как selected
    const parentFormName = '_' + name;
    const old = form.getValues()[parentFormName] || {
      created: [],
      selected: [],
      unselected: [],
    };

    const newSelected = [
      ...(old.selected || []),
      ...selectedItems.map(item => item.id),
    ];

    form.setValues({
      [parentFormName]: {
        ...old,
        selected: newSelected,
        fieldsServer: fieldsServer,
      },
    });

    // Добавляем записи локально для немедленного отображения
    const newRecords = selectedItems.map(item => ({
      ...item,
      _color: 'new' as const,
    })) as RecordType[];

    setRecords(prev => [...prev, ...newRecords]);
  };

  // Запрос many2many - используем currentModel (модель формы), а не relatedModel
  const { data, isFetching } = useSearchMany2manyQuery(
    {
      id: Number(id),
      model: currentModel, // Модель текущей формы (например 'user')
      name: name, // Имя поля M2M (например 'role_ids')
      fields: fieldsList,
      start: (page - 1) * pageSize,
      end: (page - 1) * pageSize + pageSize,
      order: sortStatus.direction,
      sort: sortStatus.columnAccessor as string,
      limit: pageSize,
    },
    { skip: !currentModel || !id },
  ) as TypedUseQueryHookResult<
    GetListResult<RecordType>,
    GetListM2mParams,
    BaseQueryFn
  >;

  // Используем данные из запроса или дефолтные значения
  const actualData = data || defaulValues;

  useEffect(() => {
    if (actualData?.data) {
      const records: RecordType[] = actualData.data.map((row: FaraRecord) => ({
        ...row,
        _color: false,
      }));
      setRecords(records);
      setRecordsCreated([]);
    }
  }, [actualData]);

  useEffect(() => {
    const addCreated = form.getValues()['_' + name];
    if (addCreated) {
      setRecordsCreated(addCreated.created);
    }
  }, [form]);

  // Columns
  const columns: DataTableColumn[] = [];
  const { effectiveColumns } = useDataTableColumns<RecordType>({
    key: undefined,
    columns,
  });

  if (!actualData || !defaulValues) return null;
  if (!Object.keys(actualData).length && !Object.keys(defaulValues).length)
    return null;

  // Build columns from fields
  for (const field of actualData.fields || []) {
    const obj: DataTableColumn = {
      accessor: field.name.toLowerCase(),
      title: field.name,
      sortable: true,
      resizable: true,
      render: row => {
        const record = row[field.name] as RecordType;
        if (record === null || record === undefined) {
          return (
            <Text c="dimmed" size="sm">
              —
            </Text>
          );
        }
        if (field.type === 'Many2many' || field.type === 'One2many') {
          return (
            <span className={classes.recordsBadge}>
              {record.length} записей
            </span>
          );
        }
        if (field.type === 'Many2one') {
          const relationModel = field.relation || field.relatedModel;
          return (
            <Anchor
              component={Link}
              to={`/${relationModel}/${record?.id}`}
              size="sm"
              onClick={event => event.stopPropagation()}>
              {record?.name || `#${record?.id}`}
            </Anchor>
          );
        }
        return <Text size="sm">{`${record}`}</Text>;
      },
    };
    columns.push(obj);
  }

  // Actions column
  columns.push({
    accessor: 'actions',
    title: '',
    width: 50,
    sortable: false,
    render: record => (
      <Group
        gap={4}
        justify="center"
        wrap="nowrap"
        className={classes.rowActions}>
        <Tooltip label="Отвязать" position="left" withArrow>
          <ActionIcon
            size="sm"
            variant="subtle"
            color="red"
            onClick={event => {
              event.stopPropagation();
              if (record._color === 'delete') record._color = false;
              else record._color = 'delete';

              if (record.id && !record.id.toString().startsWith('virtual')) {
                const parentFormName = '_' + name;
                let old = { created: [], unselected: [] };
                if (parentFormName in form.getValues())
                  old = form.getValues()[parentFormName];

                let newUnselected = [...old.unselected, record.id];
                if (!record._color) {
                  for (let i = 0; i < old.unselected.length; i++) {
                    if (old.unselected[i] === record.id) {
                      old.unselected[i] =
                        old.unselected[old.unselected.length - 1];
                      old.unselected.pop();
                      break;
                    }
                  }
                  newUnselected = [...old.unselected];
                }

                form.setValues({
                  [parentFormName]: {
                    unselected: newUnselected,
                    created: old.created,
                    fieldsServer: fieldsServer,
                  },
                });
              }
            }}>
            <IconTrash size={14} />
          </ActionIcon>
        </Tooltip>
      </Group>
    ),
  });

  // allRecords уже определен выше
  const totalRecords = actualData?.total || allRecords.length;
  const isEmpty = allRecords.length === 0;

  // Связанная модель для навигации
  const relatedModel = fieldsServer[name]?.relatedModel;

  return (
    <Box className={classes.tableContainer}>
      {/* Hidden input for form */}
      <InputBase
        display="none"
        readOnly
        key={form.key(name)}
        {...form.getInputProps(name)}
      />

      {/* Header */}
      <Box className={classes.tableHeader}>
        <Box className={classes.tableTitle}>
          <Text className={classes.tableTitleText}>{displayLabel}</Text>
          {!isEmpty && (
            <Text className={classes.recordCount}>({totalRecords})</Text>
          )}
        </Box>
        <Group gap="xs">
          {showSelect && (
            <ButtonModalSelect
              model={relatedModel || name}
              excludeIds={allRecords.map(r => r.id as number).filter(Boolean)}
              onSelect={handleSelectRecords}
              buttonProps={{
                size: 'xs',
                variant: 'light',
                leftSection: <IconLink size={14} />,
                className: classes.addButton,
                children: 'Выбрать',
              }}
            />
          )}
          {showCreate && (
            <ButtonModalCreate
              model={relatedModel || name}
              relatedFieldO2M={fieldsServer[name]?.relatedField}
              parentFieldName={name}
              parentId={Number(id)}
              buttonProps={{
                size: 'xs',
                variant: 'light',
                leftSection: <IconPlus size={14} />,
                className: classes.addButton,
                children: 'Создать',
              }}
            />
          )}
        </Group>
      </Box>

      {/* Empty state or Table */}
      {isEmpty ? (
        <Box className={classes.emptyState}>
          <IconDatabaseOff
            size={40}
            stroke={1.5}
            className={classes.emptyIcon}
          />
          <Text className={classes.emptyText}>Нет записей</Text>
        </Box>
      ) : (
        <Box className={classes.tableWrapper}>
          <DataTable
            minHeight={100}
            withTableBorder={false}
            borderRadius={0}
            highlightOnHover
            fetching={isFetching}
            records={allRecords}
            columns={effectiveColumns}
            storeColumnsKey={`${id}_${relatedModel || name}`}
            selectedRecords={selectedRecords}
            onSelectedRecordsChange={setSelectedRecords}
            onRowClick={({ record: { id: recordId } }) => {
              if (
                recordId &&
                !recordId.toString().startsWith('virtual') &&
                relatedModel
              ) {
                navigate(`/${relatedModel}/${recordId}`);
              }
            }}
            // Pagination
            totalRecords={totalRecords}
            recordsPerPage={pageSize}
            page={page}
            onPageChange={setPage}
            recordsPerPageOptions={PAGE_SIZES}
            onRecordsPerPageChange={setPageSize}
            paginationText={({ from, to, totalRecords }) =>
              `${from}–${to} из ${totalRecords}`
            }
            // Sort
            sortStatus={sortStatus}
            onSortStatusChange={setSortStatus}
            // Row styling
            rowBackgroundColor={({ _color }) => {
              if (_color === 'new')
                return { dark: '#232b25', light: '#f0f7f1' };
              if (_color === 'delete')
                return { dark: '#3d302f', light: '#f2e8e8' };
              return undefined;
            }}
            // Styling
            styles={{
              header: {
                backgroundColor: 'var(--mantine-color-gray-0)',
              },
              pagination: {
                borderTop: '1px solid var(--mantine-color-gray-3)',
              },
            }}
          />
        </Box>
      )}
    </Box>
  );
};
