import {
  Combobox,
  InputBase,
  useCombobox,
  Modal,
  CloseButton,
} from '@mantine/core';
import {
  MouseEvent as ReactMouseEvent,
  ReactElement,
  useContext,
  useEffect,
  useState,
  useMemo,
  Suspense,
} from 'react';
import { IconChevronDown } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useDisclosure } from '@mantine/hooks';
import { useTranslation } from 'react-i18next';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';
import { FormFieldsContext, useFormContext } from '../FormContext';
import { useSearchQuery, useCreateMutation } from '@/services/api/crudApi';
import {
  FaraRecord,
  GetListParams,
  GetListResult,
  Triplet,
} from '@/services/api/crudTypes';
import { FieldWrapper } from './FieldWrapper';
import { LabelPosition } from '../FormSettingsContext';
import { getModelViews } from '@/route/Routers';
import LoadingScreen from '../../LoadingScreen/LoadingScreen';

const QUICK_CREATE_VALUE = '__quick_create__';
const QUICK_CREATE_MODAL_VALUE = '__quick_create_modal__';

interface FieldMany2oneProps {
  name: string;
  label?: string;
  labelPosition?: LabelPosition;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  limit?: number;
  required?: boolean;
  /** Поле связанной модели для отображения и поиска. По умолчанию 'name'. */
  displayField?: string;
  /** Быстрое создание записи по введённому тексту. По умолчанию выкл. */
  quickCreate?: boolean;
  /** Поле, в которое писать введённый текст при быстром создании.
   *  По умолчанию = displayField (или 'name', если displayField='id'). */
  quickCreateField?: string;
  filter?: Triplet[] | ((values: Record<string, any>) => Triplet[]); // Статичный домен или функция
  [key: string]: any;
}

