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
  GetAttachmentParams,
  GetListM2mParams,
  GetListParams,
  GetListResult,
  ReadDefaultValuesParams,
  ReadDefaultValuesResult,
  ReadParams,
  ReadResult,
} from './crudTypes';

// Define a service using a base URL and expected endpoints
export const crudApi = createApi({
  reducerPath: 'crudApi',
  baseQuery: baseQueryWithReauth,
  keepUnusedDataFor: 30,
  // global configuration for the api
  // refetchOnReconnect: true,
  tagTypes: ['Fields', 'SavedFilters'],
  endpoints: build => ({
    search: build.query<GetListResult<FaraRecord>, GetListParams>({
      query: queryArg => ({
        method: 'POST',
        url: `/${queryArg.model}/search`,
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
      providesTags: (result, error, arg) => {
        // return result
        return result
          ? [
              { type: arg.model, id: 'LIST' },
              ...result?.data.map(
                ({ id }) => ({ type: arg.model, id }) as FaraRecord,
              ),
            ]
          : [{ type: arg.model, id: 'LIST' } as FaraRecord];
      },

      // forceRefetch: () => true,
      // serializeQueryArgs: ({ endpointName, queryArgs }) =>
      //   `${endpointName}-${queryArgs?.model}`,
    }),

    searchMany2many: build.query<GetListResult<FaraRecord>, GetListM2mParams>({
      query: queryArg => ({
        method: 'GET',
        url: `/${queryArg.model}/search_many2many`,
        params: queryArg,
        // body: {
        //   id: queryArg.id,
        //   name: queryArg.name,
        //   fields: queryArg.fields,
        //   order: queryArg.order,
        //   start: queryArg.start,
        //   end: queryArg.end,
        //   sort: queryArg.sort,
        //   limit: queryArg.limit,
        // },
      }),
      // providesTags: (result, error, arg) => {
      //   // return result
      //   return result
      //     ? [
      //         { type: arg.model, id: 'LIST' },
      //         ...result?.data.map(
      //           ({ id }) => ({ type: arg.model, id }) as FaraRecord,
      //         ),
      //       ]
      //     : [{ type: arg.model, id: 'LIST' } as FaraRecord];
      // },

      // forceRefetch: () => true,
      // serializeQueryArgs: ({ endpointName, queryArgs }) =>
      //   `${endpointName}-${queryArgs?.model}`,
    }),

    deleteBulk: build.mutation<DeleteListResult, DeleteListParams>({
      query: queryArg => ({
        url: `/${queryArg.model}/bulk`,
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
        url: `/${queryArg.model}/${queryArg.id}`,
        // params: { fields: queryArg.fields },
        method: 'POST',
        body: {
          fields: queryArg.fields,
        },
      }),
      providesTags: (result, error, arg) =>
        // result ? [{ type: arg.model, id: arg.id }, arg.model] : [arg.model],
        [{ type: arg.model, id: arg.id }],
    }),

    readDefaultValues: build.query<
      ReadDefaultValuesResult<FaraRecord>,
      ReadDefaultValuesParams
    >({
      query: queryArg => ({
        url: `/${queryArg.model}/default_values`,
        method: 'POST',
        body: {
          fields: queryArg.fields,
        },
      }),
      providesTags: (result, error, arg) => [arg.model],
    }),

    update: build.mutation<EditResult<FaraRecord>, EditParams<FaraRecord>>({
      query: queryArg => ({
        url: `/${queryArg.model}/${queryArg.id}`,
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
        // We also have another copy of the same data in the `read` cache
        // entry for this record ID, so we need to update that as well
        const readPatchResult = lifecycleApi.dispatch(
          crudApi.util.updateQueryData(
            'read',
            { model, id, fields: Object.keys(values) },
            draft => Object.assign(draft, values),
          ),
        );

        // при возврате в список сделать запрос
        // так как данные обновили только в форме
        lifecycleApi.dispatch(
          crudApi.util.invalidateTags([{ type: model, id: 'LIST' }]),
        );

        // нужно ли делать запрос в любом случае?
        // минусы: 1 лишний запрос 1 лишний ререндер
        // плюсы: более свежии подтвержденные данные
        lifecycleApi.dispatch(
          crudApi.util.invalidateTags([{ type: model, id: id }]),
        );
        // также инвалидируем связанные модели o2m и m2m
        // console.log(invalidateTags, 'invalidateTags');
        // invalidateTags?.map(modelRelation =>
        //   crudApi.util.invalidateTags([{ type: modelRelation, id: 'LIST' }]),
        // );

        try {
          await lifecycleApi.queryFulfilled;
        } catch {
          readPatchResult.undo();
        }
      },
    }),

    create: build.mutation<CreateResult, CreateParams<Omit<FaraRecord, 'id'>>>({
      query: queryArg => ({
        url: `/${queryArg.model}`,
        method: 'POST',
        body: queryArg.values,
      }),
      invalidatesTags: (result, error, arg) =>
        // result ? [{ type: arg.model, id: result.id }, arg.model] : [arg.model],
        [{ type: arg.model, id: 'LIST' }],
    }),

    getAttachment: build.query<string, GetAttachmentParams>({
      // hour
      keepUnusedDataFor: 0,
      query: queryArg => {
        return {
          url: `/attachments/${queryArg.id}`,
          method: 'GET',
          credentials: 'omit',
          responseHandler: async response => {
            console.log(response.headers);
            // if get svg just return it as text
            // if (
            //   response.headers.map['content-type'] ===
            //   'image/svg+xml; charset=utf-8'
            // ) {
            //   return response.text();
            // }
            // if get binary like image/png? convert it to base64
            const fileReaderInstance = new FileReader();
            if (!response.ok) {
              throw new Error(response.statusText);
            }
            // const blob = await response.blob();
            return response.blob();
            // return fileReaderInstance.readAsDataURL(blob);
            // return response;

            // return new Promise((resolve, _) => {
            //   fileReaderInstance.onload = () => {
            //     console.log(
            //       fileReaderInstance.result,
            //       'ileReaderInstance.result',
            //     );
            //     resolve(fileReaderInstance.result);
            //     return fileReaderInstance.result;
            //   };
            // });
          },
        };
      },
      transformResponse: async (response: Blob | void, meta: any) => {
        if (response instanceof Blob) {
          const { response: metaResponse } = meta;
          const filename = metaResponse.headers
            .get('Content-Disposition')
            .split('filename=')[1];
          // const contentType = metaResponse.headers.get('Content-Type');
          // const file = new File([response], filename, {
          //   type: contentType,
          // });
          // const url = window.URL.createObjectURL(file);
          // window.open(url);

          const url = window.URL.createObjectURL(response);

          const link = document.createElement('a');
          console.log(url);
          link.href = url;
          link.setAttribute('download', filename);

          // Append to html link element page
          document.body.appendChild(link);

          // Start download
          link.click();

          // Clean up and remove the link
          link.parentNode.removeChild(link);
        }
      },
    }),

    // Onchange endpoints
    getOnchangeFields: build.query<{ fields: string[] }, { model: string }>({
      query: ({ model }) => ({
        method: 'GET',
        url: `/onchange/${model}`,
      }),
    }),

    executeOnchange: build.mutation<
      { values: Record<string, any> },
      { model: string; trigger_field: string; values: Record<string, any> }
    >({
      query: ({ model, trigger_field, values }) => ({
        method: 'POST',
        url: `/onchange`,
        body: { model, trigger_field, values },
      }),
    }),
  }),
});

export const {
  useLazySearchQuery,
  useSearchQuery,
  useGetAttachmentQuery,
  useSearchMany2manyQuery,
  useDeleteBulkMutation,
  useReadQuery,
  useReadDefaultValuesQuery,
  useUpdateMutation,
  useCreateMutation,
  useGetOnchangeFieldsQuery,
  useExecuteOnchangeMutation,
} = crudApi;
