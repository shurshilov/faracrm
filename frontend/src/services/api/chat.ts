import { crudApi as api } from './crudApi';

// Chat API endpoints
const chatApi = api.injectEndpoints({
  endpoints: build => ({
    // Get list of chats for current user
    getChats: build.query<GetChatsResponse, GetChatsArgs>({
      query: args => ({
        url: '/chats',
        params: {
          limit: args?.limit || 50,
          offset: args?.offset || 0,
          ...(args?.is_internal !== undefined && {
            is_internal: args.is_internal,
          }),
          ...(args?.chat_type && { chat_type: args.chat_type }),
          ...(args?.connector_type && { connector_type: args.connector_type }),
          ...(args?.folder_id !== undefined && { folder_id: args.folder_id }),
          ...(args?.scope && { scope: args.scope }),
          ...(args?.include_deleted && { include_deleted: 1 }),
          ...(args?.include_record && { include_record: 1 }),
          ...(args?.include_foreign && { include_foreign: 1 }),
        },
      }),
      providesTags: result =>
        result
          ? [
              ...result.data.map(chat => ({
                type: 'Chat' as const,
                id: chat.id,
              })),
              { type: 'Chat', id: 'LIST' },
            ]
          : [{ type: 'Chat', id: 'LIST' }],
    }),

    // Get single chat details
    getChat: build.query<GetChatResponse, { chatId: number }>({
      query: ({ chatId }) => `/chats/${chatId}`,
      // Привязываем результат запроса к конкретному тегу Chat с его ID
      providesTags: (_result, _error, arg) => [
        { type: 'Chat', id: arg.chatId },
      ],
    }),

    // Create new chat
    createChat: build.mutation<CreateChatResponse, CreateChatArgs>({
      query: body => ({
        url: '/chats',
        method: 'POST',
        body,
      }),
      invalidatesTags: [{ type: 'Chat', id: 'LIST' }],
      // Update cache after creating chat
      // async onQueryStarted(args, { dispatch, queryFulfilled }) {
      //   try {
      //     const { data } = await queryFulfilled;

      //     // Создаём объект чата для добавления в кэш
      //     const newChat: Chat = {
      //       id: data.data.id,
      //       name: data.data.name || '',
      //       chat_type: data.data.chat_type as
      //         | 'direct'
      //         | 'group'
      //         | 'channel'
      //         | 'record',
      //       is_internal: true,
      //       members: [],
      //       unread_count: 0,
      //       connectors: [],
      //       create_datetime: new Date().toISOString(),
      //     };

      //     // Добавляем в кэш getChats (без фильтров)
      //     dispatch(
      //       chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
      //         // Добавляем в начало списка
      //         draft.data.unshift(newChat);
      //         draft.total = (draft.total || 0) + 1;
      //       }),
      //     );
      //   } catch {
      //     // Ошибка - ничего не делаем, сервер вернёт ошибку
      //   }
      // },
    }),

    // Add member to chat
    addChatMember: build.mutation<
      { success: boolean },
      { chatId: number; userId: number; permissions?: MemberPermissions }
    >({
      query: ({ chatId, userId, permissions }) => ({
        url: `/chats/${chatId}/members`,
        method: 'POST',
        body: { user_id: userId, ...permissions },
      }),
      // Инвалидируем конкретный чат, чтобы обновить список участников в UI
      invalidatesTags: (_result, _error, arg) => [
        { type: 'Chat', id: arg.chatId },
      ],
    }),

    // Remove member from chat
    removeChatMember: build.mutation<
      { success: boolean },
      { chatId: number; memberId: number }
    >({
      query: ({ chatId, memberId }) => ({
        url: `/chats/${chatId}/members/${memberId}`,
        method: 'DELETE',
      }),
      // Инвалидируем конкретный чат, чтобы участник исчез из списка в UI
      invalidatesTags: (_result, _error, arg) => [
        { type: 'Chat', id: arg.chatId },
      ],
    }),

    // Update member permissions
    updateMemberPermissions: build.mutation<
      { success: boolean },
      {
        chatId: number;
        memberId: number;
        can_read?: boolean;
        can_write?: boolean;
        can_invite?: boolean;
        can_pin?: boolean;
        can_delete_others?: boolean;
        is_admin?: boolean;
      }
    >({
      query: ({ chatId, memberId, ...permissions }) => ({
        url: `/chats/${chatId}/members/${memberId}/permissions`,
        method: 'PATCH',
        body: permissions,
      }),
      // Достаем chatId из аргументов мутации (третий параметр 'arg')
      invalidatesTags: (_result, _error, arg) => [
        { type: 'Chat', id: arg.chatId },
      ],
    }),

    // Update chat settings (including default permissions)
    updateChat: build.mutation<
      {
        success: boolean;
        data: { id: number; name?: string; description?: string };
      },
      {
        chatId: number;
        name?: string;
        description?: string;
        // Default permissions
        default_can_read?: boolean;
        default_can_write?: boolean;
        default_can_invite?: boolean;
        default_can_pin?: boolean;
        default_can_delete_others?: boolean;
      }
    >({
      query: ({ chatId, ...body }) => ({
        url: `/chats/${chatId}`,
        method: 'PATCH',
        body,
      }),
      // Достаем chatId из аргументов мутации (третий параметр 'arg')
      invalidatesTags: (_result, _error, arg) => [
        { type: 'Chat', id: arg.chatId },
      ],
    }),

    // Leave chat
    leaveChat: build.mutation<{ success: boolean }, { chatId: number }>({
      query: ({ chatId }) => ({
        url: `/chats/${chatId}/leave`,
        method: 'POST',
      }),
      invalidatesTags: [{ type: 'Chat', id: 'LIST' }],
    }),

    // Delete chat
    deleteChat: build.mutation<{ success: boolean }, { chatId: number }>({
      query: ({ chatId }) => ({
        url: `/chats/${chatId}`,
        method: 'DELETE',
      }),
      invalidatesTags: [{ type: 'Chat', id: 'LIST' }],
    }),

    // Restore a soft-deleted chat (active=false в true). Бэк ставит active=true
    // и шлёт chat_created участникам, список рефетчит, чат перестаёт быть
    // зачёркнутым / всплывает обратно.
    restoreChat: build.mutation<{ success: boolean }, { chatId: number }>({
      query: ({ chatId }) => ({
        url: `/chats/${chatId}/restore`,
        method: 'POST',
      }),
      invalidatesTags: [{ type: 'Chat', id: 'LIST' }],
    }),

    // Get available connectors for a chat (+ per-user default connector)
    getChatConnectors: build.query<
      {
        data: ChatConnectorDetail[];
        default_connector_id: number | null;
      },
      { chatId: number }
    >({
      query: ({ chatId }) => `/chats/${chatId}/connectors`,
    }),

    // Save per-user default connector for a chat (null = internal)
    setChatDefaultConnector: build.mutation<
      { data: { ok: boolean; connector_id: number | null; error?: string } },
      { chatId: number; connectorId: number | null }
    >({
      query: ({ chatId, connectorId }) => ({
        url: `/chats/${chatId}/default-connector`,
        method: 'POST',
        body: { connector_id: connectorId },
      }),
    }),

    // Default email subject for a chat (last message subject or chat name)
    getChatEmailSubject: build.query<
      { data: { subject: string } },
      { chatId: number }
    >({
      query: ({ chatId }) => `/chats/${chatId}/email-subject`,
    }),

    // Get messages for a chat
    getChatMessages: build.query<GetMessagesResponse, GetMessagesArgs>({
      query: ({ chatId, limit, beforeId, includeDeleted }) => ({
        url: `/chats/${chatId}/messages`,
        params: {
          limit: limit || 50,
          before_id: beforeId,
          ...(includeDeleted && { include_deleted: 1 }),
        },
      }),
      providesTags: (_result, _error, { chatId }) => [
        { type: 'ChatMessage' as const, id: chatId },
      ],
    }),

    // Send message to chat (with optimistic update)
    sendMessage: build.mutation<
      SendMessageResponse,
      SendMessageArgs & { currentUserId?: number; currentUserName?: string }
    >({
      query: ({
        chatId,
        currentUserId,
        currentUserName,
        connector_type,
        ...body
      }) => ({
        url: `/chats/${chatId}/messages`,
        method: 'POST',
        body,
      }),
      // После успешного POST — refetch сообщений этого чата.
      // Это страховка: оптимистик-апдейт ниже добавляет сообщение
      // в кеш мгновенно, но если по какой-то причине он не сработал
      // (кеш не инициализирован, race condition), refetch гарантирует
      // что сообщение появится из БД.
      // Также решает проблему с exclude_user в WS: отправитель не
      // получает своё сообщение через WebSocket, и без refetch'а
      // полагается только на оптимистик-апдейт.
      invalidatesTags: (_result, _error, { chatId }) => [
        { type: 'ChatMessage' as const, id: chatId },
      ],
      // Optimistic update - immediately add message to cache
      async onQueryStarted(
        {
          chatId,
          body,
          attachments,
          currentUserId,
          currentUserName,
          connector_type,
        },
        { dispatch, queryFulfilled },
      ) {
        // Create optimistic message with temporary ID
        const tempId = -Date.now();
        const createDate = new Date().toISOString();
        const optimisticMessage: ChatMessage = {
          id: tempId,
          body,
          message_type: 'comment',
          // Канал — чтобы своё письмо сразу рисовалось как HTML (без мигания
          // сырыми тегами до refetch). Для не-email просто undefined.
          connector_type,
          create_datetime: createDate,
          author: currentUserId
            ? { id: currentUserId, name: currentUserName, type: 'user' }
            : undefined,
          starred: false,
          pinned: false,
          is_edited: false,
          is_read: false,
          attachments: attachments?.map((att, index) => ({
            id: tempId - index - 1,
            name: att.name,
            mimetype: att.mimetype,
            size: att.size,
            is_voice: att.is_voice,
            content: att.content,
          })),
        };

        // Add to cache immediately
        const patchResult = dispatch(
          chatApi.util.updateQueryData(
            'getChatMessages',
            { chatId, limit: 50 },
            draft => {
              draft.data.unshift(optimisticMessage);
            },
          ),
        );

        // Update last_message in chats list
        const updateLastMessage = (args: {
          limit: number;
          is_internal?: boolean;
          chat_type?: 'direct' | 'group';
          connector_type?: string;
        }) => {
          dispatch(
            chatApi.util.updateQueryData('getChats', args, draft => {
              const chat = draft.data.find(c => c.id === chatId);
              if (chat) {
                chat.last_message = {
                  id: tempId,
                  body,
                  author_id: currentUserId || 0,
                  create_datetime: createDate,
                };
                chat.last_message_date = createDate;
              }
            }),
          );
        };

        updateLastMessage({ limit: 100 });

        try {
          const { data } = await queryFulfilled;

          dispatch(
            chatApi.util.updateQueryData(
              'getChatMessages',
              { chatId, limit: 50 },
              draft => {
                const index = draft.data.findIndex(m => m.id === tempId);
                if (index !== -1) {
                  draft.data[index] = {
                    ...optimisticMessage,
                    id: data.data.id,
                    create_datetime:
                      data.data.create_datetime ||
                      optimisticMessage.create_datetime,
                    attachments: data.data.attachments,
                  };
                }
              },
            ),
          );

          dispatch(
            chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
              const chat = draft.data.find(c => c.id === chatId);
              if (chat && chat.last_message?.id === tempId) {
                chat.last_message.id = data.data.id;
                if (data.data.create_datetime) {
                  chat.last_message.create_datetime = data.data.create_datetime;
                  chat.last_message_date = data.data.create_datetime;
                }
              }
            }),
          );
        } catch {
          patchResult.undo();
        }
      },
    }),

    // Mark chat as read
    markChatAsRead: build.mutation<
      { success: boolean; count: number },
      { chatId: number }
    >({
      query: ({ chatId }) => ({
        url: `/chats/${chatId}/read`,
        method: 'POST',
      }),
      // Прочтение сбрасывает unread чата → пересчитать бейджи папок в сайдбаре.
      invalidatesTags: [{ type: 'Chat', id: 'FOLDER_UNREAD' }],
    }),

    // Delete message
    deleteMessage: build.mutation<
      { success: boolean },
      { chatId: number; messageId: number }
    >({
      query: ({ chatId, messageId }) => ({
        url: `/chats/${chatId}/messages/${messageId}`,
        method: 'DELETE',
      }),
      async onQueryStarted(
        { chatId, messageId },
        { dispatch, queryFulfilled },
      ) {
        const patchResult = dispatch(
          chatApi.util.updateQueryData(
            'getChatMessages',
            { chatId, limit: 50 },
            draft => {
              const index = draft.data.findIndex(m => m.id === messageId);
              if (index !== -1) {
                draft.data.splice(index, 1);
              }
            },
          ),
        );

        try {
          await queryFulfilled;
        } catch {
          patchResult.undo();
        }
      },
    }),

    // Edit message
    editMessage: build.mutation<
      { success: boolean },
      { chatId: number; messageId: number; body: string }
    >({
      query: ({ chatId, messageId, body }) => ({
        url: `/chats/${chatId}/messages/${messageId}`,
        method: 'PATCH',
        body: { body },
      }),
    }),

    // Pin/unpin message
    pinMessage: build.mutation<
      { success: boolean },
      { chatId: number; messageId: number; pinned: boolean }
    >({
      query: ({ chatId, messageId, pinned }) => ({
        url: `/chats/${chatId}/messages/${messageId}/pin`,
        method: 'POST',
        body: { pinned },
      }),
    }),

    // Mark message as unread
    markMessageUnread: build.mutation<
      { success: boolean; unread_count: number },
      { chatId: number; messageId: number }
    >({
      query: ({ chatId, messageId }) => ({
        url: `/chats/${chatId}/messages/${messageId}/unread`,
        method: 'POST',
      }),
    }),

    // Forward message
    forwardMessage: build.mutation<
      { success: boolean; messageId: number },
      { chatId: number; messageId: number; targetChatId: number }
    >({
      query: ({ chatId, messageId, targetChatId }) => ({
        url: `/chats/${chatId}/messages/${messageId}/forward`,
        method: 'POST',
        body: { target_chat_id: targetChatId },
      }),
    }),

    // Get pinned messages
    getPinnedMessages: build.query<
      GetPinnedMessagesResponse,
      { chatId: number }
    >({
      query: ({ chatId }) => `/chats/${chatId}/pinned`,
    }),

    // Add reaction to message
    addReaction: build.mutation<
      { success: boolean; action: string; reactions: MessageReaction[] },
      { chatId: number; messageId: number; emoji: string }
    >({
      query: ({ chatId, messageId, emoji }) => ({
        url: `/chats/${chatId}/messages/${messageId}/reactions`,
        method: 'POST',
        body: { emoji },
      }),
    }),

    // Get reactions for message
    getReactions: build.query<
      { data: MessageReaction[] },
      { chatId: number; messageId: number }
    >({
      query: ({ chatId, messageId }) =>
        `/chats/${chatId}/messages/${messageId}/reactions`,
    }),

    // ============= CONNECTORS API =============

    // Get active connectors where current user is operator (for sidebar menu)
    getMyConnectors: build.query<
      { data: { type: string; name: string }[] },
      void
    >({
      query: () => '/connectors/my',
    }),

    // Get list of connectors
    getConnectors: build.query<
      { data: ConnectorInfo[] },
      { connector_type?: string; active?: boolean } | void
    >({
      query: args => ({
        url: '/connectors',
        params: args || {},
      }),
    }),

    // Get single connector
    getConnector: build.query<
      { data: ConnectorDetails },
      { connectorId: number }
    >({
      query: ({ connectorId }) => `/connectors/${connectorId}`,
    }),

    // Create connector
    createConnector: build.mutation<
      { data: { id: number; name: string; type: string; webhook_url: string } },
      {
        name: string;
        type: string;
        access_token?: string;
        external_account_id?: string;
      }
    >({
      query: body => ({
        url: '/connectors',
        method: 'POST',
        body,
      }),
    }),

    // Update connector
    updateConnector: build.mutation<
      { success: boolean },
      {
        connectorId: number;
        name?: string;
        access_token?: string;
        active?: boolean;
      }
    >({
      query: ({ connectorId, ...body }) => ({
        url: `/connectors/${connectorId}`,
        method: 'PATCH',
        body,
      }),
    }),

    // Set webhook
    setConnectorWebhook: build.mutation<
      {
        success: boolean;
        webhook_state: string;
        webhook_url?: string;
        webhook_hash?: string;
      },
      { connectorId: number }
    >({
      query: ({ connectorId }) => ({
        url: `/connectors/${connectorId}/webhook/set`,
        method: 'POST',
      }),
    }),

    // Unset webhook
    unsetConnectorWebhook: build.mutation<
      { success: boolean; webhook_state: string },
      { connectorId: number }
    >({
      query: ({ connectorId }) => ({
        url: `/connectors/${connectorId}/webhook/unset`,
        method: 'POST',
      }),
    }),

    // Delete a subscription/webhook by arbitrary URL (cleanup old ones, MAX)
    deleteConnectorWebhookByUrl: build.mutation<
      { data: { ok: boolean; error?: string; result?: unknown } },
      { connectorId: number; url: string }
    >({
      query: ({ connectorId, url }) => ({
        url: `/connectors/${connectorId}/webhook/delete-by-url`,
        method: 'POST',
        body: { url },
      }),
    }),

    // Get webhook info
    getConnectorWebhookInfo: build.query<
      { data: Record<string, unknown> },
      { connectorId: number }
    >({
      query: ({ connectorId }) => `/connectors/${connectorId}/webhook/info`,
    }),

    // Get self account info from external provider (e.g. Avito)
    getConnectorSelfAccount: build.query<
      { data: Record<string, unknown> },
      { connectorId: number }
    >({
      query: ({ connectorId }) => `/connectors/${connectorId}/account/self`,
    }),

    // Test connection with current saved settings (e.g. Email SMTP/IMAP login)
    testConnector: build.mutation<
      {
        data: {
          ok: boolean;
          message: string;
          details: Record<string, unknown>;
        };
      },
      { connectorId: number }
    >({
      query: ({ connectorId }) => ({
        url: `/connectors/${connectorId}/test`,
        method: 'POST',
      }),
    }),

    // Sync operator lines/numbers from the PBX (Asterisk endpoints -> external accounts)
    syncNumbers: build.mutation<
      {
        data: {
          ok: boolean;
          message: string;
          details?: Record<string, unknown>;
        };
      },
      { connectorId: number }
    >({
      query: ({ connectorId }) => ({
        url: `/connectors/${connectorId}/sync-numbers`,
        method: 'POST',
      }),
      invalidatesTags: [{ type: 'phone_number', id: 'LIST' }],
    }),

    // Read call history from CDR for a date range (Asterisk) and import as calls.
    // mode: normal (popup + lead) / no_notify / silent (message only, default).
    fetchCallHistory: build.mutation<
      { data: { ok: boolean; message: string; imported?: number } },
      {
        connectorId: number;
        start: string;
        end: string;
        mode?: 'normal' | 'no_notify' | 'silent';
      }
    >({
      query: ({ connectorId, start, end, mode }) => ({
        url: `/connectors/${connectorId}/fetch-history`,
        method: 'POST',
        body: { start, end, mode: mode ?? 'silent' },
      }),
    }),

    // Start/stop the in-process ARI listener (Asterisk local-mode autostart switch)
    startListener: build.mutation<
      { data: { ok: boolean; message: string; enabled: boolean } },
      { connectorId: number }
    >({
      query: ({ connectorId }) => ({
        url: `/connectors/${connectorId}/listener/start`,
        method: 'POST',
      }),
    }),
    stopListener: build.mutation<
      { data: { ok: boolean; message: string; enabled: boolean } },
      { connectorId: number }
    >({
      query: ({ connectorId }) => ({
        url: `/connectors/${connectorId}/listener/stop`,
        method: 'POST',
      }),
    }),

    // Delete connector
    deleteConnector: build.mutation<
      { success: boolean },
      { connectorId: number }
    >({
      query: ({ connectorId }) => ({
        url: `/connectors/${connectorId}`,
        method: 'DELETE',
      }),
    }),

    // Get available connector types
    getConnectorTypes: build.query<{ data: ConnectorType[] }, void>({
      query: () => '/connector-types',
    }),
  }),
  overrideExisting: false,
});

