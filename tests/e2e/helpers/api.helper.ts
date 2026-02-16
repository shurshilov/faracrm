/**
 * API Helper — прямые вызовы бэкенда для подготовки тестовых данных.
 * Используется в fixtures и тестах для setup/teardown без UI.
 */

export interface Session {
  token: string;
  user_id: { id: number; name: string };
}

export class ApiHelper {
  constructor(private apiUrl: string) {}

  /** URL для auto CRUD эндпоинтов */
  private autoUrl(path: string) {
    return `${this.apiUrl}/auto${path}`;
  }
  // ==================== Auth ====================

  async login(login: string, password: string): Promise<Session> {
    const res = await fetch(`${this.apiUrl}/signin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login, password }),
    });
    if (!res.ok) throw new Error(`Login failed: ${res.status} ${await res.text()}`);
    return res.json();
  }

  // ==================== Users ====================

  async ensureUser(
    token: string,
    data: { login: string; password: string; name: string },
  ): Promise<number> {
    // Проверяем существование
    const searchRes = await this.searchRecords(token, 'users', {
      fields: ['id', 'login'],
      filter: [['login', '=', data.login]],
      limit: 1,
    });

    if (searchRes.data.length > 0) {
      return searchRes.data[0].id;
    }

    // Получаем ID admin пользователя (source для копирования)
    const adminSearch = await this.searchRecords(token, 'users', {
      fields: ['id'],
      filter: [['login', '=', process.env.ADMIN_LOGIN || 'admin']],
      limit: 1,
    });
    if (!adminSearch.data.length) {
      throw new Error('Admin user not found for copy');
    }
    const sourceUserId = adminSearch.data[0].id;

    // Создаём через copy_user (надёжный endpoint)
    const copyRes = await fetch(`${this.apiUrl}/users/copy`, {
      method: 'POST',
      headers: this.headers(token),
      body: JSON.stringify({
        source_user_id: sourceUserId,
        name: data.name,
        login: data.login,
        copy_password: false,
        copy_is_admin: false,
        copy_roles: false,
        copy_contacts: false,
      }),
    });
    if (!copyRes.ok) throw new Error(`Copy user failed: ${copyRes.status} ${await copyRes.text()}`);
    const copyResult = await copyRes.json();
    const newUserId = copyResult.id;

    // Устанавливаем пароль
    const pwRes = await fetch(`${this.apiUrl}/users/password_change`, {
      method: 'POST',
      headers: this.headers(token),
      body: JSON.stringify({
        user_id: newUserId,
        password: data.password,
      }),
    });
    if (!pwRes.ok) {
      console.warn(`Password change failed: ${pwRes.status}`);
    }

    // Назначаем роль Internal User (code=base_user)
    const roleSearch = await this.searchRecords(token, 'roles', {
      fields: ['id'],
      filter: [['code', '=', 'base_user']],
      limit: 1,
    });
    if (roleSearch.data.length > 0) {
      const roleId = roleSearch.data[0].id;
      await fetch(this.autoUrl(`/users/${newUserId}`), {
        method: 'PUT',
        headers: this.headers(token),
        body: JSON.stringify({
          role_ids: { selected: [roleId] },
        }),
      });
    }

    return newUserId;
  }

  // ==================== Generic CRUD ====================

  async searchRecords(
    token: string,
    model: string,
    params: {
      fields: string[];
      filter?: any[];
      limit?: number;
      sort?: string;
      order?: string;
    },
  ): Promise<{ data: any[]; total: string }> {
    const res = await fetch(this.autoUrl(`/${model}/search`), {
      method: 'POST',
      headers: this.headers(token),
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error(`Search ${model} failed: ${res.status}`);
    return res.json();
  }

  async createRecord(
    token: string,
    model: string,
    values: Record<string, any>,
  ): Promise<any> {
    const res = await fetch(this.autoUrl(`/${model}`), {
      method: 'POST',
      headers: this.headers(token),
      body: JSON.stringify(values),
    });
    if (!res.ok) throw new Error(`Create ${model} failed: ${res.status} ${await res.text()}`);
    return res.json();
  }

  async deleteRecord(token: string, model: string, id: number): Promise<void> {
    await fetch(this.autoUrl(`/${model}/${id}`), {
      method: 'DELETE',
      headers: this.headers(token),
    });
  }

  // ==================== Chat ====================

  async createChat(
    token: string,
    data: { name: string; chat_type?: string; user_ids?: number[] },
  ): Promise<{ id: number }> {
    const res = await fetch(`${this.apiUrl}/chats`, {
      method: 'POST',
      headers: this.headers(token),
      body: JSON.stringify({
        name: data.name,
        chat_type: data.chat_type || 'group',
        user_ids: data.user_ids || [],
        partner_ids: [],
      }),
    });
    if (!res.ok) throw new Error(`Create chat failed: ${res.status} ${await res.text()}`);
    const result = await res.json();
    return { id: result.data?.id || result.id };
  }

  async sendMessage(
    token: string,
    chatId: number,
    body: string,
    attachments: any[] = [],
  ): Promise<{ data: any }> {
    const res = await fetch(`${this.apiUrl}/chats/${chatId}/messages`, {
      method: 'POST',
      headers: this.headers(token),
      body: JSON.stringify({ body, attachments }),
    });
    if (!res.ok) throw new Error(`Send message failed: ${res.status}`);
    return res.json();
  }

  async getMessages(
    token: string,
    chatId: number,
    limit = 50,
  ): Promise<{ data: any[] }> {
    const res = await fetch(
      `${this.apiUrl}/chats/${chatId}/messages?limit=${limit}`,
      { headers: this.headers(token) },
    );
    if (!res.ok) throw new Error(`Get messages failed: ${res.status}`);
    return res.json();
  }

  async deleteChat(token: string, chatId: number): Promise<void> {
    await fetch(`${this.apiUrl}/chats/${chatId}`, {
      method: 'DELETE',
      headers: this.headers(token),
    });
  }

  // ==================== Utils ====================

  private headers(token: string) {
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };
  }
}
