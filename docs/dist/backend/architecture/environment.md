# Environment

`Environment` — центральный объект приложения. Доступен через `app.state.env` в роутерах и через синглтон `env` в моделях.

## Доступ

=== "В роутере (через request)"

    ```python
    @router.get("/items")
    async def get_items(req: Request):
        env: Environment = req.app.state.env
        items = await env.models.product.search(
            filter=[("active", "=", True)],
            fields=["id", "name", "price"],
        )
        return {"data": items}
    ```

=== "В модели (через синглтон)"

    ```python
    from backend.base.system.core.enviroment import env

    class ChatMember(DotModel):
        @classmethod
        async def get_membership(cls, chat_id, user_id):
            return await env.models.chat_member.search(
                filter=[
                    ("chat_id", "=", chat_id),
                    ("user_id", "=", user_id),
                ],
                limit=1,
            )
    ```

## Атрибуты

| Атрибут | Тип | Описание |
|---------|-----|----------|
| `env.models` | `Models` | Все зарегистрированные DotModel-классы |
| `env.apps` | `Apps` | Инициализированные сервисы |
| `env.settings` | `Settings` | Конфигурация из `.env` |
| `env.services_before` | `list[Service]` | Сервисы, запущенные до роутеров |
| `env.services_after` | `list[Service]` | Сервисы, запущенные после роутеров |

## Models

`env.models` — это namespace с моделями. Каждая модель доступна по имени, заданному в `project_setup.py`:

```python
# project_setup.py
class Models(ModelsCore):
    user = User
    chat = Chat
    chat_message = ChatMessage

# Использование:
user = await env.models.user.get(user_id)
messages = await env.models.chat_message.search(
    filter=[("chat_id", "=", 1)],
    fields=["id", "body", "author_user_id"],
)
```

## Settings

Настройки загружаются из `.env` через Pydantic Settings:

```python title="backend/project_setup.py"
class Settings(SettingsCore):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",   # DB__HOST → settings.db.host
        extra="ignore",
    )

    class DatabaseSettings(BaseSettings):
        host: str = "localhost"
        port: int = 5432
        name: str = "fara"
        user: str = "postgres"
        password: str = ""

    db: DatabaseSettings = DatabaseSettings()
```

```bash title=".env"
DB__HOST=localhost
DB__PORT=5432
DB__NAME=fara_crm
DB__USER=postgres
DB__PASSWORD=secret
```