// Connector Types
export interface ConnectorInfo {
  id: number;
  name: string;
  type: string;
  category: string;
  active: boolean;
  webhook_state: string;
  webhook_url?: string;
  connector_url?: string;
  create_datetime?: string;
}

export interface ConnectorDetails extends ConnectorInfo {
  webhook_hash?: string;
  access_token?: string;
  external_account_id?: string;
}

export interface ConnectorType {
  type: string;
  name: string;
  description: string;
  icon: string;
}

// Member permissions
export interface MemberPermissions {
  can_read?: boolean;
  can_write?: boolean;
  can_invite?: boolean;
  can_pin?: boolean;
  can_delete_others?: boolean;
  is_admin?: boolean;
}

// Types
export interface ChatMember {
  id: number;
  user_id?: number;
  is_active?: boolean;
  name: string;
  email?: string;
  member_type?: 'user' | 'partner';
  /** Attachment id аватарки участника (null — нет аватара). */
  image_id?: number | null;
  permissions?: MemberPermissions;
}

export interface ChatLastMessage {
  id: number;
  body?: string;
  author_id: number;
  create_datetime?: string;
  message_type?:
    | 'comment'
    | 'notification'
    | 'system'
    | 'email'
    | 'call'
    | 'call_external';
  // Канал сообщения (email/telegram/...). Для email-превью проверяем его;
  // старые письма несли message_type='email' — оставлен как фолбэк.
  connector_type?: string;
}

