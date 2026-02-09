from typing import TYPE_CHECKING
from pydantic_settings import (
    SettingsConfigDict,
)

from backend.base.system.core.apps import AppsCore
from backend.base.system.core.models import ModelsCore
from backend.base.system.core.extensions import ExtensibleMixin
from backend.base.system.core.settings import SettingsCore
from backend.base.system.core.enviroment import env

# settings
from backend.base.system.dotorm_databases_postgres.settings import (
    PostgresSettings,
)
from backend.base.crm.attachments.settings import AttachmentsSettings
from backend.base.system.logger.settings import LoggerSettings

#
from backend.base.system.core.system_settings import SystemSettings
from backend.base.system.cron.models.cron_job import CronJob

# from backend.base.system.mkdocs.app import MkdocsService
from backend.base.crm.languages.models.language import Language
from backend.base.crm.users.models.users import User
from backend.base.crm.security.models.acls import AccessList
from backend.base.crm.security.models.models import Model
from backend.base.crm.security.models.apps import App as AppModel
from backend.base.crm.security.models.roles import Role
from backend.base.crm.security.models.rules import Rule
from backend.base.crm.security.models.sessions import Session
from backend.base.crm.attachments_google.mixins import (
    AttachmentStorageGoogleMixin,
)
from backend.base.crm.attachments.models.attachments import Attachment
from backend.base.crm.attachments.models.attachments_route import (
    AttachmentRoute,
)
from backend.base.crm.attachments.models.attachments_cache import (
    AttachmentCache,
)

from backend.base.system.saved_filters.models.saved_filter import SavedFilter
from backend.base.crm.sales.models.sale import Sale
from backend.base.crm.sales.models.sale_line import SaleLine
from backend.base.crm.partners.models.partners import Partner
from backend.base.crm.partners.models.contact import Contact
from backend.base.crm.partners.models.contact_type import ContactType
from backend.base.crm.products.models.product import Product
from backend.base.crm.products.models.category import Category
from backend.base.crm.products.models.uom import Uom
from backend.base.crm.leads.models.team_crm import TeamCrm
from backend.base.crm.sales.models.tax import Tax
from backend.base.crm.sales.models.sale_stage import SaleStage
from backend.base.crm.leads.models.leads import Lead
from backend.base.crm.leads.models.lead_stage import LeadStage

# Chat
from backend.base.crm.chat.models.chat import Chat
from backend.base.crm.chat.models.chat_member import ChatMember
from backend.base.crm.chat.models.chat_message import ChatMessage
from backend.base.crm.chat_telegram.mixins import ChatConnectorTelegramMixin
from backend.base.crm.chat_email.mixins import ChatConnectorEmailMixin
from backend.base.crm.chat_avito.mixins import ChatConnectorAvitoMixin
from backend.base.crm.chat_whatsapp_chatapp.mixins import (
    ChatConnectorWhatsAppChatAppMixin,
)

# Project and task
from backend.base.crm.tasks.models.project import Project
from backend.base.crm.tasks.models.task_stage import TaskStage
from backend.base.crm.tasks.models.task_tag import TaskTag
from backend.base.crm.tasks.models.task import Task

# Activity
from backend.base.crm.activity.models.activity_type import ActivityType
from backend.base.crm.activity.models.activity import Activity

from backend.base.crm.report_docx.models.report_template import ReportTemplate
from backend.base.crm.contract.models.contract import Contract
from backend.base.crm.contract.models.company_ext import CompanyContractMixin
from backend.base.crm.contract.models.partner_ext import PartnerContractMixin
from backend.base.crm.contract.models.sale_ext import SaleContractMixin

# когда есть расширение чтобы IDE видела все поля в модели делаем хак
if TYPE_CHECKING:
    from backend.base.crm.chat.models.chat_connector import (
        ChatConnector as ChatConnectorBase,
    )

    class ChatConnector(
        ChatConnectorTelegramMixin,
        ChatConnectorAvitoMixin,
        ChatConnectorWhatsAppChatAppMixin,
        ChatConnectorEmailMixin,
        ChatConnectorBase,
    ): ...

else:
    from backend.base.crm.chat.models.chat_connector import ChatConnector

# когда есть расширение чтобы IDE видела все поля в модели делаем хак
if TYPE_CHECKING:
    from backend.base.crm.attachments.models.attachments_storage import (
        AttachmentStorage as AttachmentStorageBase,
    )

    class AttachmentStorage(
        AttachmentStorageGoogleMixin,
        AttachmentStorageBase,
    ): ...

else:
    from backend.base.crm.attachments.models.attachments_storage import (
        AttachmentStorage,
    )

# когда есть расширение чтобы IDE видела все поля в модели делаем хак
if TYPE_CHECKING:
    from backend.base.crm.company.models.company import Company as CompanyBase

    class Company(
        CompanyContractMixin,
        CompanyBase,
    ): ...

