# Copyright 2025 FARA CRM
# Chat module - VK (ВКонтакте) strategy
#
# Интеграция с сообществом ВКонтакте через Callback API + messages.send.
#
# У ВКонтакте, в отличие от MAX/WhatsApp, НЕТ отдельного «бизнес»-канала с
# отправкой первым по номеру телефона: всё общение идёт через сообщество,
# получатель адресуется по user_id (peer_id) из вебхука. Поэтому модуль ОДИН.
#
# Особенности VK, которых нет у Telegram/MAX:
#   1. Callback API требует «рукопожатие»: на событие type="confirmation" сервер
#      обязан ответить ПРОСТЫМ ТЕКСТОМ (строка-код сообщества), а не JSON. На
#      остальные события — ответить текстом "ok". Поэтому handle_webhook
#      переопределён и возвращает str (роутер отдаёт его как PlainTextResponse).
#   2. Отправка вложений — через upload-server (photos/docs.getMessagesUploadServer
#      → загрузка → save → attachment "photo{owner}_{id}").
#   3. Имя отправителя в вебхуке не приходит — докручиваем через users.get.

import logging
import random
import re
from typing import TYPE_CHECKING, Any, Tuple

import httpx

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
from .adapter import VkMessageAdapter

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.project_setup import ChatConnector
    from backend.base.crm.chat.models.chat_external_account import (
        ChatExternalAccount,
    )
    from backend.base.crm.attachments.models.attachments import Attachment
    from backend.base.crm.chat.strategies.adapter import ChatMessageAdapter

logger = logging.getLogger(__name__)