export interface ChatConnector {
  id: number;
  type: string;
  name: string;
}

export interface ChatConnectorDetail {
  connector_id: number;
  connector_type: string;
  connector_name: string;
}

export interface Chat {
  id: number;
  name: string;
  chat_type: 'direct' | 'group' | 'channel' | 'record';
  is_internal: boolean;
  active?: boolean;
  description?: string;
  create_datetime?: string;
  last_message_date?: string;
  members: ChatMember[];
  last_message?: ChatLastMessage;
  unread_count: number;
  connectors: ChatConnector[];
  /** Закреплён ли чат текущим пользователем (per-user). */
  is_pinned?: boolean;
  // Default permissions
  default_can_read?: boolean;
  default_can_write?: boolean;
  default_can_invite?: boolean;
  default_can_pin?: boolean;
  default_can_delete_others?: boolean;
}

export interface MessageAuthor {
  id: number;
  name?: string;
  type?: 'user' | 'partner';
}

export interface MessageAttachment {
  id: number;
  name: string;
  mimetype: string;
  size: number;
  checksum?: string | null;
  is_voice?: boolean;
  show_preview?: boolean;
}

export interface ChatMessage {
  is_deleted?: boolean;
  id: number;
  body?: string;
  message_type: string;
  create_datetime?: string;
  author?: MessageAuthor;
  starred: boolean;
  connector_type?: string;
  attachments?: MessageAttachment[];
  pinned?: boolean;
  is_edited?: boolean;
  is_read?: boolean;
  reactions?: MessageReaction[];
  // Call fields (message_type='call' — WebRTC; 'call_external' — телефония)
  call_direction?: 'incoming' | 'outgoing';
  call_disposition?:
    | 'ringing'
    | 'answered'
    | 'no_answer'
    | 'busy'
    | 'failed'
    | 'cancelled';
  call_duration?: number;
  call_talk_duration?: number;
  call_answer_time?: string;
  call_end_time?: string;
}

