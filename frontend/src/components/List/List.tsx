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
import {
  Children,
  isValidElement,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import {
  FaraRecord,
  GetListField,
  GetListParams,
  GetListResult,
} from '@/services/api/crudTypes';
import { useGetFieldsQuery } from '@/services/api/crudApi';
import { useFilters } from '@/components/SearchFilter/FilterContext';
import {
  readInitialFilter,
  useFilteredSearchQuery,
} from '@/components/SearchFilter/useFilteredSearchQuery';
import { BooleanCell } from '@/components/ListCells';
import { buildRecordNav, RecordNavState } from '@/components/RecordNav';
import { Field } from './Field';
import { Toolbar } from './Toolbar';
import { ColumnsMenu } from './ColumnsMenu';
import { useColumnConfig } from './useColumnConfig';
import { useHeaderSlot } from '@/components/ViewWrapper/HeaderSlotContext';
import {
  loadViewState,
  saveViewState,
  useIsReturningToView,
} from '@/components/ViewWrapper/viewStateStore';
import listClasses from './List.module.css';

const PAGE_SIZES = [10, 20, 40, 500, 1000, 2000];

/** UI-состояние списка, восстанавливаемое при возврате из формы. */
interface ListUiState<RecordType> {
  page: number;
  pageSize: number;
  sort: DataTableSortStatus<RecordType>;
}
const listUiKey = (model: string) => `list:${model}`;

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
  /** Показывать ли массовые действия в тулбаре (по умолчанию выключено). */
  massActions?: boolean;
}

