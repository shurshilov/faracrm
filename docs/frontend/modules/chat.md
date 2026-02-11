# Chat Module (Frontend)

Real-time чат с WebSocket, оптимистичными обновлениями и поддержкой мультимедиа.

## Структура

```
fara_chat/
├── components/
│   ├── ChatPage.tsx          # Главная страница: список + чат
│   ├── ChatList.tsx          # Sidebar со списком чатов
│   ├── MessageList.tsx       # Лента сообщений
│   ├── MessageInput.tsx      # Поле ввода + вложения
│   ├── MessageBubble.tsx     # Одно сообщение
│   ├── PinnedMessages.tsx    # Закреплённые сообщения
│   └── ReactionPicker.tsx    # Выбор реакции
├── hooks/
│   ├── useChat.ts            # Логика чата
│   └── useWebSocket.ts       # WS-подключение
├── context/
│   └── ChatContext.tsx        # Контекст текущего чата
└── locales/
    ├── ru.json
    └── en.json
```

## WebSocket

```typescript title="fara_chat/hooks/useWebSocket.ts"
import { useEffect, useRef } from 'react';

export function useWebSocket(token: string, onMessage: (data: any) => void) {
    const ws = useRef<WebSocket | null>(null);

    useEffect(() => {
        const url = `${WS_BASE_URL}/ws?token=${token}`;
        ws.current = new WebSocket(url);

        ws.current.onmessage = (event) => {
            const data = JSON.parse(event.data);
            onMessage(data);
        };

        ws.current.onclose = () => {
            // Reconnect logic
            setTimeout(() => {
                ws.current = new WebSocket(url);
            }, 3000);
        };

        return () => ws.current?.close();
    }, [token]);

    return ws;
}
```

## Обработка WS-событий

```typescript title="fara_chat/components/ChatPage.tsx"
function ChatPage() {
    const { token } = useAuth();
    const [messages, setMessages] = useState<Message[]>([]);

    const handleWsMessage = useCallback((data: WsEvent) => {
        switch (data.type) {
            case 'new_message':
                setMessages(prev => [...prev, data.message]);
                break;

            case 'message_edited':
                setMessages(prev =>
                    prev.map(m =>
                        m.id === data.message_id
                            ? { ...m, body: data.body, is_edited: true }
                            : m
                    )
                );
                break;

            case 'message_deleted':
                setMessages(prev =>
                    prev.filter(m => m.id !== data.message_id)
                );
                break;

            case 'message_pinned':
                setMessages(prev =>
                    prev.map(m =>
                        m.id === data.message_id
                            ? { ...m, pinned: data.pinned }
                            : m
                    )
                );
                break;
        }
    }, []);

    useWebSocket(token, handleWsMessage);

    return (
        <ChatLayout>
            <ChatList />
            <MessageList messages={messages} />
            <MessageInput chatId={currentChatId} />
        </ChatLayout>
    );
}
```

## Компоненты

### MessageInput

```tsx title="fara_chat/components/MessageInput.tsx"
function MessageInput({ chatId }: { chatId: number }) {
    const [body, setBody] = useState('');
    const [sendMessage] = chatApi.useSendMessageMutation();

    const handleSend = async () => {
        if (!body.trim()) return;

        await sendMessage({
            chatId,
            body: body.trim(),
            attachments: [],
        });

        setBody('');
    };

    return (
        <Group>
            <Textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder={t('chat.typeMessage')}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                    }
                }}
            />
            <ActionIcon onClick={handleSend}>
                <IconSend />
            </ActionIcon>
        </Group>
    );
}
```

### MessageBubble

```tsx title="fara_chat/components/MessageBubble.tsx"
function MessageBubble({ message, isOwn }: Props) {
    return (
        <Paper
            p="sm"
            radius="md"
            bg={isOwn ? 'blue.0' : 'gray.0'}
            ml={isOwn ? 'auto' : 0}
            maw="70%"
        >
            {!isOwn && (
                <Text size="xs" fw={600} c="blue">
                    {message.author_name}
                </Text>
            )}

            <Text size="sm">{message.body}</Text>

            <Group gap={4} mt={4}>
                <Text size="xs" c="dimmed">
                    {formatTime(message.created_at)}
                </Text>
                {message.is_edited && (
                    <Text size="xs" c="dimmed">(ред.)</Text>
                )}
                {message.pinned && <IconPin size={12} />}
            </Group>
        </Paper>
    );
}
```