export interface MessageReaction {
  emoji: string;
  count: number;
  users: { user_id: number; user_name: string }[];
}

export interface GetChatsArgs {
  limit?: number;
  offset?: number;
  is_internal?: boolean;
  chat_type?: 'direct' | 'group';
  connector_type?: string;
  /** Фильтр по папке чатов пользователя (chat_folder.id). */
  folder_id?: number;
  /** Внешние чаты: 'mine' = где я участник, 'all' = мои команды + членство. */
  scope?: 'mine' | 'all';
  include_deleted?: boolean;
  include_record?: boolean;
  /** Admin-only: показать чужие чаты (где user не мембер). */
  include_foreign?: boolean;
}

export interface GetChatsResponse {
  data: Chat[];
  total: number;
}

export interface GetChatResponse {
  data: Chat;
}

export interface CreateChatArgs {
  name?: string;
  chat_type: 'direct' | 'group' | 'channel' | 'record';
  user_ids: number[];
  partner_ids?: number[];
}

export interface CreateChatResponse {
  data: {
    id: number;
    name: string;
    chat_type: string;
    is_internal?: boolean;
  };
}

export interface GetMessagesArgs {
  chatId: number;
  limit?: number;
  beforeId?: number;
  includeDeleted?: boolean;
}

export interface GetMessagesResponse {
  data: ChatMessage[];
}

