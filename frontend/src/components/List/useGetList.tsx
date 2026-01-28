// import { useSearchQuery } from '@/services/api/crudApi';
// import { FaraRecord, GetListParams, GetListResult } from './type';

// export const useGetList = <RecordType extends FaraRecord = any>(
//   resource: string,
//   params: GetListParams = {},
// ): GetListResult<RecordType> => {
//   console.log(resource, params);
//   const { data } = useSearchQuery({
//     model: resource,
//     order: params.order,
//     sort: params.sort,
//   });
//   console.log(data, '!!!!!!!!!!');

//   if (data) {
//     return data as GetListResult;
//   }
//   return undefined;

// };

// export type UseGetListHookValue<RecordType extends FaraRecord = any> =
//   RecordType[];