export const List = <RecordType extends FaraRecord>({
  children,
  toolbarActions,
  rowClassName,
  onRefetch,
  massActions = true,
  ...props
}: ListProps<RecordType>) => {
  const navigate = useNavigate();
  const location = useLocation();

  // Общий фильтр вью из FilterContext. Здесь он нужен только для сброса
  // страницы при его изменении (см. эффект ниже). В сам запрос его —
  // вместе с props.filter и stateFilter x2m-навигации — подмешивает
  // useFilteredSearchQuery.
  const contextFilters = useFilters();

  // Debug
  // console.log('List filters:', {
  //   contextFilters,
  //   combinedFilters,
  //   propsFilter: props.filter,
  // });

  // Страница/размер/сортировка: при ВОЗВРАТЕ к списку («К списку» на форме,
  // браузерное «назад») — из снимка, иначе с начала. Снимок обновляется при
  // каждом изменении (эффект ниже), см. viewStateStore.
  const isReturning = useIsReturningToView();
  const [restored] = useState(() =>
    isReturning
      ? loadViewState<ListUiState<RecordType>>(listUiKey(props.model))
      : null,
  );

  // pagination
  const [pageSize, setPageSize] = useState(restored?.pageSize ?? PAGE_SIZES[1]);
  const [page, setPage] = useState(restored?.page ?? 1);

  // Сбрасываем страницу при РЕАЛЬНОМ изменении фильтров. Сравниваем по
  // значению, а не по ссылке: SearchFilter переизлучает структурно тот же
  // массив (обновление подписей чипсов после загрузки полей), а при
  // возврате из формы восстановленная страница должна уцелеть.
  const filtersKey = JSON.stringify(contextFilters);
  const prevFiltersKey = useRef(filtersKey);
  useEffect(() => {
    if (prevFiltersKey.current === filtersKey) return;
    prevFiltersKey.current = filtersKey;
    setPage(1);
  }, [filtersKey]);

  const [selectedRecords, setSelectedRecords] = useState<RecordType[]>([]);

  // sort
  const [sortStatus, setSortStatus] = useState<DataTableSortStatus<RecordType>>(
    restored?.sort ?? {
      columnAccessor: props.sort || 'id',
      direction: props.order || 'asc',
    },
  );

  useEffect(() => {
    const snapshot: ListUiState<RecordType> = { page, pageSize, sort: sortStatus };
    saveViewState(listUiKey(props.model), snapshot);
  }, [props.model, page, pageSize, sortStatus]);

  // Собираем поля для запроса, дефолтные видимые колонки и виртуальные
  const virtualColumns: Array<{
    name: string;
    label?: string;
    render: (value: any, record: any) => React.ReactNode;
  }> = [];
  const fieldsList: string[] = [];
  // Колонки вью «по умолчанию» — реальные, не скрытые, не виртуальные.
  // От них считается стартовый выбор колонок (см. useColumnConfig ниже).
  const defaultVisibleFields: string[] = [];

  Children.forEach(children, field => {
    if (!isValidElement<Record<string, any>>(field) || field.type !== Field) {
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
      // Скрытая колонка (<Field hidden>) — запрашиваем, но по умолчанию
      // не показываем (пользователь может добавить её через меню колонок).
      if (!hidden) {
        defaultVisibleFields.push(name);
      }
    }

    // Дополнительные поля для запроса (помощники кастом-рендеров) — только
    // в запрос, в дефолтные колонки не попадают.
    if (extraFields) {
      for (const extraField of extraFields) {
        if (!fieldsList.includes(extraField)) {
          fieldsList.push(extraField);
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
    if (isValidElement<Record<string, any>>(field) && field.type === Field) {
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

  // Пользовательский выбор колонок (per-user, per-model). По умолчанию —
  // колонки вью (defaultVisibleFields). allFields — метаданные всех полей
  // модели: нужны и для меню колонок, и для сборки только что добавленных
  // колонок до прихода нового ответа поиска.
  const columnConfig = useColumnConfig(props.model, defaultVisibleFields);
  const { data: allFields } = useGetFieldsQuery(props.model);

  // Слот в шапке ViewWrapper: если он есть — «шестерёнку» настройки колонок
  // рендерим туда (портал), а не в тулбар списка. Вне ViewWrapper слота нет
  // (null) — тогда фолбэк в собственный тулбар (см. columnsControl ниже).
  const headerSlot = useHeaderSlot();

  // Записать выбор колонок при размонтировании, если меню закрыть не успели
  // (навигация с открытым поповером). Guard по dirty — внутри хука.
  const persistRef = useRef(columnConfig.persistIfDirty);
  persistRef.current = columnConfig.persistIfDirty;
  useEffect(() => () => persistRef.current(), []);

  // Известные (не-private) поля модели из /fields. Пока грузятся — null.
  const knownFieldNames = allFields
    ? new Set(allFields.map(f => f.name))
    : null;

  // Видимые колонки, очищенные от неизвестных/приватных полей. private-поля
  // (password_hash и т.п.) больше не отдаются в /fields, и их НЕЛЬЗЯ
  // запрашивать в search — иначе 422 и пустой список (а с ним пропадёт и
  // тулбар с «шестерёнкой», чинить нечем). Такое возможно из устаревшего
  // сохранённого набора, где private-поле осталось с прошлых версий.
  const selectedColumns = knownFieldNames
    ? columnConfig.selected.filter(n => knownFieldNames.has(n))
    : columnConfig.selected;

  // Запрашиваем всё, что нужно вью (fieldsList: видимые по умолчанию +
  // скрытые «помощники» для кастомных рендеров) ПЛЮС добавленные
  // пользователем колонки. Скрытие дефолтной колонки не убирает её из
  // запроса — так кастомные рендеры соседних колонок не ломаются.
  // Пользовательские колонки добавляем только когда набор полей известен
  // (allFields загружен) — чтобы устаревшее private-поле не улетело в search.
  const requestFields = Array.from(
    new Set([...fieldsList, ...(knownFieldNames ? selectedColumns : [])]),
  );

  const { data, refetch, originalArgs } = useFilteredSearchQuery({
    ...props,
    start: (page - 1) * pageSize,
    end: (page - 1) * pageSize + pageSize,
    sort: (sortStatus?.columnAccessor as string) || props.sort || 'id',
    order: sortStatus?.direction || props.order || 'asc',
    fields: requestFields,
    // filter (props.filter) приходит через ...props выше; stateFilter
    // и общий фильтр вью добавляет useFilteredSearchQuery.
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

  // ⚠️ ВАЖНО (mantine-datatable v9): массив `columns` нужно собрать ПОЛНОСТЬЮ
  // ДО вызова useDataTableColumns. В v9 хук делает useMemo-снимок переданного
  // массива в момент вызова (deps: [columns, order, toggle, pinning, width]).
  // Раньше колонки пушились в пустой массив ПОСЛЕ вызова хука — на v8 это
  // «дотекало» (effectiveColumns ссылался на тот же массив), а на v9 снимок
  // остаётся пустым и таблица рисует только колонку-чекбокс выделения.
  // Поэтому строим колонки здесь, затем зовём хук, и только потом ранний return.
  const columns: DataTableColumn[] = [];

  if (data) {
    // Метаданные по имени поля: приоритет — из ответа поиска (data.fields),
    // добор — из полного списка полей модели (allFields), чтобы только что
    // добавленная колонка появилась сразу, не дожидаясь рефетча.
    const metaByName = new Map<string, GetListField>();
    for (const f of data.fields) metaByName.set(f.name, f);
    if (allFields) {
      for (const f of allFields) {
        if (!metaByName.has(f.name)) metaByName.set(f.name, f as GetListField);
      }
    }

    // Колонки строим в порядке пользовательского выбора (selectedColumns —
    // уже очищен от приватных/неизвестных полей).
    for (const fieldName of selectedColumns) {
      const field = metaByName.get(fieldName);
      if (!field) continue; // метаданные ещё не подгрузились

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
  }

  // Теперь массив колонок готов — снимок хука увидит их все.
  const { effectiveColumns } = useDataTableColumns<RecordType>({
    // key: props.model,
    key: undefined,
    columns,
  });

  if (!data) {
    return null;
  }

  // Контрол настройки колонок. Живёт в шапке вида (портал в слот
  // ViewWrapper), а вне ViewWrapper (слота нет) — в тулбаре списка.
  const columnsMenu = (
    <ColumnsMenu
      model={props.model}
      selected={selectedColumns}
      isCustom={columnConfig.isCustom}
      onChange={columnConfig.setDraft}
      onReset={columnConfig.reset}
      onClose={columnConfig.persistIfDirty}
    />
  );

  return (
    <>
      {headerSlot && createPortal(columnsMenu, headerSlot)}
      <Toolbar
        selectedRecords={selectedRecords}
        model={props.model}
        fields={data.fields}
        massActions={massActions}
        extraActions={toolbarActions}
        onClearSelection={() => setSelectedRecords([])}
        columnsControl={headerSlot ? undefined : columnsMenu}
      />
      <DataTable
        minHeight={200}
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
        onRowClick={({
          record,
          index,
        }: {
          record: RecordType;
          index: number;
        }) => {
          // Форме — контекст навигации по этой выборке: параметры запроса
          // как ушли на бэк (originalArgs), позиция записи и total. По нему
          // форма листает соседей и возвращается сюда (см. RecordNav).
          const state: RecordNavState | undefined = originalArgs && {
            recordNav: buildRecordNav(
              originalArgs,
              (page - 1) * pageSize + index,
              data.total,
              readInitialFilter(location.state),
            ),
          };
          navigate(`${record.id}`, { state });
        }}
        rowClassName={rowClassName as ((record: unknown) => string) | undefined}
        // pagination — показываем только если total > минимального pageSize,
        // иначе нет смысла (всё помещается на одну страницу).
        {...((data?.total > PAGE_SIZES[1]
          ? {
              totalRecords: data?.total,
              recordsPerPage: pageSize,
              page,
              onPageChange: (p: number) => setPage(p),
              recordsPerPageOptions: PAGE_SIZES,
              onRecordsPerPageChange: (size: number) => {
                setPageSize(size);
                setPage(1);
              },
            }
          : {}) as any)}
        // sort
        sortStatus={sortStatus}
        onSortStatusChange={setSortStatus}
      />
    </>
  );
};