export interface GetPinnedMessagesResponse {
  data: ChatMessage[];
}

export interface SendMessageAttachment {
  name: string;
  mimetype: string;
  size: number;
  content: string;
  is_voice?: boolean;
}

export interface SendMessageArgs {
  chatId: number;
  body: string;
  message_type?: string;
  connector_id?: number;
  // Тип выбранного коннектора — только для оптимистик-рендера (email → HTML
  // сразу, без мигания сырым HTML до refetch). В запрос НЕ уходит: бэк сам
  // выводит connector_type из connector_id.
  connector_type?: string;
  parent_id?: number;
  // Теги: к какому лиду/задаче относится исходящее (панель чата партнёра на
  // форме проставляет). Уходят в тело POST → message.lead_id / message.task_id.
  lead_id?: number | null;
  task_id?: number | null;
  attachments?: SendMessageAttachment[];
}

export interface SendMessageResponse {
  data: {
    id: number;
    body: string;
    create_datetime?: string;
    attachments?: MessageAttachment[];
  };
}

// WebSocket message types
export interface WSNewMessage {
  type: 'new_message';
  chat_id: number;
  message: ChatMessage;
  external?: boolean;
}

export interface WSTyping {
  type: 'typing';
  chat_id: number;
  user_id: number;
}

export interface WSPresence {
  type: 'presence';
  user_id: number;
  status: 'online' | 'offline';
  timestamp: string;
}

