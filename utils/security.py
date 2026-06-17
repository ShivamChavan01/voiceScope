import ipaddress
import re
import hashlib
from urllib.parse import urlparse
from utils.logger import logger


BLOCKED_SCHEMES = {"file", "ftp", "gopher", "unix", "javascript"}

PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def validate_callback_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("https",):
        logger.warning(f"[Security] callback_url rejected: scheme={parsed.scheme}")
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    try:
        ip = ipaddress.ip_address(hostname)
        if any(ip in net for net in PRIVATE_RANGES):
            logger.warning(f"[Security] callback_url rejected: private IP={hostname}")
            return False
    except ValueError:
        pass

    return True


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


PLUGIN_DIR = "plugins"
VALID_MODULE_PATTERN = re.compile(r"^(plugins|examples)\.[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_plugin_path(module_path: str) -> bool:
    return bool(VALID_MODULE_PATTERN.match(module_path))


def sanitize_log_input(s: str, max_len: int = 200) -> str:
    return re.sub(r"[\n\r\x00-\x1f]", "", str(s))[:max_len]
