import re
import unicodedata
from uuid import NAMESPACE_URL, UUID, uuid5

_APOSTROPHES = re.compile("[\u02bb\u02bc\u2018\u2019\u0060\u00b4\u2032']")
_WHITESPACE = re.compile(r"\s+")
_ID_NAMESPACE = uuid5(NAMESPACE_URL, "semantic-qa")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = _APOSTROPHES.sub("'", text)
    return _WHITESPACE.sub(" ", text).strip()


def stable_id(text: str) -> UUID:
    return uuid5(_ID_NAMESPACE, normalize(text))
