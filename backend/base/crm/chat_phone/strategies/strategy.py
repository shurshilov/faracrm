# Copyright 2025 FARA CRM
# Chat Phone module - base phone strategy

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Tuple

from backend.base.crm.chat.strategies.strategy import ChatStrategyBase
from .adapter import PhoneMessageAdapter

if TYPE_CHECKING:
    from backend.base.system.core.enviroment import Environment
    from backend.base.crm.chat.models.chat_connector import ChatConnector
    from backend.base.crm.partners.models.contact import Contact

logger = logging.getLogger(__name__)


class PhoneStrategyBase(ChatStrategyBase):
    """
    Базовая стратегия для телефонных коннекторов.

    Переопределяет логику handle_webhook для обработки жизненного цикла звонка:
    1. ringing → создать сообщение type='call', disposition='ringing'
    2. answered → обновить существующее сообщение: disposition='answered', call_answer_time
    3. ended → обновить: disposition, duration, скачать запись

    В отличие от мессенджеров, где каждый webhook = новое сообщение,
    в телефонии несколько событий относятся к ОДНОМУ звонку (call_id).

    Конкретные провайдеры наследуют и реализуют:
    - create_message_adapter() — парсинг формата провайдера
    - chat_send_message() — инициация исходящего звонка (если поддерживается)
    - get_or_generate_token() — авторизация
    - set_webhook() / unset_webhook() — настройка webhook
    - _download_call_record() — скачивание аудиозаписи (опционально)
    """

    async def handle_webhook(
        self,
        connector: "ChatConnector",
        payload: dict,
        env: "Environment",
    ) -> dict:
        """
        Обработка входящего webhook от телефонного провайдера.

        Жизненный цикл звонка:
        - ringing: создаём новое сообщение type='call'
        - answered: обновляем существующее сообщение
        - ended: финализируем (disposition, duration, запись)

        Привязка событий к одному звонку — через external_message
        (external_id = call_id провайдера).
        """
        try:
            adapter: PhoneMessageAdapter = self.create_message_adapter(
                connector, payload
            )

            if adapter.should_skip:
                logger.debug(
                    "[%s] Skipping phone event %s",
                    self.strategy_type,
                    adapter.message_id,
                )
                return {"ok": True}

            # Обрабатываем в зависимости от типа события
            event_type = adapter.event_type

            if event_type == "ringing":
                await self._handle_ringing(env, connector, adapter)
            elif event_type == "answered":
                await self._handle_answered(env, connector, adapter)
            elif event_type == "ended":
                await self._handle_ended(env, connector, adapter)
            else:
                logger.warning(
                    "[%s] Unknown phone event type: %s",
                    self.strategy_type,
                    event_type,
                )

            return {"ok": True}

        except Exception as e:
            logger.error(
                "[%s] Error processing phone webhook: %s",
                self.strategy_type,
                e,
                exc_info=True,
            )
            return {"ok": True}

    # ========================================================================
    # Обработчики событий жизненного цикла звонка
    # ========================================================================

    async def _handle_ringing(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: PhoneMessageAdapter,
    ) -> None:
        """
        Обработка события 'ringing' — начало дозвона.

        Создаёт новое сообщение type='call' в чате.
        Если чата нет — создаёт новый.
        """

        # Проверяем дубликат (по call_id провайдера)
        if await self._find_existing_message(env, connector, adapter):
            logger.debug(
                "[%s] Ringing duplicate for call %s",
                self.strategy_type,
                adapter.message_id,
            )
            return

        # Находим или создаём внешний аккаунт + контакт клиента
        external_account, contact, created = (
            await env.models.chat_external_account.find_or_create_for_webhook(
                connector=connector,
                external_id=adapter.author_id,
                contact_value=adapter.author_id,
                display_name=adapter.author_name,
                raw=json.dumps(adapter.raw) if adapter.raw else None,
            )
        )

        # Находим или создаём чат
        chat_id = await self._resolve_chat(
            env, connector, adapter, external_account
        )
        if chat_id is None:
            return

        # Определяем автора
        author_user_id, author_partner_id = self._resolve_author(
            contact, adapter
        )

        # Создаём сообщение type='call'
        now = datetime.now(timezone.utc)
        message = await env.models.chat_message.post_message(
            chat_id=chat_id,
            author_user_id=author_user_id,
            author_partner_id=author_partner_id,
            body=adapter.text or "",
            message_type="call",
            connector_id=connector.id,
        )

        # Заполняем поля звонка
        await message.update(
            env.models.chat_message(
                call_direction=adapter.call_direction,
                call_disposition="ringing",
            )
        )

        # Создаём связь с внешним сообщением (call_id)
        await env.models.chat_external_message.create_link(
            external_id=adapter.message_id,
            connector_id=connector.id,
            message_id=message.id,
            external_chat_id=adapter.chat_id,
        )

        # Отправляем через WebSocket
        await self._notify_ws(
            env.apps.chat.chat_manager,
            chat_id,
            message,
            adapter,
            connector,
            author_user_id,
            author_partner_id,
        )

        logger.info(
            "[%s] Ringing: call %s → message %s in chat %s",
            self.strategy_type,
            adapter.message_id,
            message.id,
            chat_id,
        )

    async def _handle_answered(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: PhoneMessageAdapter,
    ) -> None:
        """
        Обработка события 'answered' — сняли трубку.

        Обновляет существующее сообщение (найденное по call_id).
        Если ringing не было — создаёт новое.
        """

        existing = await self._find_existing_message(env, connector, adapter)

        if existing:
            # Обновляем существующее сообщение
            answer_time = adapter._timestamp_to_datetime(
                adapter.call_answer_timestamp
            )
            await existing.message_id.update(
                env.models.chat_message(
                    call_disposition="answered",
                    call_answer_time=answer_time,
                    body=adapter.text or "",
                    write_date=datetime.now(timezone.utc),
                )
            )

            # WS уведомление об обновлении
            message_id = existing.message_id.id
            chat_id = await self._get_chat_id_from_message(env, message_id)
            if chat_id:
                await env.apps.chat.chat_manager.send_to_chat(
                    chat_id=chat_id,
                    message={
                        "type": "message_edited",
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "body": adapter.text or "",
                    },
                )

            logger.info(
                "[%s] Answered: updated message %s",
                self.strategy_type,
                message_id,
            )
        else:
            # Ringing не было — создаём сообщение с нуля
            # (может случиться при пропуске ringing события)
            await self._handle_ringing(env, connector, adapter)

    async def _handle_ended(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: PhoneMessageAdapter,
    ) -> None:
        """
        Обработка события 'ended' — звонок завершён.

        Финализирует сообщение: disposition, duration, запись.
        """

        existing = await self._find_existing_message(env, connector, adapter)

        end_time = adapter._timestamp_to_datetime(adapter.call_end_timestamp)

        if existing:
            message_id = existing.message_id.id

            # Обновляем поля звонка
            update_payload = env.models.chat_message(
                call_disposition=adapter.disposition,
                call_duration=adapter.call_duration,
                call_talk_duration=adapter.talk_duration,
                call_end_time=end_time,
                body=adapter.text or "",
                write_date=datetime.now(timezone.utc),
            )

            # Если есть call_answer_time из этого события — обновляем
            answer_time = adapter._timestamp_to_datetime(
                adapter.call_answer_timestamp
            )
            if answer_time:
                update_payload.call_answer_time = answer_time

            await existing.message_id.update(update_payload)

            # Скачиваем запись разговора (если есть)
            await self._process_call_record(
                env, connector, adapter, message_id
            )

            # WS уведомление
            chat_id = await self._get_chat_id_from_message(env, message_id)
            if chat_id:
                await env.apps.chat.chat_manager.send_to_chat(
                    chat_id=chat_id,
                    message={
                        "type": "message_edited",
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "body": adapter.text or "",
                    },
                )

            logger.info(
                "[%s] Ended: call %s, disposition=%s, duration=%s",
                self.strategy_type,
                adapter.message_id,
                adapter.disposition,
                adapter.call_duration,
            )
        else:
            # Ни ringing, ни answered не было — создаём и сразу финализируем
            # Это может случиться при пакетном импорте истории звонков
            await self._create_completed_call(env, connector, adapter)

    # ========================================================================
    # Вспомогательные методы
    # ========================================================================

    async def _find_existing_message(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: PhoneMessageAdapter,
    ):
        """
        Найти существующее внешнее сообщение по call_id провайдера.

        Returns:
            ChatExternalMessage или None
        """
        return await env.models.chat_external_message.find_by_external_id(
            external_id=adapter.message_id,
            connector_id=connector.id,
        )

    async def _resolve_chat(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: PhoneMessageAdapter,
        external_account,
    ) -> int | None:
        """
        Найти или создать чат для звонка.

        Сначала ищем external_chat (по номеру клиента + коннектор).
        Если нет — создаём новый через базовый _create_new_chat.
        """
        external_chat = (
            await env.models.chat_external_chat.find_by_external_id(
                external_id=adapter.chat_id,
                connector_id=connector.id,
            )
        )

        if external_chat and external_chat.chat_id:
            return external_chat.chat_id.id

        return await self._create_new_chat(
            env, connector, adapter, external_account
        )

    def _resolve_author(
        self, contact, adapter: PhoneMessageAdapter
    ) -> Tuple[int | None, int | None]:
        """
        Определить автора сообщения (user_id или partner_id).

        Для входящего: автор = клиент (partner).
        Для исходящего: автор = оператор (user).
        """
        author_user_id = None
        author_partner_id = None

        if contact.user_id:
            author_user_id = contact.user_id.id
        elif contact.partner_id:
            author_partner_id = contact.partner_id.id

        return author_user_id, author_partner_id

    async def _get_chat_id_from_message(
        self, env: "Environment", message_id: int
    ) -> int | None:
        """Получить chat_id из сообщения."""
        messages = await env.models.chat_message.search(
            filter=[("id", "=", message_id)],
            fields=["chat_id"],
            limit=1,
        )
        if messages and messages[0].chat_id:
            return messages[0].chat_id.id
        return None

    async def _process_call_record(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: PhoneMessageAdapter,
        message_id: int,
    ) -> None:
        """
        Скачать и сохранить запись разговора как вложение.

        Провайдеры переопределяют _download_call_record()
        для своей логики скачивания.
        """
        record_url = adapter.call_record_url
        if not record_url:
            return

        try:
            record_content = await self._download_call_record(
                connector, adapter
            )
            if not record_content:
                return

            # Создаём вложение
            attachment = env.models.attachment(
                name=f"call_{adapter.message_id}.mp3",
                mimetype="audio/mpeg",
                res_id=message_id,
                res_model="chat_message",
            )
            attachment.id = await env.models.attachment.create(
                payload=attachment
            )

            # Сохраняем содержимое через стратегию хранения
            await env.models.attachment.save_content(
                attachment.id, record_content
            )

            logger.info(
                "[%s] Saved call record: attachment %s for message %s",
                self.strategy_type,
                attachment.id,
                message_id,
            )

        except Exception as e:
            logger.error(
                "[%s] Failed to download call record: %s",
                self.strategy_type,
                e,
            )

    async def _download_call_record(
        self,
        connector: "ChatConnector",
        adapter: PhoneMessageAdapter,
    ) -> bytes | None:
        """
        Скачать запись разговора. Провайдеры переопределяют.

        По умолчанию — HTTP GET по call_record_url.
        """
        url = adapter.call_record_url
        if not url:
            return None

        return await self.file_download(connector, url)

    async def _create_completed_call(
        self,
        env: "Environment",
        connector: "ChatConnector",
        adapter: PhoneMessageAdapter,
    ) -> None:
        """
        Создать уже завершённый звонок (для пакетного импорта).

        Создаёт сообщение со всеми заполненными полями сразу.
        """

        external_account, contact, created = (
            await env.models.chat_external_account.find_or_create_for_webhook(
                connector=connector,
                external_id=adapter.author_id,
                contact_value=adapter.author_id,
                display_name=adapter.author_name,
                raw=json.dumps(adapter.raw) if adapter.raw else None,
            )
        )

        chat_id = await self._resolve_chat(
            env, connector, adapter, external_account
        )
        if chat_id is None:
            return

        author_user_id, author_partner_id = self._resolve_author(
            contact, adapter
        )

        message = await env.models.chat_message.post_message(
            chat_id=chat_id,
            author_user_id=author_user_id,
            author_partner_id=author_partner_id,
            body=adapter.text or "",
            message_type="call",
            connector_id=connector.id,
        )

        # Заполняем все поля звонка сразу
        answer_time = adapter._timestamp_to_datetime(
            adapter.call_answer_timestamp
        )
        end_time = adapter._timestamp_to_datetime(adapter.call_end_timestamp)

        await message.update(
            env.models.chat_message(
                call_direction=adapter.call_direction,
                call_disposition=adapter.disposition,
                call_duration=adapter.call_duration,
                call_talk_duration=adapter.talk_duration,
                call_answer_time=answer_time,
                call_end_time=end_time,
            )
        )

        await env.models.chat_external_message.create_link(
            external_id=adapter.message_id,
            connector_id=connector.id,
            message_id=message.id,
            external_chat_id=adapter.chat_id,
        )

        # Скачиваем запись
        await self._process_call_record(env, connector, adapter, message.id)

        await self._notify_ws(
            env.apps.chat.chat_manager,
            chat_id,
            message,
            adapter,
            connector,
            author_user_id,
            author_partner_id,
        )

    async def _notify_ws(
        self,
        chat_manager,
        chat_id: int,
        message,
        adapter: PhoneMessageAdapter,
        connector: "ChatConnector",
        author_user_id: int | None,
        author_partner_id: int | None,
    ) -> None:
        """Отправить уведомление о новом сообщении через WebSocket."""
        author_data = {
            "id": author_user_id or author_partner_id,
            "name": adapter.author_name,
            "type": "user" if author_user_id else "partner",
        }

        await chat_manager.send_to_chat(
            chat_id=chat_id,
            message={
                "type": "new_message",
                "chat_id": chat_id,
                "message": {
                    "id": message.id,
                    "body": message.body,
                    "message_type": "call",
                    "author": author_data,
                    "author_user_id": author_user_id,
                    "author_partner_id": author_partner_id,
                    "create_date": (
                        message.create_date.isoformat()
                        if message.create_date
                        else None
                    ),
                    "connector_type": connector.type,
                    "call_direction": adapter.call_direction,
                    "call_disposition": adapter.disposition,
                },
                "external": True,
            },
        )

    # ========================================================================
    # Абстрактные методы ChatStrategyBase — заглушки для телефонии
    # ========================================================================

    async def chat_send_message(
        self,
        connector: "ChatConnector",
        user_from: "Contact",
        body: str,
        chat_id: str | None = None,
        recipients_ids: list | None = None,
    ) -> Tuple[str, str]:
        """
        Инициация исходящего звонка.

        По умолчанию не поддерживается — провайдеры могут переопределить
        если API позволяет инициировать звонки.
        """
        raise NotImplementedError(
            f"Outgoing calls not supported for {self.strategy_type}"
        )
