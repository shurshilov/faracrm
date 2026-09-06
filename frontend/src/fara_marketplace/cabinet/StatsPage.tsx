import {
  Badge,
  Container,
  Paper,
  SimpleGrid,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useTranslation } from 'react-i18next';
import { useGetMarketStatsQuery } from '../api';

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Paper withBorder p="md" radius="md">
      <Text size="xs" c="dimmed" tt="uppercase">
        {label}
      </Text>
      <Text fz={28} fw={700}>
        {value}
      </Text>
    </Paper>
  );
}

/** Простая статистика поставщика: скачивания, продажи, выручка по приложениям. */
export default function StatsPage() {
  const { t } = useTranslation('marketplace');
  const { data, isLoading } = useGetMarketStatsQuery();
  const rows = data?.data || [];

  const sum = (key: 'downloads' | 'purchases' | 'revenue') =>
    rows.reduce((acc, row) => acc + row[key], 0);
  const money = (value: number) => `${value.toLocaleString('ru-RU')} ₽`;

  return (
    <Container size="lg" py="md">
      <Title order={3} mb="md">
        {t('stats.title')}
      </Title>

      <SimpleGrid cols={{ base: 2, sm: 4 }} mb="lg">
        <StatCard label={t('stats.apps')} value={rows.length} />
        <StatCard label={t('stats.downloads')} value={sum('downloads')} />
        <StatCard label={t('stats.purchases')} value={sum('purchases')} />
        <StatCard label={t('stats.revenue')} value={money(sum('revenue'))} />
      </SimpleGrid>

      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('fields.name')}</Table.Th>
            <Table.Th>{t('fields.published')}</Table.Th>
            <Table.Th>{t('fields.price')}</Table.Th>
            <Table.Th>{t('stats.downloads')}</Table.Th>
            <Table.Th>{t('stats.purchases')}</Table.Th>
            <Table.Th>{t('stats.revenue')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map(row => (
            <Table.Tr key={row.id}>
              <Table.Td>{row.name}</Table.Td>
              <Table.Td>
                <Badge variant="light" color={row.published ? 'teal' : 'gray'}>
                  {row.published ? t('stats.published') : t('stats.draft')}
                </Badge>
              </Table.Td>
              <Table.Td>{money(row.price)}</Table.Td>
              <Table.Td>{row.downloads}</Table.Td>
              <Table.Td>{row.purchases}</Table.Td>
              <Table.Td>{money(row.revenue)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      {!isLoading && rows.length === 0 && (
        <Text c="dimmed" ta="center" py="lg">
          {t('stats.empty')}
        </Text>
      )}
    </Container>
  );
}
