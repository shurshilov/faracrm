from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Many2one,
    One2many,
    PolymorphicMany2one,
    Selection,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env
from backend.base.crm.attachments.models.attachments import Attachment

# Доступные типы соцсетей для странички логина.
# Список расширяемый — добавил новый, и сразу появился в Selection.
# label на фронте берётся из SOCIAL_TYPE_META (см. SignIn.tsx),
# здесь label нужен только для админки.
_SOCIAL_OPTIONS: list[tuple[str, str]] = [
    ("telegram", "Telegram"),
    ("github", "GitHub"),
    ("rutube", "RuTube"),
    ("youtube", "YouTube"),
    ("vk", "ВКонтакте"),
    ("whatsapp", "WhatsApp"),
    ("linkedin", "LinkedIn"),
    ("x", "X (Twitter)"),
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("discord", "Discord"),
    ("email", "Email"),
    ("website", "Website"),
]


class Company(DotModel):
    __table__ = "company"

    id: int = Integer(primary_key=True)
    name: str = Char(string="Company Name")
    active: bool = Boolean(default=True)
    sequence: int = Integer(
        help="Used to order Companies in the company switcher", default=10
    )
    parent_id: "Company | None" = Many2one(
        lambda: env.models.company,
        string="Parent Company",
        index=True,
        ondelete="restrict",
    )
    child_ids: list["Company"] = One2many(
        lambda: env.models.company, "parent_id", string="Child companies"
    )

    logo_id: "Attachment | None" = PolymorphicMany2one(
        relation_table=Attachment,
    )
    login_logo_id: "Attachment | None" = PolymorphicMany2one(
        relation_table=Attachment,
    )
    login_background_id: "Attachment | None" = PolymorphicMany2one(
        relation_table=Attachment,
    )

    # Тексты на странице входа
    login_title: str | None = Char(
        string="Login title",
        description="Заголовок на странице входа",
    )
    login_subtitle: str | None = Char(
        string="Login subtitle",
        description="Подзаголовок (под логотипом) на странице входа",
    )
    # Цвет кнопки "Войти" на странице входа (HEX, например "#009982").
    # Если пусто — используется дефолтный цвет из CSS.
    login_button_color: str | None = Char(
        string="Login button color",
        description="Цвет кнопки входа в формате HEX (#RRGGBB)",
    )

    # Стиль карточки на странице входа.
    # - elevated: современный объёмный (тень, скругление, отступ от краёв)
    # - flat:     классический плоский (на всю высоту, без тени)
    # Список расширяемый — в будущем можно добавить glass, outlined и пр.
    login_card_style: str = Selection(
        string="Login card style",
        description="Стиль карточки на странице входа",
        options=[
            ("elevated", "Elevated (объёмный)"),
            ("flat", "Flat (плоский)"),
        ],
        default="elevated",
    )

    # Соцсети на странице входа. До 3 штук.
    # Если type или url пусты — ссылка не выводится. Если все 3 пусты —
    # показываются дефолтные ссылки FARA (Telegram/GitHub/RuTube).
    # Label генерируется по type на фронте (см. SOCIAL_TYPE_META).
    login_social1_type: str | None = Selection(
        string="Login social #1 type",
        description="Тип первой соцсети на странице входа",
        options=_SOCIAL_OPTIONS,
    )
    login_social1_url: str | None = Char(
        string="Login social #1 URL",
        description="Ссылка для первой соцсети",
    )
    login_social2_type: str | None = Selection(
        string="Login social #2 type",
        description="Тип второй соцсети на странице входа",
        options=_SOCIAL_OPTIONS,
    )
    login_social2_url: str | None = Char(
        string="Login social #2 URL",
        description="Ссылка для второй соцсети",
    )
    login_social3_type: str | None = Selection(
        string="Login social #3 type",
        description="Тип третьей соцсети на странице входа",
        options=_SOCIAL_OPTIONS,
    )
    login_social3_url: str | None = Char(
        string="Login social #3 URL",
        description="Ссылка для третьей соцсети",
    )
