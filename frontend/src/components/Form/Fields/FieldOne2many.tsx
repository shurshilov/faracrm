import {
  ActionIcon,
  Box,
  Button,
  Group,
  InputBase,
  Text,
  Tooltip,
} from '@mantine/core';
import { FormFieldsContext, useFormContext } from '../FormContext';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Children,
  isValidElement,
  useContext,
  useEffect,
  useState,
  useMemo,
  ComponentType,
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
  IconExternalLink,
} from '@tabler/icons-react';
import { InlineCell } from './InlineCell';
import {
  BooleanCell,
  RelationCell,
  DateTimeCell,
} from '@/components/ListCells';
import classes from './FieldRelation.module.css';

const PAGE_SIZES = [10, 20, 40, 100];

export const FieldOne2many = <RecordType extends FaraRecord>({
  name,
  label,
  children,
  showCreate = false,
  showSelect = true,
  displayField = 'name',
  customForm = undefined,
  deleteSoft = true,
  inline_create = false,
  inline_update = false,
  quickCreateFields = [],
  parentField,
  showDelete = true,
  ...props
}: {
  name: string;
  label?: string;
  children: React.ReactNode;
  showCreate?: boolean;
  showSelect?: boolean;
  displayField?: string;
  customForm?: ComponentType;
  deleteSoft?: boolean;
  /** Режим инлайн-редактирования. Ячейки становятся input-ами. */
  inline_create?: boolean;
  inline_update?: boolean;
  /** Имена Many2one-колонок, для которых в инлайн-редакторе
   *  доступно быстрое создание записи по имени. По умолчанию []. */
  quickCreateFields?: string[];
  /**
   * Имя Many2one-поля ФОРМЫ, чьё значение — владелец записей (вместо id
   * текущей записи), как у ContactsWidget. Напр. parentField="partner_id"
   * на заказе: звонки клиента (call.partner_id = заказ.partner_id).
   */
  parentField?: string;
  /** Кнопка удаления/отвязки в строке. false — таблица только для просмотра. */
  showDelete?: boolean;
} & Omit<GetListParams, 'fields' | 'model'>) => {
  const [records, setRecords] = useState<RecordType[]>([]);
  const [recordsCreated, setRecordsCreated] = useState<RecordType[]>([]);
  const { fields: fieldsServer } = useContext(FormFieldsContext);
  const form = useFormContext();
  const defaulValues = form.getValues()[name] || [];
  const { id } = useParams<{ id: string }>();

  // Владелец записей для запроса: значение parentField из формы, иначе id
  // текущей записи из URL.
  const parentValue = parentField ? form.getValues()?.[parentField] : null;
  const ownerId: number | null = parentField
    ? typeof parentValue === 'object' && parentValue !== null
      ? parentValue.id
      : typeof parentValue === 'number'
        ? parentValue
        : null
    : id
      ? Number(id)
      : null;
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
      if (!isValidElement<Record<string, any>>(field) || field.type !== Field) {
        return [];
      }
      return field.props.name;
    }) || [];

  // Собираем label-ы и render-ы из children <Field label="..." render={...} />
  // для заголовков и ячеек колонок (как в List)
  const customLabels: Record<string, string> = {};
  const customRenders: Record<
    string,
    (value: any, record: RecordType) => React.ReactNode
  > = {};
  Children.forEach(children, field => {
    if (!isValidElement<Record<string, any>>(field) || field.type !== Field) {
      return;
    }
    if (field.props.label) {
      customLabels[field.props.name] = field.props.label;
    }
    if (field.props.render) {
      customRenders[field.props.name] = field.props.render;
    }
  });

  // Получаем все текущие записи для исключения из выбора
  const allRecords = useMemo(
    () => [...records, ...recordsCreated],
    [records, recordsCreated],
  );

  // Если его нет — поле удаляется из запроса (else { delete values[field.name] }).
  // Дефолтные значения o2m приходят в 'fieldName' как {data, fields, total},
  // но '_fieldName' никогда не создаётся — данные теряются при сохранении.
  //
  // Решение: при монтировании на форме создания (нет id) инициализируем
  // '_fieldName.created' из записей дефолтных данных,
  // имитируя ручное создание пользователем (O2M использует created, не selected).
  useEffect(() => {
    if (id) return; // только форма создания
    if (!defaulValues?.data?.length) return; // нет дефолтных записей

    const parentFormName = '_' + name;
    if (form.getValues()[parentFormName]) return; // уже инициализировано

    form.setValues({
      [parentFormName]: {
        created: defaulValues.data, // имитируем ручное создание строк
        deleted: [],
        fieldsServer: fieldsServer,
      },
    });
    // Помечаем форму dirty — кнопка Create становится активной
    form.setDirty({ [parentFormName]: true });
  }, [defaulValues, id]);
  // ────────────────────────────────────────────────────────────────────────

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
        values: { [relatedField]: Number(id) } as any,
      });
    }

    // Добавляем записи локально для немедленного отображения
    const newRecords = selectedItems.map(item => ({
      ...item,
      _color: 'new' as const,
    })) as unknown as RecordType[];

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
      filter: [[fieldsServer[name]?.relatedField || '', '=', ownerId ?? 0]],
    },
    { skip: !fieldsServer[name]?.relatedModel || !ownerId },
  ) as TypedUseQueryHookResult<
    GetListResult<RecordType>,
    GetListParams,
    BaseQueryFn
  >;

  // Используем данные из запроса или дефолтные значения
  const actualData = data || defaulValues;

  // Проблема: defaulValues читается через form.getValues() на каждом рендере
  // и возвращает НОВУЮ ссылку даже если содержимое не менялось. Из-за этого
  // useEffect ниже срабатывал при любом изменении формы (например при вводе
  // имени пользователя) и перезаписывал уже добавленные пользователем
  // записи (через Создать).
  //
  // Решение: content-key через JSON.stringify по всему набору строк
  // (не только по id). Это:
  //   - не реагирует на смену ссылки defaulValues, пока контент не менялся
  //     (React сравнивает строки по значению, useEffect не дёрнется);
  //   - реагирует на ИЗМЕНЕНИЕ ПОЛЕЙ в существующих строках — иначе после
  //     PUT'а и refetch'а `search` пересчитанные на бэке
  //     price_subtotal / price_total и т.п. не доезжали до UI: набор id
  //     строк прежний → старый id-only ключ совпадал → setRecords не звался.
  const serverRecordsKey = JSON.stringify(actualData?.data ?? null);

  useEffect(() => {
    if (!actualData?.data) return;

    const serverRecords: RecordType[] = actualData.data.map(
      (row: FaraRecord) => ({
        ...row,
        // На форме создания (нет id) дефолтные записи подсвечиваем зелёным —
        // как если бы пользователь добавил их вручную
        _color: !id ? 'new' : false,
      }),
    );

    // На форме создания у нас могут быть ручные добавления — они хранятся
    // в records/recordsCreated. НЕ сбрасываем recordsCreated: пользователь
    // уже нажал "Создать" и хранит там строки. Мержим records: server +
    // manuallySelectedIds из _form-state (для случаев ButtonModalSelect,
    // хотя на create форме он обычно не работает).
    if (!id) {
      const formState = form.getValues()['_' + name];
      const manuallySelectedIds: number[] = formState?.selected || [];
      setRecords(prev => {
        const serverIds = new Set(serverRecords.map(r => r.id).filter(Boolean));
        const manualOnly = prev.filter(
          r =>
            r.id &&
            manuallySelectedIds.includes(r.id as number) &&
            !serverIds.has(r.id),
        );
        return [...serverRecords, ...manualOnly];
      });
      // recordsCreated НЕ сбрасываем — там строки созданные через ButtonModalCreate
    } else {
      // На форме редактирования берём данные с сервера
      setRecords(serverRecords);
      setRecordsCreated([]);
    }
  }, [serverRecordsKey, id]);

  // Мост form-state → recordsCreated, СИММЕТРИЧНЫЙ и реактивный по
  // СОДЕРЖИМОМУ patch'а (не по ссылке form, которая в Mantine v8
  // стабильна и не триггерит этот эффект на setValues).
  //
  // Покрывает ВЕСЬ цикл одним правилом — recordsCreated всегда равен
  // form['_' + name].created (или [], если patch пустой/удалён):
  //   • modal-create (ButtonCreate в модалке) → parentForm._name.created;
  //   • inline-add / inline-edit / delete виртуалки;
  //   • post-Save cleanup в ButtonUpdate → patch undefined → []
  //   • любая правка из других мест.
  //
  // Дeп — JSON.stringify content'а patch'а: пока контент одинаковый —
  // эффект не запускается; как только содержимое изменилось — синк.
  // FormProvider Mantine v8 ре-рендерит consumer'ов на setValues, так
  // что patchKey тут гарантированно перевычисляется при изменениях.
  const patchKey = JSON.stringify(form.getValues()['_' + name] || null);
  useEffect(() => {
    const patch = form.getValues()['_' + name];
    setRecordsCreated(patch?.created || []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patchKey]);

  // Columns — ВАЖНО: массив собирается ПОЛНОСТЬЮ ниже, ДО вызова
  // useDataTableColumns. mantine-datatable v9: хук снимает useMemo-снимок
  // columns в момент вызова, поздний push в него не виден (таблица покажет
  // только колонку-чекбокс). Поэтому хук перенесён ПОСЛЕ сборки колонок.
  const columns: DataTableColumn<RecordType>[] = [];

  // Inline change handler: обновляет значение в записи и пишет в form
  const handleInlineCellChange = (
    row: any,
    fieldName: string,
    newValue: any,
  ) => {
    // Обновляем запись в allRecords
    const rowId = row.id;
    const isVirtual = rowId?.toString().startsWith('virtual');

    if (isVirtual) {
      // Новая (created) запись — обновляем в recordsCreated
      setRecordsCreated(prev =>
        prev.map(r => (r.id === rowId ? { ...r, [fieldName]: newValue } : r)),
      );
    } else {
      // Существующая запись — обновляем локально + пишем в _name
      setRecords(prev =>
        prev.map(r => (r.id === rowId ? { ...r, [fieldName]: newValue } : r)),
      );
    }

    // Обновляем _fieldName для сохранения
    const parentFormName = '_' + name;
    const old = form.getValues()[parentFormName] || {
      created: [],
      deleted: [],
      updated: {},
      unselected: [],
    };

    if (isVirtual) {
      // Обновляем created запись
      const updatedCreated = (old.created || []).map((c: any) =>
        c.id === rowId ? { ...c, [fieldName]: newValue } : c,
      );
      form.setValues({
        [parentFormName]: { ...old, created: updatedCreated },
      });
    } else {
      // Для существующих записей — собираем updated dict
      const updated = { ...(old.updated || {}) };
      if (!updated[rowId]) updated[rowId] = {};
      updated[rowId][fieldName] = newValue;
      form.setValues({
        [parentFormName]: { ...old, updated },
      });
    }

    form.setDirty({ [parentFormName]: true });
  };

  // Build columns from fields (actualData может быть ещё не загружен —
  // тогда массив полей пустой; ранний выход ниже, после вызова хука).
  for (const field of actualData?.fields || []) {
    const obj: DataTableColumn<RecordType> = {
      accessor: field.name.toLowerCase(),
      title: customLabels[field.name] || field.name,
      sortable: !inline_update,
      resizable: true,
      render: row => {
        const cellValue = row[field.name];

        // Inline mode — рендерим input
        if (inline_update) {
          return (
            <InlineCell
              value={cellValue}
              fieldName={field.name}
              fieldType={field.type}
              options={field.options}
              relation={field.relation || field.relatedModel}
              quickCreate={quickCreateFields.includes(field.name)}
              onChange={newValue =>
                handleInlineCellChange(row, field.name, newValue)
              }
            />
          );
        }

        // Readonly mode (default). Кастомный render дочернего <Field>
        // (как в List) рисует ячейку целиком, включая пустое значение.
        const customRender = customRenders[field.name];
        if (customRender) {
          return customRender(cellValue, row);
        }
        if (cellValue === null || cellValue === undefined) {
          // Для Boolean null трактуем как false — всё равно рисуем кружок
          if (field.type === 'Boolean') {
            return <BooleanCell value={false} />;
          }
          return (
            <Text c="dimmed" size="sm">
              —
            </Text>
          );
        }
        if (field.type === 'Many2many' || field.type === 'One2many') {
          return (
            <span className={classes.recordsBadge}>
              {cellValue.length} записей
            </span>
          );
        }
        if (field.type === 'Many2one') {
          const relationModel = field.relation || field.relatedModel;
          return (
            <RelationCell
              value={cellValue}
              model={relationModel}
              variant="link"
            />
          );
        }
        if (field.type === 'Boolean') {
          return <BooleanCell value={Boolean(cellValue)} />;
        }
        if (field.type === 'Datetime' || field.type === 'Date') {
          return (
            <DateTimeCell
              value={cellValue}
              format={field.type === 'Date' ? 'date' : 'full'}
            />
          );
        }
        return <Text size="sm">{`${cellValue}`}</Text>;
      },
    };
    columns.push(obj);
  }

  // Actions column
  columns.push({
    accessor: 'actions',
    title: '',
    width: 80,
    sortable: false,
    render: (record: any) => (
      <Group
        gap={4}
        justify="center"
        wrap="nowrap"
        className={classes.rowActions}>
        {/* Открыть запись в её форме (drill-in). Доступно всегда,
            в т.ч. при inline_update, когда onRowClick отключён. */}
        {record.id && !record.id.toString().startsWith('virtual') && (
          <Tooltip label="Открыть" position="left" withArrow>
            <ActionIcon
              size="sm"
              variant="subtle"
              color="gray"
              onClick={event => {
                event.stopPropagation();
                navigate(`/${fieldsServer[name].relatedModel}/${record.id}`);
              }}>
              <IconExternalLink size={14} />
            </ActionIcon>
          </Tooltip>
        )}
        {showDelete && (
        <Tooltip label="Удалить" position="left" withArrow>
          <ActionIcon
            size="sm"
            variant="subtle"
            color="red"
            onClick={event => {
              event.stopPropagation();

              // Виртуальная строка ещё не на сервере → soft-delete не
              // имеет смысла. Полностью убираем её и из локального
              // recordsCreated, и из form['_' + name].created, чтобы на
              // Save она просто не ушла. Никакого `_color = 'delete'` тут
              // не выставляем — строка должна исчезнуть.
              if (record.id?.toString().startsWith('virtual')) {
                setRecordsCreated(prev =>
                  prev.filter(r => r.id !== record.id),
                );
                const parentFormName = '_' + name;
                const old = form.getValues()[parentFormName] || {
                  created: [],
                  deleted: [],
                };
                form.setValues({
                  [parentFormName]: {
                    ...old,
                    created: (old.created || []).filter(
                      (c: any) => c.id !== record.id,
                    ),
                  },
                });
                return;
              }

              if (!record.id) return;

              // Real-row soft/hard delete с поддержкой множественного
              // выбора и toggle (повторный клик — снять флаг удаления).
              //
              // BUG was: код читал `old.deleted` и при deleteSoft=true
              // писал в `old.unselected`, не зная что предыдущий клик
              // уже положил id'ы туда же. На втором клике `old.deleted`
              // оказывался undefined → spread бросал TypeError, состояние
              // в форме не обновлялось, но record._color уже мутирован —
              // отсюда «покрашена только одна строка из нескольких».
              //
              // Fix: ключ выбирается один раз исходя из deleteSoft и
              // используется и для чтения, и для записи; toggle через
              // filter без мутации массива; record._color обновляется
              // ТОЛЬКО если форма успешно записана.
              const parentFormName = '_' + name;
              const deletedKey = deleteSoft ? 'unselected' : 'deleted';
              const old = form.getValues()[parentFormName] || {};
              const currentDeleted: (number | string)[] =
                old[deletedKey] || [];
              const alreadyMarked = currentDeleted.includes(
                record.id as number,
              );

              const newDeleted = alreadyMarked
                ? currentDeleted.filter(itemId => itemId !== record.id)
                : [...currentDeleted, record.id];

              form.setValues({
                [parentFormName]: {
                  ...old,
                  [deletedKey]: newDeleted,
                  created: old.created || [],
                  fieldsServer: fieldsServer,
                },
              });
              form.setDirty({ [parentFormName]: true });

              // Локальная пометка цветом: переключаем относительно того,
              // что мы только что записали в форму. Прямая мутация record
              // оставлена для совместимости с DataTable rowBackgroundColor,
              // но теперь она консистентна с состоянием формы.
              record._color = alreadyMarked ? false : 'delete';
              // Принудительно перерендерим таблицу: меняем records по
              // ссылке, чтобы DataTable увидел новый _color.
              setRecords(prev => [...prev]);
            }}>
            <IconTrash size={14} />
          </ActionIcon>
        </Tooltip>
        )}
      </Group>
    ),
  });

  // Массив колонок готов — теперь зовём хук (снимок увидит все колонки).
  const { effectiveColumns } = useDataTableColumns<RecordType>({
    key: undefined,
    columns,
  });

  if (!actualData || !defaulValues) return null;
  if (!Object.keys(actualData).length && !Object.keys(defaulValues).length)
    return null;

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
              relatedFieldO2M={fieldsServer[name]?.relatedField}
              parentId={Number(id)}
              displayField={displayField}
              buttonProps={{
                size: 'xs',
                variant: 'light',
                leftSection: <IconLink size={14} />,
                className: classes.addButton,
                children: 'Выбрать',
              }}
            />
          )}
          {showCreate && !inline_create && (
            <ButtonModalCreate
              model={fieldsServer[name]?.relatedModel || name}
              relatedFieldO2M={fieldsServer[name]?.relatedField}
              parentFieldName={name}
              parentId={Number(id)}
              customForm={customForm}
              buttonProps={{
                size: 'xs',
                variant: 'light',
                leftSection: <IconPlus size={14} />,
                className: classes.addButton,
                children: 'Создать',
              }}
            />
          )}
          {/* Inline add row — добавляет пустую строку прямо в таблицу */}
          {showCreate && inline_create && (
            <Button
              size="xs"
              variant="light"
              leftSection={<IconPlus size={14} />}
              className={classes.addButton}
              onClick={() => {
                const oldSource = form.getValues()[name] || { total: 0 };
                const parentFormName = '_' + name;
                const old = form.getValues()[parentFormName] || {
                  created: [],
                  deleted: [],
                };
                const virtualId =
                  'virtual' + ((oldSource.total || 0) + old.created.length);

                // Новая пустая строка с FK на родителя
                const newRow: any = {
                  id: virtualId,
                  _color: 'new',
                  [fieldsServer[name]?.relatedField || '']: id
                    ? Number(id)
                    : 'VirtualId',
                };
                // Заполняем пустые значения для всех полей
                for (const f of actualData?.fields || []) {
                  if (!(f.name in newRow)) {
                    newRow[f.name] = null;
                  }
                }

                setRecordsCreated(prev => [...prev, newRow as RecordType]);
                form.setValues({
                  [parentFormName]: {
                    ...old,
                    created: [...old.created, newRow],
                    fieldsServer: fieldsServer,
                  },
                });
                form.setDirty({ [parentFormName]: true });
              }}>
              Добавить строку
            </Button>
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
            onRowClick={
              inline_update
                ? undefined
                : ({ record: { id: recordId } }: { record: RecordType }) => {
                    if (
                      recordId &&
                      !recordId.toString().startsWith('virtual')
                    ) {
                      navigate(
                        `/${fieldsServer[name].relatedModel}/${recordId}`,
                      );
                    }
                  }
            }
            // Пагинация — как в списках: показываем только если
            // total больше размера страницы по умолчанию
            // (PAGE_SIZES[0]); иначе всё помещается на одну страницу
            // и пагинация не нужна.
            {...((totalRecords > PAGE_SIZES[0]
              ? {
                  totalRecords,
                  recordsPerPage: pageSize,
                  page,
                  onPageChange: setPage,
                  recordsPerPageOptions: PAGE_SIZES,
                  onRecordsPerPageChange: setPageSize,
                }
              : {}) as any)}
            paginationText={({
              from,
              to,
              totalRecords,
            }: {
              from: number;
              to: number;
              totalRecords: number;
            }) => `${from}–${to} из ${totalRecords}`}
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
