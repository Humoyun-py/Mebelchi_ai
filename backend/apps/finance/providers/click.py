from .base import NotImplementedProvider


class ClickProvider(NotImplementedProvider):
    """Not implemented. The official Click SHOP-API pages (docs.click.uz) could not be read (the site served its overview page for every
    path), so the Prepare/Complete fields, the sign_string rule and the error codes are unknown and are not guessed."""

    name = "click"
