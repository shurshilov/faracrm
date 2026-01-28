# from datetime import datetime, timezone
from ssl import (
    CERT_REQUIRED,
    VERIFY_CRL_CHECK_CHAIN,
    PROTOCOL_TLSv1_2,
    SSLContext,
)

# import pytz


def create_ssl_context(
    client_cert, client_key, ca_bundle, crl=None, protocol=PROTOCOL_TLSv1_2
):
    ctx = SSLContext(protocol=protocol)
    ctx.verify_mode = CERT_REQUIRED
    if client_cert and client_key:
        ctx.load_cert_chain(certfile=client_cert, keyfile=client_key)
    if ca_bundle:
        ctx.load_verify_locations(cafile=ca_bundle)
    if crl:
        ctx.load_verify_locations(cafile=crl)
        ctx.verify_flags = VERIFY_CRL_CHECK_CHAIN
    return ctx


# def from_datetime_to_iso8601(dt: datetime, tz: str) -> str:
#     result = (
#         pytz.timezone(tz)
#         .localize(dt)
#         .astimezone(pytz.utc)
#         .strftime("%Y-%m-%dT%H:%M:%SZ")
#     )
#     return result


# def from_iso8601_to_str(date: datetime, tz: str) -> str:
#     result = (
#         date.replace(tzinfo=timezone.utc)
#         .astimezone(pytz.timezone(tz))
#         .strftime("%Y-%m-%d %H:%M:%S")
#     )

#     return result


def camel_to_snake(camel: str):
    return "".join(["_" + c.lower() if c.isupper() else c for c in camel]).lstrip("_")


def snake_to_camel(snake: str):
    return "".join(x.capitalize() for x in snake.lower().split("_"))
