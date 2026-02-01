import {
  Box,
  Table,
  Badge,
  Text,
  Title,
  Paper,
  Group,
  Loader,
  Center,
} from '@mantine/core';
import {
  IconPhone,
  IconMail,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconBrandInstagram,
  IconWorld,
  IconMessageCircle,
  IconShoppingBag,
  IconSend,
  IconAddressBook,
} from '@tabler/icons-react';
import { useContactTypes } from '@/components/ContactsWidget';

// Маппинг icon name → React component
const ICON_MAP: Record<string, React.ElementType> = {
  IconPhone,
  IconMail,
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconBrandInstagram,
  IconWorld,
  IconMessageCircle,
  IconShoppingBag,
  IconSend,
  // Легаси
  phone: IconPhone,
  mail: IconMail,
  send: IconSend,
  'shopping-bag': IconShoppingBag,
  'message-circle': IconMessageCircle,
  camera: IconBrandInstagram,
};

function getIcon(iconName: string): React.ElementType {
  return ICON_MAP[iconName] || IconAddressBook;
}

/**
 * Справочник типов контактов.
 * Данные загружаются из таблицы contact_type.
 */
export function ViewListContactTypes() {
  const { contactTypes, isLoading } = useContactTypes();

  if (isLoading) {
    return (
      <Center p="xl">
        <Loader />
      </Center>
    );
  }

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
            {contactTypes.map(type => {
              const Icon = getIcon(type.icon);
              return (
                <Table.Tr key={type.name}>
                  <Table.Td>
                    <Group gap="sm">
                      <Badge
                        size="lg"
                        color={type.color || 'gray'}
                        leftSection={<Icon size={14} />}>
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
                      {type.connectorTypes.length > 0 ? (
                        type.connectorTypes.map(connector => (
                          <Badge key={connector} size="sm" variant="outline">
                            {connector}
                          </Badge>
                        ))
                      ) : (
                        <Text size="sm" c="dimmed">
                          —
                        </Text>
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
