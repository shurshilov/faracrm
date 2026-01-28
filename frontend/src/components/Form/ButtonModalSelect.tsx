import {
  Button,
  ButtonProps,
  Modal,
  Box,
  Text,
  TextInput,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useState, useEffect } from 'react';
import { DataTable, DataTableColumn } from 'mantine-datatable';
import { useSearchQuery } from '@/services/api/crudApi';
import {
  FaraRecord,
  GetListParams,
  GetListResult,
} from '@/services/api/crudTypes';
import { IconSearch } from '@tabler/icons-react';
import {
  BaseQueryFn,
  TypedUseQueryHookResult,
} from '@reduxjs/toolkit/query/react';

interface ButtonModalSelectProps {
  model: string;
  onSelect: (records: FaraRecord[]) => void;
  excludeIds?: number[];
  buttonProps?: ButtonProps & { children?: React.ReactNode };
}

const PAGE_SIZES = [10, 20, 40];

export function ButtonModalSelect({
  model,
  onSelect,
  excludeIds = [],
  buttonProps,
}: ButtonModalSelectProps) {
  const [opened, { open, close }] = useDisclosure(false);
  const [selectedRecords, setSelectedRecords] = useState<FaraRecord[]>([]);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZES[0]);

  // Сброс при открытии
  useEffect(() => {
    if (opened) {
      setSelectedRecords([]);
      setSearch('');
      setPage(1);
    }
  }, [opened]);

  // Формируем фильтр
  const filter: [string, string, any][] = [];
  if (search) {
    filter.push(['name', 'ilike', `%${search}%`]);
  }
  if (excludeIds.length > 0) {
    filter.push(['id', 'not in', excludeIds]);
  }

  const { data, isFetching } = useSearchQuery(
    {
      model,
      fields: ['id', 'name'],
      start: (page - 1) * pageSize,
      limit: pageSize,
      sort: 'name',
      order: 'ASC',
      filter: filter.length > 0 ? filter : undefined,
    },
    { skip: !opened },
  ) as TypedUseQueryHookResult<
    GetListResult<FaraRecord>,
    GetListParams,
    BaseQueryFn
  >;

  const handleConfirm = () => {
    if (selectedRecords.length > 0) {
      onSelect(selectedRecords);
    }
    close();
  };

  const columns: DataTableColumn<FaraRecord>[] = [
    {
      accessor: 'id',
      title: 'ID',
      width: 80,
    },
    {
      accessor: 'name',
      title: 'Название',
    },
  ];

  const { children: buttonChildren = 'Выбрать', ...restButtonProps } =
    buttonProps || {};

  return (
    <>
      <Modal
        opened={opened}
        onClose={close}
        title={`Выбор: ${model}`}
        centered
        size="lg">
        <Box mb="md">
          <TextInput
            placeholder="Поиск по названию..."
            leftSection={<IconSearch size={16} />}
            value={search}
            onChange={e => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </Box>

        <DataTable
          minHeight={300}
          withTableBorder
          borderRadius="sm"
          highlightOnHover
          fetching={isFetching}
          records={data?.data || []}
          columns={columns}
          selectedRecords={selectedRecords}
          onSelectedRecordsChange={setSelectedRecords}
          totalRecords={data?.total || 0}
          recordsPerPage={pageSize}
          page={page}
          onPageChange={setPage}
          recordsPerPageOptions={PAGE_SIZES}
          onRecordsPerPageChange={setPageSize}
          paginationText={({ from, to, totalRecords }) =>
            `${from}–${to} из ${totalRecords}`
          }
          noRecordsText="Записи не найдены"
        />

        <Box
          mt="md"
          style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button variant="default" onClick={close}>
            Отмена
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={selectedRecords.length === 0}>
            Выбрать ({selectedRecords.length})
          </Button>
        </Box>
      </Modal>

      <Button variant="filled" onClick={open} {...restButtonProps}>
        {buttonChildren}
      </Button>
    </>
  );
}
