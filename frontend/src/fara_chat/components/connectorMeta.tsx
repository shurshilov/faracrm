import {
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconMail,
  IconMessage,
  IconPhoneCall,
} from '@tabler/icons-react';
import avitoIconUrl from '@/fara_chat_avito/assets/avito.svg';
import { MaxIcon } from '@/fara_chat_max_bot/components/MaxIcon';
import { VkIcon } from '@/fara_chat_vk/components/VkIcon';

// SVG-логотип Avito отдаётся как URL (project resolves *.svg в строку).
// draggable=false — чтобы иконка не «отрывалась» при drag внутри Menu.Item.
const AvitoIcon = ({ size = 16 }: { size?: number }) => (
  <img
    src={avitoIconUrl}
    width={size}
    height={size}
    alt="Avito"
    draggable={false}
    style={{ display: 'block' }}
  />
);

// Цвет канала (Mantine color) — общий для свитчера и бабла сообщения.
export const connectorColors: Record<string, string> = {
  internal: 'gray',
  telegram: 'blue',
  whatsapp: 'green',
  email: 'orange',
  avito: 'lime',
  max_bot: 'grape',
  // max_wamm: 'grape',
  max_business: 'grape',
  vk: 'indigo',
  phone_asterisk: 'teal',
};

/**
 * Иконка канала по типу коннектора — единый источник для переключателя
 * (ConnectorSwitcher) и футера сообщения (ChatMessages). size задаёт размер,
 * чтобы одна и та же иконка подходила и под кнопку, и под мелкий футер.
 */
export function connectorIcon(
  type: string | undefined,
  size = 16,
): React.ReactNode {
  switch (type) {
    case 'telegram':
      return <IconBrandTelegram size={size} />;
    case 'whatsapp':
      return <IconBrandWhatsapp size={size} />;
    case 'email':
      return <IconMail size={size} />;
    case 'avito':
      return <AvitoIcon size={size} />;
    case 'max_bot':
    case 'max_business':
      return <MaxIcon size={size} />;
    case 'vk':
      return <VkIcon size={size} />;
    case 'phone_asterisk':
      return <IconPhoneCall size={size} />;
    default:
      return <IconMessage size={size} />;
  }
}
