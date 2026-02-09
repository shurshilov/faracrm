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
        },
      }),
    }),

    // Get single chat details
    getChat: build.query<GetChatResponse, { chatId: number }>({
      query: ({ chatId }) => `/chats/${chatId}`,
    }),

    // Create new chat
    createChat: build.mutation<CreateChatResponse, CreateChatArgs>({
      query: body => ({
        url: '/chats',
        method: 'POST',
        body,
      }),
      // Update cache after creating chat
      async onQueryStarted(args, { dispatch, queryFulfilled }) {
        try {
          const { data } = await queryFulfilled;

          // Создаём объект чата для добавления в кэш
          const newChat: Chat = {
            id: data.data.id,
            name: data.data.name || '',
            chat_type: data.data.chat_type as 'direct' | 'group' | 'channel' | 'record',
            is_internal: true,
            members: [],
            unread_count: 0,
            connectors: [],
            create_date: new Date().toISOString(),
          };

          // Добавляем в кэш getChats (без фильтров)
          dispatch(
            chatApi.util.updateQueryData('getChats', { limit: 100 }, draft => {
              // Добавляем в начало списка
              draft.data.unshift(newChat);
              draft.total = (draft.total || 0) + 1;
            }),
          );
        } catch {
          // Ошибка - ничего не делаем, сервер вернёт ошибку
        }
      },
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
    }),

    // Leave chat
    leaveChat: build.mutation<{ success: boolean }, { chatId: number }>({
      query: ({ chatId }) => ({
        url: `/chats/${chatId}/leave`,
        method: 'POST',
      }),
    }),

    // Delete chat
    deleteChat: build.mutation<{ success: boolean }, { chatId: number }>({
      query: ({ chatId }) => ({
        url: `/chats/${chatId}`,
        method: 'DELETE',
      }),
    }),

    // Get available connectors for a chat
    getChatConnectors: build.query<
      { data: ChatConnectorDetail[] },
      { chatId: number }
    >({
      query: ({ chatId }) => `/chats/${chatId}/connectors`,
    }),

    // Get messages for a chat
    getChatMessages: build.query<GetMessagesResponse, GetMessagesArgs>({
      query: ({ chatId, limit, beforeId }) => ({
        url: `/chats/${chatId}/messages`,
        params: {
          limit: limit || 50,
          before_id: beforeId,
        },
      }),
    }),

    // Send message to chat (with optimistic update)
    sendMessage: build.mutation<
      SendMessageResponse,
      SendMessageArgs & { currentUserId?: number; currentUserName?: string }
    >({
      query: ({ chatId, currentUserId, currentUserName, ...body }) => ({
        url: `/chats/${chatId}/messages`,
        method: 'POST',
        body,
      }),
      // Optimistic update - immediately add message to cache
      async onQueryStarted(
        { chatId, body, attachments, currentUserId, currentUserName },
        { dispatch, queryFulfilled },
      ) {
        // Create optimistic message with temporary ID
        const tempId = -Date.now();
        const createDate = new Date().toISOString();
        const optimisticMessage: ChatMessage = {
          id: tempId,
          body,
          message_type: 'comment',
          create_date: createDate,
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
          chat_type?: string;
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
                  create_date: createDate,
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
                    create_date:
                      data.data.create_date || optimisticMessage.create_date,
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
                if (data.data.create_date) {
                  chat.last_message.create_date = data.data.create_date;
                  chat.last_message_date = data.data.create_date;
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
      { success: boolean; webhook_state: string },
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

    // Get webhook info
    getConnectorWebhookInfo: build.query<
      { data: Record<string, unknown> },
      { connectorId: number }
    >({
      query: ({ connectorId }) => `/connectors/${connectorId}/webhook/info`,
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
  create_date?: string;
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
  name: string;
  email?: string;
  member_type?: 'user' | 'partner';
  permissions?: MemberPermissions;
}

export interface ChatLastMessage {
  id: number;
  body?: string;
  author_id: number;
  create_date?: string;
}

export interface ChatConnector {
  id: number;
  type: string;
  name: string;
}

export interface ChatConnectorDetail {
  external_chat_id: number;
  external_id: string;
  connector_id: number;
  connector_type: string;
  connector_name: string;
}

export interface Chat {
  id: number;
  name: string;
  chat_type: 'direct' | 'group' | 'channel' | 'record';
  is_internal: boolean;
  description?: string;
  create_date?: string;
  last_message_date?: string;
  members: ChatMember[];
  last_message?: ChatLastMessage;
  unread_count: number;
  connectors: ChatConnector[];
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
  is_voice?: boolean;
  show_preview?: boolean;
}

export interface ChatMessage {
  id: number;
  body?: string;
  message_type: string;
  create_date?: string;
  author?: MessageAuthor;
  starred: boolean;
  connector_type?: string;
  attachments?: MessageAttachment[];
  pinned?: boolean;
  is_edited?: boolean;
  is_read?: boolean;
  reactions?: MessageReaction[];
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
  connector_id?: number;
  parent_id?: number;
  attachments?: SendMessageAttachment[];
}

export interface SendMessageResponse {
  data: {
    id: number;
    body: string;
    create_date?: string;
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

export type WSMessage = WSNewMessage | WSTyping | WSPresence | WSRead | WSReactionChanged | WSMessageEdited | WSMessageDeleted | WSMessagePinned;

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
  }),
  overrideExisting: false,
});

export { chatApi, recordChatApi };
export const {
  useGetChatsQuery,
  useGetChatQuery,
  useCreateChatMutation,
  useRemoveChatMemberMutation,
  useUpdateChatMutation,
  useLeaveChatMutation,
  useDeleteChatMutation,
  useGetChatConnectorsQuery,
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
  // Connectors
  useGetMyConnectorsQuery,
  useSetConnectorWebhookMutation,
  useUnsetConnectorWebhookMutation,
  useLazyGetConnectorWebhookInfoQuery,
} = chatApi;

export const {
  useFindRecordChatQuery,
  useGetOrCreateRecordChatMutation,
} = recordChatApi;