class VkStrategy(ChatStrategyBase):
    """
    Стратегия для интеграции с сообществом ВКонтакте (Callback API).

    Поддерживает:
    - Приём сообщений через Callback API (событие message_new)
    - Подтверждение адреса сервера (type="confirmation")
    - Отправку текстовых сообщений (messages.send)
    - Отправку изображений/документов (через upload-server)
    - Скачивание входящих вложений (по прямым URL)

    Требует настройки коннектора:
    - access_token: ключ доступа СООБЩЕСТВА (права messages + manage)
    - external_account_id: числовой id сообщества (group_id) — можно получить
      кнопкой в форме (groups.getById)
    - connector_url: https://api.vk.com/method (по умолчанию)
    - webhook_url: URL для приёма событий (используется как адрес callback-сервера)
    - webhook_hash: секрет callback-сервера (secret_key)

    Документация API: https://dev.vk.com/ru/api/callback/getting-started
    """

    strategy_type = "vk"
    BASE_API_URL = "https://api.vk.com/method"
    API_VERSION = "5.199"
    TIMEOUT = 30.0
    CALLBACK_TITLE = "FARA CRM"

    # ========================================================================
    # Вспомогательные методы (VK API)
    # ========================================================================

    def _base_url(self, connector: "ChatConnector") -> str:
        """База API без хвостового слеша."""
        return (connector.connector_url or self.BASE_API_URL).rstrip("/")

    async def _call(
        self,
        connector: "ChatConnector",
        method: str,
        params: dict | None = None,
        *,
        http_method: str = "POST",
    ) -> Any:
        """
        Вызвать метод VK API и вернуть содержимое поля `response`.

        Токен и версия API добавляются автоматически. VK всегда отвечает 200 и
        кладёт ошибку в поле `error` — проверяем его и бросаем ValueError.
        """
        url = f"{self._base_url(connector)}/{method}"
        payload = dict(params or {})
        payload.setdefault("access_token", connector.access_token or "")
        payload.setdefault("v", self.API_VERSION)

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            if http_method == "GET":
                response = await client.get(url, params=payload)
            else:
                # VK принимает параметры form-encoded в теле POST.
                response = await client.post(url, data=payload)

        try:
            result = response.json()
        except Exception:  # noqa: BLE001
            raise ValueError(
                f"VK {method}: non-JSON response HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        if isinstance(result, dict) and result.get("error"):
            error = result["error"]
            msg = error.get("error_msg") if isinstance(error, dict) else error
            code = error.get("error_code") if isinstance(error, dict) else ""
            raise ValueError(f"VK {method} error [{code}]: {msg}")

        return result.get("response") if isinstance(result, dict) else result

    async def _get_group_id(self, connector: "ChatConnector") -> int:
        """
        Получить числовой id сообщества (group_id).

        Берём из connector.external_account_id (если заполнен), иначе спрашиваем
        VK через groups.getById (для токена сообщества возвращает своё
        сообщество).
        """
        raw = str(connector.external_account_id or "").strip()
        digits = re.sub(r"\D", "", raw)
        if digits:
            return int(digits)

        response = await self._call(
            connector, "groups.getById", http_method="GET"
        )
        group_id = self._extract_group_id(response)
        if not group_id:
            raise ValueError(
                "VK: cannot resolve group_id (fill external_account_id or "
                "check community token)"
            )
        return group_id

    @staticmethod
    def _extract_group_id(response: Any) -> int | None:
        """Достать id сообщества из ответа groups.getById (разные форматы)."""
        groups = None
        if isinstance(response, dict):
            groups = response.get("groups") or response.get("items")
        elif isinstance(response, list):
            groups = response
        if groups:
            gid = groups[0].get("id")
            return int(gid) if gid else None
        return None

    async def get_or_generate_token(
        self, connector: "ChatConnector"
    ) -> str | None:
        """
        Токен сообщества VK статичен и не требует обновления.
        Возвращаем существующий access_token.
        """
        return connector.access_token

    # ========================================================================
    # Callback API (webhook)
    # ========================================================================

    async def set_webhook(self, connector: "ChatConnector") -> bool:
        """
        Зарегистрировать и включить callback-сервер сообщества.

        Шаги:
        1. groups.getCallbackConfirmationCode — убеждаемся, что код доступен
           (его вернёт handle_webhook на type="confirmation").
        2. groups.addCallbackServer — регистрируем URL (VK тут же дёрнет наш
           webhook с type="confirmation" — handle_webhook ответит кодом).
        3. groups.setCallbackSettings — включаем событие message_new.

        Требует токен сообщества с правами manage.
        """
        group_id = await self._get_group_id(connector)

        # 1. Проверяем/логируем код подтверждения (сам код VK сверит сам).
        try:
            code_resp = await self._call(
                connector,
                "groups.getCallbackConfirmationCode",
                {"group_id": group_id},
                http_method="GET",
            )
            logger.info("VK confirmation code for group %s ready", group_id)
            _ = code_resp
        except Exception as exc:  # noqa: BLE001
            logger.warning("VK getCallbackConfirmationCode failed: %s", exc)

        # 2. Регистрируем callback-сервер (VK проверит адрес рукопожатием).
        add_resp = await self._call(
            connector,
            "groups.addCallbackServer",
            {
                "group_id": group_id,
                "url": connector.webhook_url,
                "title": self.CALLBACK_TITLE,
                "secret_key": connector.webhook_hash or "",
            },
        )
        server_id = None
        if isinstance(add_resp, dict):
            server_id = add_resp.get("server_id")
        if not server_id:
            raise ValueError(
                f"VK addCallbackServer: no server_id in response {add_resp}"
            )

        # 3. Включаем нужные события для этого сервера.
        await self._call(
            connector,
            "groups.setCallbackSettings",
            {
                "group_id": group_id,
                "server_id": server_id,
                "api_version": self.API_VERSION,
                "message_new": 1,
            },
        )

        logger.info(
            "VK callback server %s set for connector %s (group %s)",
            server_id,
            connector.id,
            group_id,
        )
        return True

    async def unset_webhook(self, connector: "ChatConnector") -> Any:
        """
        Удалить callback-сервер сообщества, соответствующий webhook_url.

        groups.getCallbackServers → ищем server_id по нашему url →
        groups.deleteCallbackServer.
        """
        group_id = await self._get_group_id(connector)

        servers_resp = await self._call(
            connector,
            "groups.getCallbackServers",
            {"group_id": group_id},
            http_method="GET",
        )
        items = []
        if isinstance(servers_resp, dict):
            items = servers_resp.get("items", []) or []

        deleted = []
        for server in items:
            if server.get("url") == connector.webhook_url:
                server_id = server.get("id")
                await self._call(
                    connector,
                    "groups.deleteCallbackServer",
                    {"group_id": group_id, "server_id": server_id},
                )
                deleted.append(server_id)

        logger.info(
            "VK callback servers %s deleted for connector %s",
            deleted,
            connector.id,
        )
        return {"deleted": deleted}

    async def get_webhook_info(self, connector: "ChatConnector") -> dict:
        """Получить список callback-серверов сообщества (groups.getCallbackServers)."""
        group_id = await self._get_group_id(connector)
        response = await self._call(
            connector,
            "groups.getCallbackServers",
            {"group_id": group_id},
            http_method="GET",
        )
        return (
            response if isinstance(response, dict) else {"response": response}
        )

    async def get_self_account_id(self, connector: "ChatConnector") -> dict:
        """
        Получить информацию о сообществе (groups.getById) — для заполнения
        external_account_id (group_id) кнопкой в форме коннектора.
        """
        response = await self._call(
            connector, "groups.getById", http_method="GET"
        )
        # Нормализуем к словарю для показа в модалке фронта.
        if isinstance(response, dict):
            return response
        return {"groups": response}

    # ========================================================================
    # Определение отправителя (имя докручиваем через users.get)
    # ========================================================================

    async def resolve_partner_id_and_name(
        self,
        connector: "ChatConnector",
        adapter: "ChatMessageAdapter",
    ) -> tuple[str | None, str | None]:
        """Вернуть (from_id, "Имя Фамилия") клиента.

        VK не присылает имя в вебхуке — берём его через users.get. Если запрос
        не удался — имя = id (обработка не срывается).
        """
        from_id = adapter.author_id
        if not from_id:
            return None, None

        name = None
        try:
            response = await self._call(
                connector,
                "users.get",
                {"user_ids": from_id, "fields": "screen_name"},
                http_method="GET",
            )
            users = response if isinstance(response, list) else []
            if users:
                user = users[0]
                first = user.get("first_name", "") or ""
                last = user.get("last_name", "") or ""
                full = " ".join(p for p in [first, last] if p).strip()
                screen = user.get("screen_name")
                if full and screen:
                    # name = f"{full} (@{screen})"
                    name = f"{full}"
                else:
                    name = full or (f"@{screen}" if screen else None)
        except Exception as exc:  # noqa: BLE001
            logger.warning("VK users.get failed for %s: %s", from_id, exc)

        return from_id, name or from_id

    # ========================================================================
    # Отправка сообщений
    # ========================================================================

    @staticmethod
    def _random_id() -> int:
        """Уникальный random_id для messages.send (защита VK от дублей)."""
        return random.randint(1, 2_147_483_647)

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
        thread_message_id: str | None = None,
        attachments: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить текстовое сообщение (messages.send).

        Args:
            chat_id: peer_id получателя (для лички == user_id клиента).

        Returns:
            Tuple[message_id, chat_id]
        """
        if not chat_id:
            raise ValueError(
                "Cannot send VK message without chat_id (peer_id)"
            )

        clean_text = re.sub(r"<[^>]+>", "", body or "")

        response = await self._call(
            connector,
            "messages.send",
            {
                **self._peer_param(chat_id),
                "message": clean_text,
                "random_id": self._random_id(),
            },
        )

        message_id = str(response) if response is not None else ""
        logger.info("VK message sent: %s to peer %s", message_id, chat_id)
        return message_id, str(chat_id)

    @staticmethod
    def _peer_param(chat_id: str) -> dict:
        """
        Параметр адресации messages.send.

        Числовой ключ → peer_id (личка/беседа). Нечисловой (screen name) →
        domain (для write-first по короткому имени).
        """
        key = str(chat_id).strip()
        if re.fullmatch(r"-?\d+", key):
            return {"peer_id": key}
        return {"domain": key.lstrip("@")}

    async def chat_send_message_binary(
        self,
        connector: "ChatConnector",
        user_from: "ChatExternalAccount",
        chat_id: str,
        attachment: "Attachment",
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Отправить изображение или документ в VK.

        Изображения — через photos.getMessagesUploadServer, прочие файлы —
        через docs.getMessagesUploadServer. Возвращаем (message_id, chat_id).
        """
        if not chat_id:
            raise ValueError("Cannot send VK file without chat_id (peer_id)")

        mimetype = attachment.mimetype or ""

        content = attachment.content
        if content is None and hasattr(attachment, "read_content"):
            content = await attachment.read_content()
        if content is None:
            raise ValueError("Attachment has no content")

        if mimetype.startswith("image/"):
            attach_str = await self._upload_photo(
                connector, chat_id, attachment.name, content, mimetype
            )
        else:
            attach_str = await self._upload_doc(
                connector, chat_id, attachment.name, content, mimetype
            )

        response = await self._call(
            connector,
            "messages.send",
            {
                **self._peer_param(chat_id),
                "attachment": attach_str,
                "random_id": self._random_id(),
            },
        )
        message_id = str(response) if response is not None else ""
        logger.info("VK file sent: %s to peer %s", message_id, chat_id)
        return message_id, str(chat_id)

    async def _upload_photo(
        self,
        connector: "ChatConnector",
        peer_id: str,
        filename: str,
        content: bytes,
        mimetype: str,
    ) -> str:
        """Загрузить фото для сообщения и вернуть строку attachment."""
        # 1. Получаем upload-сервер.
        upload = await self._call(
            connector,
            "photos.getMessagesUploadServer",
            {"peer_id": self._peer_param(peer_id).get("peer_id", peer_id)},
            http_method="GET",
        )
        upload_url = (upload or {}).get("upload_url")
        if not upload_url:
            raise ValueError(f"VK photos upload: no upload_url in {upload}")

        # 2. Загружаем файл (поле `photo`).
        files = {"photo": (filename, content, mimetype or "image/jpeg")}
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            up_resp = await client.post(upload_url, files=files)
        up = up_resp.json()

        # 3. Сохраняем фото.
        saved = await self._call(
            connector,
            "photos.saveMessagesPhoto",
            {
                "photo": up.get("photo"),
                "server": up.get("server"),
                "hash": up.get("hash"),
            },
        )
        items = saved if isinstance(saved, list) else []
        if not items:
            raise ValueError(f"VK saveMessagesPhoto: empty response {saved}")
        photo = items[0]
        return f"photo{photo.get('owner_id')}_{photo.get('id')}"

    async def _upload_doc(
        self,
        connector: "ChatConnector",
        peer_id: str,
        filename: str,
        content: bytes,
        mimetype: str,
    ) -> str:
        """Загрузить документ для сообщения и вернуть строку attachment."""
        # 1. Получаем upload-сервер (type=doc для обычного файла).
        upload = await self._call(
            connector,
            "docs.getMessagesUploadServer",
            {
                "type": "doc",
                "peer_id": self._peer_param(peer_id).get("peer_id", peer_id),
            },
            http_method="GET",
        )
        upload_url = (upload or {}).get("upload_url")
        if not upload_url:
            raise ValueError(f"VK docs upload: no upload_url in {upload}")

        # 2. Загружаем файл (поле `file`).
        files = {
            "file": (filename, content, mimetype or "application/octet-stream")
        }
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            up_resp = await client.post(upload_url, files=files)
        up = up_resp.json()

        # 3. Сохраняем документ.
        saved = await self._call(
            connector,
            "docs.save",
            {"file": up.get("file"), "title": filename},
        )
        # docs.save возвращает {"type": "doc", "doc": {...}} либо список.
        doc = None
        if isinstance(saved, dict):
            doc = saved.get("doc") or saved
        elif isinstance(saved, list) and saved:
            doc = saved[0]
        if not doc:
            raise ValueError(f"VK docs.save: empty response {saved}")
        return f"doc{doc.get('owner_id')}_{doc.get('id')}"

    # ========================================================================
    # Webhook обработка — VK-специфичное «рукопожатие»
    # ========================================================================

    async def handle_webhook(
        self,
        connector: "ChatConnector",
        payload: dict,
        env: "Environment",
    ) -> Any:
        """
        Обработка события Callback API.

        VK требует ответа ПРОСТЫМ ТЕКСТОМ:
        - на type="confirmation" — строка-код подтверждения сообщества;
        - на остальные события — строка "ok".

        Поэтому метод возвращает str (роутер отдаёт его как PlainTextResponse,
        см. chat/routers/webhook.py). Базовая обработка сообщения делегируется
        родителю.
        """
        event_type = payload.get("type")

        # 1. Подтверждение адреса сервера — отвечаем строкой подтверждения.
        if event_type == "confirmation":
            # 1a. Если админ вписал строку возврата в коннектор (её видно в UI
            # сообщества: «Строка, которую должен вернуть сервер») — отдаём её
            # напрямую. Это надёжнее и не требует у токена права manage.
            stored = str(connector.vk_confirmation or "").strip()
            if stored:
                logger.info(
                    "VK confirmation answered from stored string for "
                    "connector %s",
                    connector.id,
                )
                return stored

            # 1b. Иначе — фолбэк на живой запрос кода у VK (нужно право manage).
            try:
                group_id = await self._get_group_id(connector)
                code_resp = await self._call(
                    connector,
                    "groups.getCallbackConfirmationCode",
                    {"group_id": group_id},
                    http_method="GET",
                )
                code = ""
                if isinstance(code_resp, dict):
                    code = code_resp.get("code", "") or ""
                logger.info(
                    "VK confirmation answered via API for connector %s",
                    connector.id,
                )
                return str(code)
            except Exception as exc:  # noqa: BLE001
                logger.error("VK confirmation failed: %s", exc, exc_info=True)
                # Возвращаем пусто — VK повторит; лучше, чем 500.
                return ""

        # 2. Прочие события — обычная обработка сообщения, ответ "ok".
        try:
            await super().handle_webhook(
                connector=connector, payload=payload, env=env
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("VK handle_webhook error: %s", exc, exc_info=True)
        # VK ждёт именно "ok" (иначе считает сервер недоступным).
        return "ok"

    def create_message_adapter(
        self, connector: "ChatConnector", raw_message: dict
    ) -> VkMessageAdapter:
        """Создать адаптер для события VK."""
        return VkMessageAdapter(connector, raw_message)