export interface WSPresenceUpdate {
  type: 'presence_update';
  add: number[];
  remove: number[];
  timestamp: string;
}

export interface WSRead {
  type: 'messages_read';
  chat_id: number;
  user_id: number;
}

export interface WSReactionChanged {
  type: 'reaction_changed';
  chat_id: number;
  message_id: number;
  reactions: MessageReaction[];
}

export interface WSMessageEdited {
  type: 'message_edited';
  chat_id: number;
  message_id: number;
  body: string;
}

export interface WSMessageDeleted {
  type: 'message_deleted';
  chat_id: number;
  message_id: number;
}

export interface WSMessagePinned {
  type: 'message_pinned';
  chat_id: number;
  message_id: number;
  pinned: boolean;
}

export type WSMessage =
  | WSNewMessage
  | WSTyping
  | WSPresence
  | WSPresenceUpdate
  | WSRead
  | WSReactionChanged
  | WSMessageEdited
  | WSMessageDeleted
  | WSMessagePinned;

// ====================== RECORD CHAT (get_or_create) ======================

// Единственный уникальный эндпоинт для record-чатов.
// Всё остальное через стандартные /chats/{chat_id}/... хуки.

const recordChatApi = api.injectEndpoints({
  endpoints: build => ({
    // Find record chat (GET, no creation)
    findRecordChat: build.query<
      { chat_id: number | null; name: string | null },
      { resModel: string; resId: number }
    >({
      query: ({ resModel, resId }) => `/records/${resModel}/${resId}/chat`,
    }),

    // Get or create record chat (POST, lazy creation)
    getOrCreateRecordChat: build.mutation<
      { chat_id: number; name: string },
      { resModel: string; resId: number }
    >({
      query: ({ resModel, resId }) => ({
        url: `/records/${resModel}/${resId}/chat`,
        method: 'POST',
      }),
    }),

    // Count of chat_message linked to a record.
    // auto-CRUD для chat_message отключён (права проверяются через
    // ChatMember), поэтому search напрямую через /auto/chat_message/search
    // не работает. Для бейджика в FormPanels достаточно только числа.
    getRecordMessagesCount: build.query<
      { total: number; unread: number },
      { resModel: string; resId: number }
    >({
      query: ({ resModel, resId }) => ({
        url: '/chats/messages/count',
        params: { res_model: resModel, res_id: resId },
      }),
    }),
  }),
  overrideExisting: false,
});

