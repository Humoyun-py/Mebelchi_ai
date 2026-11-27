from .base import NotImplementedProvider


class UzumProvider(NotImplementedProvider):
    """Not implemented. developer.uzumbank.uz renders its API reference client-side and answered 500/timeouts when it was opened, so the
    webhook fields and the way callbacks are authenticated are unknown and are not guessed. Uzum onboarding also goes through an account manager."""

    name = "uzum"