else:
    from backend.base.crm.company.models.company import Company

from backend.base.crm.chat.models.chat_external_account import (
    ChatExternalAccount,
)
from backend.base.crm.chat.models.chat_external_chat import ChatExternalChat
from backend.base.crm.chat.models.chat_external_message import (
    ChatExternalMessage,
)
from backend.base.crm.chat.models.chat_message_reaction import (
    ChatMessageReaction,
)

# apps
from backend.base.system.cron.app import CronApp
from backend.base.crm.languages.app import LanguageApp
from backend.base.crm.auth_token.app import AuthTokenApp
from backend.base.system.administration.app import AdministrationApp
from backend.base.crm.users.app import UserApp
from backend.base.crm.security.app import SecurityApp
from backend.base.crm.attachments.app import AttachmentsApp
from backend.base.crm.attachments_google.app import AttachmentsGoogleApp
from backend.base.crm.leads.app import LeadsApp
from backend.base.crm.partners.app import PartnersApp
from backend.base.crm.sales.app import SalesApp
from backend.base.crm.products.app import ProductsApp
from backend.base.crm.company.app import CompanyApp
from backend.base.crm.chat.app import ChatApp
from backend.base.crm.chat_telegram.app import ChatTelegramApp
from backend.base.crm.chat_email.app import ChatEmailApp
from backend.base.crm.tasks.app import TasksApp
from backend.base.crm.activity.app import ActivityApp
from backend.base.crm.report_docx.app import ReportDocxApp
from backend.base.crm.contract.app import ContractApp

# services
from backend.base.system.logger.app import LoggerService
from backend.base.system.swagger_offlain.app import SwaggerOfflainService
from backend.base.system.dotorm_databases_postgres.app import (
    DotormDatabasesPostgresService,
)

from backend.base.system.dotorm_crud_auto.app_v2 import DotormCrudAutoService

# from backend.base.system.dotorm_crud_auto.app import DotormCrudAutoService


class Settings(SettingsCore):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    logger: LoggerSettings
    dotorm_databases_postgres: dict[str, PostgresSettings]
    attachments: AttachmentsSettings = AttachmentsSettings()


# MONKEY PATCH TRICK
env.settings = Settings()  # type: ignore


# ExtensibleMixin добавляет возможно @extend(Lead)
# расширения существующих моделей
class Models(ModelsCore, ExtensibleMixin):
    # system
    system_settings = SystemSettings
    cron_job = CronJob
    # users
    user = User
    saved_filter = SavedFilter
    language = Language
    company = Company
    partner = Partner
    contact = Contact
    contact_type = ContactType
    # security
    role = Role
    rule = Rule
    access_list = AccessList
    model = Model
    app = AppModel
    session = Session
    # attachments
    attachment = Attachment
    attachment_storage = AttachmentStorage
    attachment_route = AttachmentRoute
    attachment_cache = AttachmentCache
    # crm
    sale_line = SaleLine
    sale = Sale
    sale_stage = SaleStage
    team_crm = TeamCrm
    tax = Tax
    uom = Uom
    category = Category
    product = Product
    lead = Lead
    lead_stage = LeadStage
    # chat
    chat = Chat
    chat_member = ChatMember
    chat_message = ChatMessage
    chat_connector = ChatConnector
    chat_external_account = ChatExternalAccount
    chat_external_chat = ChatExternalChat
    chat_external_message = ChatExternalMessage
    chat_message_reaction = ChatMessageReaction
    # project and task
    task = Task
    task_tag = TaskTag
    task_stage = TaskStage
    project = Project
    # activity
    activity = Activity
    activity_type = ActivityType
    report_template = ReportTemplate
    contract = Contract


class Apps(AppsCore):
    "Соглашение имя атрибута должно совпадать с именем папки приложения"

    administration = AdministrationApp()
    cron = CronApp()
    auth = AuthTokenApp()
    languages = LanguageApp()
    users = UserApp()
    security = SecurityApp()
    attachments = AttachmentsApp()
    attachments_google = AttachmentsGoogleApp()
    leads = LeadsApp()
    partners = PartnersApp()
    sales = SalesApp()
    products = ProductsApp()
    company = CompanyApp()
    chat = ChatApp()
    chat_telegram = ChatTelegramApp()
    chat_email = ChatEmailApp()
    task = TasksApp()
    activity = ActivityApp()
    report_docx = ReportDocxApp()
    contract = ContractApp()

    dotorm_crud_auto = DotormCrudAutoService()
    # alise
    db = DotormDatabasesPostgresService()
    logger = LoggerService()
    swagger_offlain = SwaggerOfflainService()
    # mkdocs = MkdocsService()


# MONKEY PATCH TRICK
env.models = Models()._build_table_mapping()
env.apps = Apps()
