from backend.base.system.dotorm.dotorm.fields import (
    Char,
    Integer,
    Boolean,
    Many2one,
    One2many,
)
from backend.base.system.dotorm.dotorm.model import DotModel
from backend.base.system.core.enviroment import env


class Company(DotModel):
    __table__ = "company"

    id: int = Integer(primary_key=True)
    name: str = Char(string="Company Name")
    active: bool = Boolean(default=True)
    sequence: int = Integer(
        help="Used to order Companies in the company switcher", default=10
    )
    parent_id: "Company" = Many2one(
        lambda: env.models.company,
        string="Parent Company",
        index=True,
        ondelete="restrict",
    )
    child_ids: list["Company"] = One2many(
        lambda: env.models.company, "parent_id", string="Child companies"
    )
    # partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    # logo = fields.Binary(related='partner_id.image_1920', default=_get_logo, string="Company Logo", readonly=False)
    # currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self._default_currency_id())
    # user_ids = fields.Many2many('res.users', 'res_company_users_rel', 'cid', 'user_id', string='Accepted Users')
    # street = fields.Char(compute='_compute_address', inverse='_inverse_street')
    # street2 = fields.Char(compute='_compute_address', inverse='_inverse_street2')
    # zip = fields.Char(compute='_compute_address', inverse='_inverse_zip')
    # city = fields.Char(compute='_compute_address', inverse='_inverse_city')
    # state_id = fields.Many2one(
    #     'res.country.state', compute='_compute_address', inverse='_inverse_state',
    #     string="Fed. State", domain="[('country_id', '=?', country_id)]"
    # )
    # bank_ids = fields.One2many(related='partner_id.bank_ids', readonly=False)
    # country_id = fields.Many2one('res.country', compute='_compute_address', inverse='_inverse_country', string="Country")
    # email = fields.Char(related='partner_id.email', store=True, readonly=False)
    # phone = fields.Char(related='partner_id.phone', store=True, readonly=False)
    # mobile = fields.Char(related='partner_id.mobile', store=True, readonly=False)
    # website = fields.Char(related='partner_id.website', readonly=False)