export const FieldMany2one = <RecordType extends FaraRecord>({
  name,
  label,
  labelPosition,
  sortKey = 'id',
  sortDirection = 'asc',
  limit = 10,
  required,
  displayField = 'name',
  quickCreate = false,
  quickCreateField,
  filter,
  ...props
}: FieldMany2oneProps) => {
  const form = useFormContext();
  const {
    fields: fieldsServer,
    handleFieldChange,
    onchangeFields,
  } = useContext(FormFieldsContext);
  const [search, setSearch] = useState('');
  const [options, setOptions] = useState<ReactElement[]>();
  const [startFetch, setStartFetch] = useState(false);
  const displayLabel = label ?? name;

  const relatedModel = fieldsServer[name]?.relatedModel || '';
  const [createRecord] = useCreateMutation();
  const createField =
    quickCreateField || (displayField !== 'id' ? displayField : 'name');

  const { t } = useTranslation('common');
  const [createOpened, { open: openCreate, close: closeCreate }] =
    useDisclosure(false);
  // Полноценная форма связанной модели для попапа «Создать и заполнить…».
  // RelatedForm — lazy-компонент (getModelViews), рендерим в Suspense.
  // Опцию показываем только если у модели есть зарегистрированная форма.
  const relatedViews = useMemo(
    () => getModelViews(relatedModel),
    [relatedModel],
  );
  const RelatedForm = relatedViews?.form;

  // Вычисляем домен - статичный или через функцию
  const filterDomain = useMemo((): Triplet[] => {
    if (!filter) return [];
    if (typeof filter === 'function') {
      return filter(form.values || {});
    }
    return filter;
  }, [filter, form.values]);

  const combinedFilter = useMemo(() => {
    const filters: Triplet[] = [];
    if (search) {
      filters.push([displayField, 'ilike', search]);
    }
    if (filterDomain.length > 0) {
      filters.push(...filterDomain);
    }
    return filters;
  }, [search, filterDomain]);

  const { data, isLoading } = useSearchQuery(
    {
      model: relatedModel,
      limit,
      sort: sortKey,
      order: sortDirection,
      fields: displayField === 'id' ? ['id'] : ['id', displayField],
      filter: combinedFilter,
    },
    {
      // Пропускаем только если dropdown не открыт и нет поиска
      skip: !startFetch && search === '',
    },
  ) as TypedUseQueryHookResult<
    GetListResult<RecordType>,
    GetListParams,
    BaseQueryFn
  >;

  useEffect(() => {
    if (data) {
      const optionsData = data.data.map(item => (
        <Combobox.Option value={item.id.toString()} key={item.id}>
          {item[displayField] ?? item.id}
        </Combobox.Option>
      ));
      setOptions(optionsData);
    }
  }, [data]);

  // Пункт "Создать «...»" — когда включён quickCreate, есть введённый
  // текст и нет точного совпадения по displayField.
  const trimmedSearch = search.trim();
  const hasExactMatch = useMemo(
    () =>
      !!data?.data.some(
        r =>
          String(r[displayField] ?? '').toLowerCase() ===
          trimmedSearch.toLowerCase(),
      ),
    [data, displayField, trimmedSearch],
  );
  const showQuickCreate =
    quickCreate && !!relatedModel && !!trimmedSearch && !hasExactMatch;
  // Попап доступен всегда, когда включён quickCreate и у модели есть форма
  // (даже без введённого текста — можно открыть пустую форму и заполнить).
  const showCreateModal = quickCreate && !!relatedModel && !!RelatedForm;

  const selectRecord = (record: FaraRecord | null) => {
    if (onchangeFields?.includes(name) && handleFieldChange) {
      handleFieldChange(name, record);
    } else {
      form.setValues({ [name]: record });
    }
  };

  // Очистка значения. null долетает до prepareValuesToSave как есть
  // (в число не конвертируется) → на бэк уходит null и связь снимается.
  const clearable = !required && !!form.getValues()[name];

  const combobox = useCombobox({
    onDropdownClose: () => {
      combobox.resetSelectedOption();
      combobox.focusTarget();
      setSearch('');
    },

    onDropdownOpen: () => {
      setStartFetch(true);
      combobox.focusSearchInput();
    },
  });

  return (
    <>
      {form.getValues() && (
        <FieldWrapper
          label={displayLabel}
          labelPosition={labelPosition}
          required={required}>
          <InputBase
            display={'none'}
            readOnly={true}
            key={form.key(name)}
            {...form.getInputProps(name)}
          />
          <Combobox
            {...props}
            {...form.getInputProps(name)}
            store={combobox}
            width={250}
            position="bottom-start"
            withArrow
            onOptionSubmit={async val => {
              if (val === QUICK_CREATE_MODAL_VALUE) {
                // «Создать и заполнить…» — открываем полную форму в модалке.
                combobox.closeDropdown();
                openCreate();
                return;
              }
              if (val === QUICK_CREATE_VALUE) {
                try {
                  const created = await createRecord({
                    model: relatedModel,
                    values: { [createField]: trimmedSearch },
                  }).unwrap();
                  selectRecord({
                    id: created.id,
                    [displayField]: trimmedSearch,
                  } as FaraRecord);
                } catch {
                  notifications.show({
                    color: 'red',
                    message: 'Не удалось создать запись',
                  });
                }
                combobox.closeDropdown();
                return;
              }
              if (data) {
                const record = data.data.find(obj => {
                  return obj.id.toString() === val;
                });
                if (record) {
                  selectRecord(record);
                }
              }
              combobox.closeDropdown();
            }}>
            <Combobox.Target>
              <InputBase
                component="button"
                type="button"
                pointer
                rightSection={
                  clearable ? (
                    // component="div": таргет комбобокса сам <button>,
                    // вложенная кнопка — невалидный DOM.
                    <CloseButton
                      component="div"
                      role="button"
                      aria-label={t('clear')}
                      title={t('clear')}
                      size="sm"
                      style={{ cursor: 'pointer' }}
                      onMouseDown={(event: ReactMouseEvent) => {
                        // Не даём таргету получить фокус → не открываем
                        // дропдаун вместо очистки.
                        event.preventDefault();
                        event.stopPropagation();
                      }}
                      onClick={(event: ReactMouseEvent) => {
                        event.stopPropagation();
                        selectRecord(null);
                        combobox.closeDropdown();
                      }}
                    />
                  ) : (
                    <IconChevronDown
                      size={16}
                      style={{
                        opacity: 0.4,
                        transition: 'transform 150ms ease',
                        transform: combobox.dropdownOpened
                          ? 'rotate(180deg)'
                          : 'rotate(0deg)',
                      }}
                    />
                  )
                }
                rightSectionPointerEvents={clearable ? 'auto' : 'none'}
                onClick={() => {
                  combobox.openDropdown();
                }}
                onFocus={() => combobox.openDropdown()}
                onBlur={() => combobox.closeDropdown()}>
                {form.getValues()[name] ? (
                  (form.getValues()[name][displayField] ??
                  form.getValues()[name].id)
                ) : (
                  <span style={{ opacity: 0.4 }}>Выбрать...</span>
                )}
              </InputBase>
            </Combobox.Target>

            <Combobox.Dropdown>
              <Combobox.Search
                value={search}
                onChange={event => {
                  setSearch(event.currentTarget.value);
                }}
                placeholder={'Поиск...'}
              />
              {/* Ограничение высоты со скроллом обязательно: без него список
                  (limit=10 + пункты «Создать…») вырастает высоким, Mantine
                  флипает дропдаун вверх, когда снизу мало места, и верх
                  списка уезжает за край экрана. Тот же приём в InlineCell. */}
              <Combobox.Options style={{ maxHeight: 240, overflowY: 'auto' }}>
                {isLoading ? (
                  <Combobox.Empty>Загрузка...</Combobox.Empty>
                ) : options && !!options.length ? (
                  options
                ) : !showQuickCreate && !showCreateModal ? (
                  <Combobox.Empty>Ничего не найдено</Combobox.Empty>
                ) : null}
                {showQuickCreate && (
                  <Combobox.Option
                    value={QUICK_CREATE_VALUE}
                    key={QUICK_CREATE_VALUE}>
                    <span style={{ color: 'var(--mantine-color-blue-6)' }}>
                      {t('createNamed', { name: trimmedSearch })}
                    </span>
                  </Combobox.Option>
                )}
                {showCreateModal && (
                  <Combobox.Option
                    value={QUICK_CREATE_MODAL_VALUE}
                    key={QUICK_CREATE_MODAL_VALUE}>
                    <span style={{ color: 'var(--mantine-color-blue-6)' }}>
                      {t('createAndFill')}
                    </span>
                  </Combobox.Option>
                )}
              </Combobox.Options>
            </Combobox.Dropdown>
          </Combobox>
        </FieldWrapper>
      )}

      {/* Попап «Создать и заполнить…»: полноценная форма связанной модели.
          onCreated возвращает созданную запись → сразу подставляем её
          значением поля; ButtonCreate внутри сам закрывает модалку. */}
      {showCreateModal && RelatedForm && (
        <Modal
          opened={createOpened}
          onClose={closeCreate}
          title={`${t('create')}: ${displayLabel}`}
          centered
          size="90%"
          styles={{ content: { maxWidth: 1100 } }}>
          <Suspense fallback={<LoadingScreen />}>
            <RelatedForm
              isCreateForm
              onCreated={(record: FaraRecord) => selectRecord(record)}
              modalClose={closeCreate}
            />
          </Suspense>
        </Modal>
      )}
    </>
  );
};
