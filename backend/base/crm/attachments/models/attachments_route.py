# from ..schemas.attachments_route import SchemaAttachmentRoute
# from backend.base.system.dotorm.dotorm.fields import Char, Integer, Many2one, Text
# from backend.base.system.dotorm.dotorm.model import DotModel


# class AttachmentRoute(DotModel):
#     __table__ = "attachments_route"
#     __route__ = "/attachments_routes"
#
#     __schema__ = SchemaAttachmentRoute
#

#     id: int = Integer(primary_key=True)
#     model_id = Many2one("models", domain=[("transient", "=", False)])
#     model = Char(
#         related="model_id.model",
#         string="Related Document Model",
#         store=True,
#         readonly=True,
#     )
#     pattern_record = Char(
#         "Folder pattern record template",
#         help="""For every record like SO1234
#         Example: {{zfill(object.id)}}-{{object.name}}.
#         Available functions:
#         'ctx'
#         'format_date'
#         'format_datetime'
#         'format_time'
#         'format_amount'
#         'format_duration'
#         'is_html_empty'
#         'slug'
#         'user'
#         'zfiil'
#         and pyton builtins funs like str, len ...
#         """,
#     )
#     pattern_root = Char(
#         "Folder pattern root (model) template",
#         help="""For all model like Sales Order
#         Example: {{zfill(object.id)}}-{{object.name}}.
#         Available functions:
#         'ctx'
#         'format_date'
#         'format_datetime'
#         'format_time'
#         'format_amount'
#         'format_duration'
#         'is_html_empty'
#         'slug'
#         'user'
#         'zfiil'
#         and pyton builtins funs like str, len ...
#         """,
#     )
#     filter = Text(
#         "Filtering",
#         default="[]",
#         help="""Filtering records to sync in model""",
#     )
#     folder_id = Char(
#         string="Folder cloud ID",
#         copy=False,
#         help="""Show route activate or not.
#         If at least one file has been created along the route folder_id will not empty""",
#     )
