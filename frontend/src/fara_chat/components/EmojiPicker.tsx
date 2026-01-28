import { Box, SimpleGrid, Text, Tabs, ScrollArea } from '@mantine/core';
import styles from './EmojiPicker.module.css';

interface EmojiPickerProps {
  onSelect: (emoji: string) => void;
}

// Категории эмодзи
const EMOJI_CATEGORIES = {
  recent: {
    label: '🕐',
    emojis: ['👍', '❤️', '😂', '🔥', '👏', '🎉', '💯', '✅'],
  },
  smileys: {
    label: '😀',
    emojis: [
      '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂',
      '🙂', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗',
      '😚', '😙', '🥲', '😋', '😛', '😜', '🤪', '😝',
      '🤑', '🤗', '🤭', '🤫', '🤔', '🤐', '🤨', '😐',
      '😑', '😶', '😏', '😒', '🙄', '😬', '🤥', '😌',
      '😔', '😪', '🤤', '😴', '😷', '🤒', '🤕', '🤢',
      '🤮', '🤧', '🥵', '🥶', '🥴', '😵', '🤯', '🤠',
      '🥳', '🥸', '😎', '🤓', '🧐', '😕', '😟', '🙁',
      '☹️', '😮', '😯', '😲', '😳', '🥺', '😦', '😧',
      '😨', '😰', '😥', '😢', '😭', '😱', '😖', '😣',
      '😞', '😓', '😩', '😫', '🥱', '😤', '😡', '😠',
    ],
  },
  gestures: {
    label: '👋',
    emojis: [
      '👋', '🤚', '🖐️', '✋', '🖖', '👌', '🤌', '🤏',
      '✌️', '🤞', '🤟', '🤘', '🤙', '👈', '👉', '👆',
      '🖕', '👇', '☝️', '👍', '👎', '✊', '👊', '🤛',
      '🤜', '👏', '🙌', '👐', '🤲', '🤝', '🙏', '✍️',
      '💪', '🦾', '🦿', '🦵', '🦶', '👂', '🦻', '👃',
    ],
  },
  hearts: {
    label: '❤️',
    emojis: [
      '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍',
      '🤎', '💔', '❣️', '💕', '💞', '💓', '💗', '💖',
      '💘', '💝', '💟', '♥️', '🩷', '🩵', '🩶',
    ],
  },
  objects: {
    label: '🎉',
    emojis: [
      '🎉', '🎊', '🎈', '🎁', '🏆', '🥇', '🥈', '🥉',
      '⚽', '🏀', '🏈', '⚾', '🎾', '🎮', '🎯', '🎲',
      '🔔', '🎵', '🎶', '🎤', '🎧', '📱', '💻', '⌨️',
      '📷', '📹', '📺', '📻', '⏰', '💡', '🔦', '📚',
      '📝', '✏️', '📌', '📎', '✂️', '📁', '📂', '🗂️',
    ],
  },
  symbols: {
    label: '✅',
    emojis: [
      '✅', '❌', '❓', '❗', '💯', '🔥', '⭐', '✨',
      '💫', '💥', '💢', '💦', '💨', '🕳️', '💣', '💬',
      '👁️‍🗨️', '🗨️', '🗯️', '💭', '💤', '🔴', '🟠', '🟡',
      '🟢', '🔵', '🟣', '⚫', '⚪', '🟤', '🔶', '🔷',
      '▶️', '⏸️', '⏹️', '⏺️', '⏭️', '⏮️', '⏩', '⏪',
      '🔀', '🔁', '🔂', '🔃', '🔄', '➕', '➖', '➗',
    ],
  },
};

export function EmojiPicker({ onSelect }: EmojiPickerProps) {
  return (
    <Box className={styles.container}>
      <Tabs defaultValue="recent" variant="pills" className={styles.tabs}>
        <Tabs.List className={styles.tabsList}>
          {Object.entries(EMOJI_CATEGORIES).map(([key, { label }]) => (
            <Tabs.Tab key={key} value={key} className={styles.tab}>
              {label}
            </Tabs.Tab>
          ))}
        </Tabs.List>

        {Object.entries(EMOJI_CATEGORIES).map(([key, { emojis }]) => (
          <Tabs.Panel key={key} value={key} pt="xs">
            <ScrollArea h={200}>
              <SimpleGrid cols={8} spacing={2}>
                {emojis.map((emoji, index) => (
                  <Box
                    key={`${emoji}-${index}`}
                    className={styles.emoji}
                    onClick={() => onSelect(emoji)}
                  >
                    {emoji}
                  </Box>
                ))}
              </SimpleGrid>
            </ScrollArea>
          </Tabs.Panel>
        ))}
      </Tabs>
    </Box>
  );
}

export default EmojiPicker;
