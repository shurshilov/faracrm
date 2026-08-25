// Need to use the React-specific entry point to import createApi
import { createApi } from '@reduxjs/toolkit/query/react';
import { baseQueryWithReauth } from '@services/baseQueryWithReauth';
import {
  CreateParams,
  CreateResult,
  DeleteListParams,
  DeleteListResult,
  EditParams,
  EditResult,
  FaraRecord,
  GetListM2mParams,
  GetListParams,
  GetListResult,
  ReadDefaultValuesParams,
  ReadDefaultValuesResult,
  ReadParams,
  ReadResult,
  UpdateBulkParams,
  UpdateBulkResult,
} from './crudTypes';

// Prefix для автогенерированных CRUD роутов бекенда
const AUTO = '/auto';

// Define a service using a base URL and expected endpoints
export const crudApi = createApi({
  reducerPath: 'crudApi',
  baseQuery: baseQueryWithReauth,
  keepUnusedDataFor: 30,
  // global configuration for the api
  // refetchOnReconnect: true,
  // Универсальный CRUD-API работает по ЛЮБОЙ модели → теги динамические
  // ({ type: <имя модели> }). Поэтому набор тегов открытый (string), а не
  // замкнутый union — иначе RTK 2.12 ругается на { type: arg.model }.
  tagTypes: [
    'Fields',
    'SavedFilters',
    'ColumnSettings',
    'Chat',
    'ChatMessage',
  ] as string[],
  endpoints: build => ({
    search: build.query<GetListResult<FaraRecord>, GetListParams>({
      query: queryArg => ({
        method: 'POST',
        url: `${AUTO}/${queryArg.model}/search`,
        body: {
          end: queryArg.end,
          order: queryArg.order,
          sort: queryArg.sort,
          start: queryArg.start,
          filter: queryArg.filter,
          fields: queryArg.fields,
          limit: queryArg.limit,
          raw: queryArg.raw,
        },
      }),
      providesTags: (result, _error, arg) =>
        result
          ? [
              { type: arg.model, id: 'LIST' },
              ...result.data.map(({ id }) => ({ type: arg.model, id })),
            ]
          : [{ type: arg.model, id: 'LIST' }],

      // forceRefetch: () => true,
      // serializeQueryArgs: ({ endpointName, queryArgs }) =>
      //   `${endpointName}-${queryArgs?.model}`,
    }),

    searchMany2many: build.query<GetListResult<FaraRecord>, GetListM2mParams>({
      query: queryArg => ({
        method: 'GET',
        url: `${AUTO}/${queryArg.model}/search_many2many`,
        params: queryArg,
      }),
      providesTags: (_result, _error, arg) => [
        { type: arg.model, id: `M2M_${arg.id}_${arg.name}` },
      ],
    }),

    deleteBulk: build.mutation<DeleteListResult, DeleteListParams>({
      query: queryArg => ({
        url: `${AUTO}/${queryArg.model}/bulk`,
        method: 'DELETE',
        body: queryArg.ids,
      }),
      // invalidatesTags: (result, error, arg) => [
      //   ...arg.ids.map(id => ({ type: arg.model, id })),
      // ],

      // The `invalidatesTags` line has been removed,
      // since we're now doing optimistic updates
      async onQueryStarted({ model, ids }, lifecycleApi) {
        // `updateQueryData` requires the endpoint name and cache key arguments,
        // so it knows which piece of cache state to update
        // var startTime = performance.now();
        // let idsDeleted = ids.slice();
        const searchPatchResults = [];
        for (const {
          endpointName,
          originalArgs,
        } of crudApi.util.selectInvalidatedBy(lifecycleApi.getState(), [
          { type: model },
        ])) {
          // we only want to update `search` here
          if (endpointName !== 'search') continue;
          searchPatchResults.push(
            lifecycleApi.dispatch(
              crudApi.util.updateQueryData('search', originalArgs, draft => {
                // find in list & update
                // console.log('START');
                // console.log(idsDeleted);
                // console.log(draft.data);
                // for (let i = idsDeleted.length - 1; i >= 0; i--) {
                //   for (let j = draft.data.length - 1; j >= 0; j--) {
                //     console.log(idsDeleted[i], draft.data[j].id);
                //     if (idsDeleted[i] === draft.data[j].id) {
                //       console.log('FOUND');
                //       idsDeleted.pop();
                //       draft.data[j] = draft.data[draft.data.length - 1];
                //       draft.data.pop();
                //     }
                //   }
                // }
                // draft.data = draft.data.slice();
                draft.data = draft.data.filter(x => {
                  return !ids.includes(x.id);
                });
              }),
            ),
          );
        }
        // var endTime = performance.now();
        // console.log(`Call to delete took ${endTime - startTime} milliseconds`);

        // нужно ли делать запрос в любом случае?
        // минусы: 1 лишний запрос 1 лишний ререндер
        // плюсы: более свежии подтвержденные данные
        // ВАЖНО! обновиться также тотал каунт в пагинации
        // поэтому лучше оставить инвалидацию
        lifecycleApi.dispatch(
          crudApi.util.invalidateTags([{ type: model, id: 'LIST' }]),
        );

        // также инвалидируем `read` записи формы
        ids.map(id =>
          lifecycleApi.dispatch(
            crudApi.util.invalidateTags([{ type: model, id: id }]),
          ),
        );

        try {
          await lifecycleApi.queryFulfilled;
        } catch {
          searchPatchResults.map(id => id.undo());
        }
      },
    }),

    read: build.query<ReadResult<FaraRecord>, ReadParams>({
      query: queryArg => ({
        url: `${AUTO}/${queryArg.model}/${queryArg.id}`,
        // params: { fields: queryArg.fields },
        method: 'POST',
        body: {
          fields: queryArg.fields,
        },
      }),
      providesTags: (_result, _error, arg) =>
        // result ? [{ type: arg.model, id: arg.id }, arg.model] : [arg.model],
        [{ type: arg.model, id: arg.id }],
    }),

    readDefaultValues: build.query<
      ReadDefaultValuesResult<FaraRecord>,
      ReadDefaultValuesParams
    >({
      query: queryArg => ({
        url: `${AUTO}/${queryArg.model}/default_values`,
        method: 'POST',
        body: {
          fields: queryArg.fields,
        },
      }),
      providesTags: (_result, _error, arg) => [arg.model],
    }),

    updateBulk: build.mutation<UpdateBulkResult, UpdateBulkParams>({
      query: ({ model, ids, values }) => ({
        url: `${AUTO}/${model}/bulk`,
        method: 'PUT',
        body: { ids, values },
      }),
      // После массового апдейта перечитываем список и каждую затронутую
      // запись (открытая форма / кеш read).
      invalidatesTags: (_result, _error, arg) => [
        { type: arg.model, id: 'LIST' },
        ...arg.ids.map(id => ({ type: arg.model, id })),
      ],
    }),

    update: build.mutation<EditResult<FaraRecord>, EditParams<FaraRecord>>({
      query: queryArg => ({
        url: `${AUTO}/${queryArg.model}/${queryArg.id}`,
        method: 'PUT',
        body: queryArg.values,
      }),
      // invalidatesTags: (result, error, arg) => [
      //   { type: arg.model, id: arg.id },
      // ],

      // The `invalidatesTags` line has been removed,
      // since we're now doing optimistic updates
      async onQueryStarted(
        { model, id, values, invalidateTags },
        lifecycleApi,
      ) {
        // Optimistic patch read-кеша только по СКАЛЯРНЫМ полям. O2M/M2M
        // приходят сюда как command-dict {created/updated/deleted/...} —
        // это формат payload'а на запись, а не "состояние записи". Если
        // запихнуть его в кеш напрямую, форма прочитает order_line_ids
        // как command-dict и собьёт рендер O2M-таблицы.
        const isCommandDict = (v: unknown): boolean =>
          !!v &&
          typeof v === 'object' &&
          !Array.isArray(v) &&
          ('created' in (v as any) ||
            'updated' in (v as any) ||
            'deleted' in (v as any) ||
            'unselected' in (v as any) ||
            'selected' in (v as any));

        const scalarValues = Object.fromEntries(
          Object.entries(values).filter(([, v]) => !isCommandDict(v)),
        );
        const readPatchResult = lifecycleApi.dispatch(
          crudApi.util.updateQueryData(
            'read',
            { model, id, fields: Object.keys(values) },
            draft => Object.assign(draft, scalarValues),
          ),
        );

        try {
          await lifecycleApi.queryFulfilled;

          // ВАЖНО: refetch — только ПОСЛЕ того, как PUT отработал на
          // сервере. Раньше GET успевал стартануть, пока PUT ещё летел,
          // забирал из БД старые computed-поля строк (price_subtotal и др.),
          // и финальный PUT уже не триггерил повторного refetch'а.
          // Итог: O2M-строки висели stale до полного F5.
          //
          // То же и для списка: он инвалидировался рано в расчёте, что
          // подписчиков на него сейчас нет. Но живая подписка бывает прямо
          // на форме — например виджет контактов (FieldContacts держит
          // useSearchQuery по contact) — и она успевала перечитать СТАРОЕ
          // значение поверх только что отредактированного.
          lifecycleApi.dispatch(
            crudApi.util.invalidateTags([
              { type: model, id: id },
              { type: model, id: 'LIST' },
            ]),
          );

          // Инвалидируем M2M/O2M кеши для затронутых полей
          if (invalidateTags?.length) {
            const m2mTags = invalidateTags.map(fieldName => ({
              type: model,
              id: `M2M_${id}_${fieldName}`,
            }));
            lifecycleApi.dispatch(crudApi.util.invalidateTags(m2mTags));
          }
        } catch {
          readPatchResult.undo();
        }
      },
    }),

    create: build.mutation<CreateResult, CreateParams<Omit<FaraRecord, 'id'>>>({
      query: queryArg => ({
        url: `${AUTO}/${queryArg.model}`,
        method: 'POST',
        body: queryArg.values,
      }),
      invalidatesTags: (_result, _error, arg) =>
        // result ? [{ type: arg.model, id: result.id }, arg.model] : [arg.model],
        [{ type: arg.model, id: 'LIST' }],
    }),

    // getAttachment: build.query<string, GetAttachmentParams>({
    //   // hour
    //   keepUnusedDataFor: 0,
    //   query: queryArg => {
    //     return {
    //       url: `/attachments/${queryArg.id}`,
    //       method: 'GET',
    //       credentials: 'include',
    //       responseHandler: async response => {
    //         console.log(response.headers);
    //         // if get svg just return it as text
    //         // if (
    //         //   response.headers.map['content-type'] ===
    //         //   'image/svg+xml; charset=utf-8'
    //         // ) {
    //         //   return response.text();
    //         // }
    //         // if get binary like image/png? convert it to base64
    //         const fileReaderInstance = new FileReader();
    //         if (!response.ok) {
    //           throw new Error(response.statusText);
    //         }
    //         // const blob = await response.blob();
    //         return response.blob();
    //         // return fileReaderInstance.readAsDataURL(blob);
    //         // return response;

    //         // return new Promise((resolve, _) => {
    //         //   fileReaderInstance.onload = () => {
    //         //     console.log(
    //         //       fileReaderInstance.result,
    //         //       'ileReaderInstance.result',
    //         //     );
    //         //     resolve(fileReaderInstance.result);
    //         //     return fileReaderInstance.result;
    //         //   };
    //         // });
    //       },
    //     };
    //   },
    //   transformResponse: async (response: Blob | void, meta: any) => {
    //     if (response instanceof Blob) {
    //       const { response: metaResponse } = meta;
    //       const filename = metaResponse.headers
    //         .get('Content-Disposition')
    //         .split('filename=')[1];
    //       // const contentType = metaResponse.headers.get('Content-Type');
    //       // const file = new File([response], filename, {
    //       //   type: contentType,
    //       // });
    //       // const url = window.URL.createObjectURL(file);
    //       // window.open(url);

    //       const url = window.URL.createObjectURL(response);

    //       const link = document.createElement('a');
    //       console.log(url);
    //       link.href = url;
    //       link.setAttribute('download', filename);

    //       // Append to html link element page
    //       document.body.appendChild(link);

    //       // Start download
    //       link.click();

    //       // Clean up and remove the link
    //       link.parentNode.removeChild(link);
    //     }
    //   },
    // }),

    // Onchange endpoints
    getOnchangeFields: build.query<{ fields: string[] }, { model: string }>({
      query: ({ model }) => ({
        method: 'GET',
        url: `/onchange/${model}`,
      }),
    }),

    executeOnchange: build.mutation<
      { values: Record<string, any>; fields?: Record<string, any> },
      { model: string; trigger_field: string; values: Record<string, any> }
    >({
      query: ({ model, trigger_field, values }) => ({
        method: 'POST',
        url: `/onchange`,
        body: { model, trigger_field, values },
      }),
    }),

    // Получение списка полей модели для фильтрации
    getFields: build.query<FieldInfoResponse[], string>({
      query: model => ({
        url: `${AUTO}/${model}/fields`,
        method: 'GET',
      }),
      providesTags: (_result, _error, model) => [{ type: 'Fields', id: model }],
    }),

    // Поля модели по её env-имени (значение models.name) — для конструктора
    // шаблонов папок маршрута вложений. Позволяет предлагать выбор только
    // существующих полей выбранной модели вместо ручного ввода {поле}.
    // Бэкенд: GET /attachments/model_fields/{model_name}.
    getRouteModelFields: build.query<FieldInfoResponse[], string>({
      query: modelName => ({
        url: `/attachments/model_fields/${modelName}`,
        method: 'GET',
      }),
      providesTags: (_result, _error, modelName) => [
        { type: 'Fields', id: `route-model:${modelName}` },
      ],
    }),
  }),
});

export interface FieldInfoResponse {
  name: string;
  type: string;
  relation?: string;
  options?: string[];
  required?: boolean;
}

export const {
  useLazySearchQuery,
  useSearchQuery,
  // useGetAttachmentQuery,
  useSearchMany2manyQuery,
  useDeleteBulkMutation,
  useReadQuery,
  useReadDefaultValuesQuery,
  useUpdateMutation,
  useUpdateBulkMutation,
  useCreateMutation,
  useGetOnchangeFieldsQuery,
  useExecuteOnchangeMutation,
  useGetFieldsQuery,
  useGetRouteModelFieldsQuery,
} = crudApi;
