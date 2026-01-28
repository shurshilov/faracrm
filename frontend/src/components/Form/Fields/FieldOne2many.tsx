import {
  ActionIcon,
  Anchor,
  Box,
  Button,
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
  useMemo,
} from 'react';
import {
  FaraRecord,
  GetListParams,
  GetListResult,
} from '@/services/api/crudTypes';
import {
  DataTable,
  DataTableColumn,
  DataTableSortStatus,
  useDataTableColumns,
} from 'mantine-datatable';
import { useSearchQuery, useUpdateMutation } from '@/services/api/crudApi';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import { Field } from '@/components/List/Field';
import { ButtonModalSelect } from '../ButtonModalSelect';
import { ButtonModalCreate } from '../ButtonModalCreate';
import {
  IconTrash,
  IconLink,
  IconPlus,
  IconDatabaseOff,
} from '@tabler/icons-react';
import classes from './FieldRelation.module.css';

const PAGE_SIZES = [10, 20, 40, 100];

export const FieldOne2many = <RecordType extends FaraRecord>({
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
  const { fields: fieldsServer } = useContext(FormFieldsContext);
  const form = useFormContext();
  const defaulValues = form.getValues()[name] || [];
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const displayLabel = label ?? name;

  // Mutation для привязки записей
  const [update] = useUpdateMutation();

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
  const allRecords = useMemo(
    () => [...records, ...recordsCreated],
    [records, recordsCreated],
  );

  // Обработчик выбора существующих записей
  const handleSelectRecords = async (selectedItems: FaraRecord[]) => {
    const relatedModel = fieldsServer[name]?.relatedModel;
    const relatedField = fieldsServer[name]?.relatedField;

    if (!relatedModel || !relatedField || !id) return;

    // Привязываем каждую выбранную запись к текущей записи
    for (const item of selectedItems) {
      await update({
        model: relatedModel,
        id: item.id as number,
        values: { [relatedField]: Number(id) },
      });
    }

    // Добавляем записи локально для немедленного отображения
    const newRecords = selectedItems.map(item => ({
      ...item,
      _color: 'new' as const,
    })) as RecordType[];

    setRecords(prev => [...prev, ...newRecords]);
  };

  // Запрос к связанной модели с фильтром
  const { data, isFetching } = useSearchQuery(
    {
      ...props,
      model: fieldsServer[name]?.relatedModel || '',
      start: (page - 1) * pageSize,
      end: (page - 1) * pageSize + pageSize,
      limit: pageSize,
      sort: sortStatus.columnAccessor as string,
      order: sortStatus.direction,
      fields: fieldsList,
      filter: [[fieldsServer[name]?.relatedField || '', '=', Number(id)]],
    },
    { skip: !fieldsServer[name]?.relatedModel || !id },
  ) as TypedUseQueryHookResult<
    GetListResult<RecordType>,
    GetListParams,
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
        <Tooltip label="Удалить" position="left" withArrow>
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
                let old = { created: [], deleted: [] };
                if (parentFormName in form.getValues())
                  old = form.getValues()[parentFormName];

                let newDeleted = [...old.deleted, record.id];
                if (!record._color) {
                  for (let i = 0; i < old.deleted.length; i++) {
                    if (old.deleted[i] === record.id) {
                      old.deleted[i] = old.deleted[old.deleted.length - 1];
                      old.deleted.pop();
                      break;
                    }
                  }
                  newDeleted = [...old.deleted];
                }

                form.setValues({
                  [parentFormName]: {
                    deleted: newDeleted,
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

  const totalRecords = actualData?.total || allRecords.length;
  const isEmpty = allRecords.length === 0;

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
              model={fieldsServer[name]?.relatedModel || name}
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
              model={fieldsServer[name]?.relatedModel || name}
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
            storeColumnsKey={`${id}_${fieldsServer[name].relatedModel || name}`}
            selectedRecords={selectedRecords}
            onSelectedRecordsChange={setSelectedRecords}
            onRowClick={({ record: { id: recordId } }) => {
              if (recordId && !recordId.toString().startsWith('virtual')) {
                navigate(`/${fieldsServer[name].relatedModel}/${recordId}`);
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
