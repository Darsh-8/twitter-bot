from newsbot.adapters.social.dry_run_client import DryRunXClient
from newsbot.adapters.social.x_client import TweepyXClient
from newsbot.application.interfaces.social_client import SocialPostClient
from newsbot.config.settings import Settings


def get_social_client(settings: Settings) -> SocialPostClient:
    if settings.dry_run:
        return DryRunXClient()

    missing = [
        name
        for name, value in (
            ("X_API_KEY", settings.x_api_key),
            ("X_API_SECRET", settings.x_api_secret),
            ("X_ACCESS_TOKEN", settings.x_access_token),
            ("X_ACCESS_TOKEN_SECRET", settings.x_access_token_secret),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing X API credentials for live posting: {', '.join(missing)}")

    return TweepyXClient(
        api_key=settings.x_api_key.get_secret_value(),
        api_secret=settings.x_api_secret.get_secret_value(),
        access_token=settings.x_access_token.get_secret_value(),
        access_token_secret=settings.x_access_token_secret.get_secret_value(),
    )
