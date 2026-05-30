from esi.models import Token
from esi.openapi_clients import ESIClientProvider

from srpmod import __version__


def get_token(character_id, scopes):
    """
    Helper method to get a token for a specific character with specific scopes
    :return: :class:'esi.models.Token or False
    """
    try:
        return Token.objects.filter(character_id=character_id).require_scopes(scopes)[0]
    except:
        return False


provider = ESIClientProvider(
    compatibility_date="2026-05-30",
    ua_appname="allianceauth-srp-mod",
    ua_version=__version__,
    operations=["GetCharactersCharacterIdOnline", "PostUiOpenwindowInformation"],
)