// ====================== ЧАТ ПАРТНЁРА (1:1) ======================
//
// Модель 1:1: у партнёра ОДИН внешний групповой чат. Панель на форме
// лида/партнёра резолвит его id и показывает обычным чат-компонентом
// (ChatMessages + ChatInput). Отдельной «ленты»/агрегации нет — доступ идёт
// через штатные правила чата (членство / team). resolve БЕЗ создания (пустой
// чат на открытие не плодим); чат создаётся при первом входящем/ответе.

const partnerChatApi = api.injectEndpoints({
  endpoints: build => ({
    // Найти чат партнёра (без создания). { chat_id: null } → чата ещё нет.
    resolvePartnerChat: build.query<
      { chat_id: number | null; partner_id: number },
      { partnerId: number }
    >({
      query: ({ partnerId }) => `/partners/${partnerId}/chat`,
    }),

    // Как resolvePartnerChat, но партнёр берётся из лида (lead.partner_id).
    resolveLeadChat: build.query<
      { chat_id: number | null; partner_id: number | null },
      { leadId: number }
    >({
      query: ({ leadId }) => `/leads/${leadId}/chat`,
    }),

    // Создать (get-or-create) групповой чат партнёра — кнопка «Создать чат».
    createPartnerChat: build.mutation<
      { chat_id: number; partner_id: number },
      { partnerId: number }
    >({
      query: ({ partnerId }) => ({
        url: `/partners/${partnerId}/chat`,
        method: 'POST',
      }),
    }),

    // Недавние теги чата (лиды/задачи) — для селектора тега при ответе.
    getChatTags: build.query<
      { data: { lead_ids: number[]; task_ids: number[] } },
      { chatId: number; limit?: number }
    >({
      query: ({ chatId, limit }) => ({
        url: `/chats/${chatId}/tags`,
        params: { limit: limit || 5 },
      }),
    }),
  }),
  overrideExisting: false,
});

