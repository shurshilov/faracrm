import { Box, Table, Badge, Text, Title, Paper, Group } from '@mantine/core';
import {
  IconPhone,
  IconMail,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconBrandInstagram,
  IconWorld,
  IconMessageCircle,
} from '@tabler/icons-react';

// Конфиг типов контактов
const CONTACT_TYPES = [
  {
    name: 'phone',
    label: 'Телефон',
    icon: IconPhone,
    color: 'green',
    placeholder: '+7 999 123-45-67',
    connectors: ['whatsapp', 'viber', 'sms'],
  },
  {
    name: 'email',
    label: 'Email',
    icon: IconMail,
    color: 'blue',
    placeholder: 'example@mail.com',
    connectors: ['email'],
  },
  {
    name: 'telegram',
    label: 'Telegram',
    icon: IconBrandTelegram,
    color: 'cyan',
    placeholder: '@username',
    connectors: ['telegram'],
  },
  {
    name: 'whatsapp',
    label: 'WhatsApp',
    icon: IconBrandWhatsapp,
    color: 'teal',
    placeholder: '+7 999 123-45-67',
    connectors: ['whatsapp'],
  },
  {
    name: 'viber',
    label: 'Viber',
    icon: IconMessageCircle,
    color: 'violet',
    placeholder: '+7 999 123-45-67',
    connectors: ['viber'],
  },
  {
    name: 'instagram',
    label: 'Instagram',
    icon: IconBrandInstagram,
    color: 'pink',
    placeholder: '@username',
    connectors: ['instagram'],
  },
  {
    name: 'website',
    label: 'Сайт',
    icon: IconWorld,
    color: 'indigo',
    placeholder: 'https://example.com',
    connectors: [],
  },
];

/**
 * Справочник типов контактов.
 * Отображает все доступные типы из конфига (не из БД).
 */
export function ViewListContactTypes() {
  return (
    <Box p="md">
      <Group mb="lg" justify="space-between">
        <Title order={3}>Типы контактов</Title>
        <Text size="sm" c="dimmed">
          Справочник доступных типов контактов
        </Text>
      </Group>

      <Paper shadow="xs" withBorder>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Тип</Table.Th>
              <Table.Th>Код</Table.Th>
              <Table.Th>Формат</Table.Th>
              <Table.Th>Коннекторы</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {CONTACT_TYPES.map((type) => {
              const Icon = type.icon;
              return (
                <Table.Tr key={type.name}>
                  <Table.Td>
                    <Group gap="sm">
                      <Badge
                        size="lg"
                        color={type.color}
                        leftSection={<Icon size={14} />}
                      >
                        {type.label}
                      </Badge>
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" ff="monospace" c="dimmed">
                      {type.name}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {type.placeholder}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      {type.connectors.length > 0 ? (
                        type.connectors.map((connector) => (
                          <Badge key={connector} size="sm" variant="outline">
                            {connector}
                          </Badge>
                        ))
                      ) : (
                        <Text size="sm" c="dimmed">—</Text>
                      )}
                    </Group>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </Paper>
    </Box>
  );
}