// ====================== CHAT FOLDERS + PIN ======================
//
// Папки чатов управляются через ОБЩИЙ auto-CRUD (/auto/chat_folder/*) —
// используем crudApi (useSearchQuery/useCreateMutation/useUpdateMutation/
// useDeleteBulkMutation) с model: 'chat_folder'. Отдельного folder-API нет.
// Здесь остаётся только НЕ-CRUD действие — закрепление чата.

/** Папка чатов = сохранённый domain-фильтр над chat (см. backend chat_folder). */
export interface ChatFolder {
  id: number;
  name: string;
  icon?: string | null;
  color?: string | null;
  sequence: number;
  /** NULL = глобальная папка (Все/Личные/Группы/коннектор), видна всем. */
  user_id?: { id: number; name?: string } | number | null;
  /** all | direct | group — у встроенных глобальных папок. */
  kind?: string | null;
  /** FK на коннектор — у глобальной папки коннектора. */
  connector_id?: { id: number; name?: string } | number | null;
  /** FARA-домен над chat: [["chat_type","=","direct"], "or", ["id","in",[...]]]. */
  domain?: unknown[] | Record<string, unknown> | null;
}

const folderApi = api.injectEndpoints({
  endpoints: build => ({
    // Закрепить/открепить чат (per-user). Инвалидируем список → пересортировка.
    pinChat: build.mutation<
      { success: boolean; is_pinned: boolean },
      { chatId: number; pinned: boolean }
    >({
      query: ({ chatId, pinned }) => ({
        url: `/chats/${chatId}/pin`,
        method: 'POST',
        body: { pinned },
      }),
      invalidatesTags: [{ type: 'Chat', id: 'LIST' }],
    }),

    // Непрочитанные по папкам — считаются на бэке на лету (не хранятся),
    // как и общий счётчик вверху справа. Ответ: { "<folder_id>": count }
    // (только папки с count>0). Тег FOLDER_UNREAD инвалидируется из WS-контекста
    // при new_message / messages_read / notification → бейджи обновляются живьём.
    getFolderUnread: build.query<{ data: Record<string, number> }, void>({
      query: () => '/chats/folders/unread',
      providesTags: [{ type: 'Chat', id: 'FOLDER_UNREAD' }],
    }),
  }),
  overrideExisting: false,
});

export { chatApi, recordChatApi, folderApi, partnerChatApi };
export const { usePinChatMutation, useGetFolderUnreadQuery } = folderApi;
export const {
  useResolvePartnerChatQuery,
  useResolveLeadChatQuery,
  useGetChatTagsQuery,
  useCreatePartnerChatMutation,
} = partnerChatApi;
export const {
  useGetChatsQuery,
  useGetChatQuery,
  useCreateChatMutation,
  useRemoveChatMemberMutation,
  useUpdateChatMutation,
  useLeaveChatMutation,
  useDeleteChatMutation,
  useRestoreChatMutation,
  useGetChatConnectorsQuery,
  useSetChatDefaultConnectorMutation,
  useGetChatEmailSubjectQuery,
  useGetChatMessagesQuery,
  useSendMessageMutation,
  useMarkChatAsReadMutation,
  useDeleteMessageMutation,
  useEditMessageMutation,
  usePinMessageMutation,
  useMarkMessageUnreadMutation,
  useForwardMessageMutation,
  useGetPinnedMessagesQuery,
  useAddReactionMutation,
  useAddChatMemberMutation,
  useUpdateMemberPermissionsMutation,
  // Connectors
  useGetMyConnectorsQuery,
  useSetConnectorWebhookMutation,
  useUnsetConnectorWebhookMutation,
  useDeleteConnectorWebhookByUrlMutation,
  useLazyGetConnectorWebhookInfoQuery,
  useLazyGetConnectorSelfAccountQuery,
  useTestConnectorMutation,
  useSyncNumbersMutation,
  useFetchCallHistoryMutation,
  useStartListenerMutation,
  useStopListenerMutation,
} = chatApi;

export const {
  useFindRecordChatQuery,
  useGetOrCreateRecordChatMutation,
  useGetRecordMessagesCountQuery,
} = recordChatApi;
