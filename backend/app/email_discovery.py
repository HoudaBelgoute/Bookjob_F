"""Find publicly listed contact emails on a company's own website."""
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests


class EmailDiscoveryError(Exception):
    """A public contact page could not be safely or reliably checked."""


EMAIL_PATTERN = re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\b")
CONTACT_WORDS = ("contact", "recrut", "emploi", "career", "job", "rh", "about", "equipe", "équipe")
MAX_PAGES = 8
MAX_PAGE_BYTES = 1_000_000


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href", "")
            if href:
                self.links.append(href)


def _canonical_host(host: str) -> str:
    return host.lower().removeprefix("www.")


def _normalize_site_url(site_url: str) -> tuple[str, str]:
    raw = site_url.strip()
    if not raw:
        raise EmailDiscoveryError("Cette entreprise n'a pas de site web enregistré.")
    parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise EmailDiscoveryError("L'adresse du site web de l'entreprise est invalide.")
    if parsed.username or parsed.password:
        raise EmailDiscoveryError("Le site web enregistré n'est pas une adresse publique valide.")
    port = parsed.port
    if port not in (None, 443) and not (parsed.scheme == "http" and port == 80):
        raise EmailDiscoveryError("Le site web enregistré n'est pas une adresse publique valide.")
    host = parsed.hostname.lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise EmailDiscoveryError("La recherche est limitée aux noms de domaine des sites d'entreprise.")
    netloc = host if port in (None, 80) else f"{host}:{port}"
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, "")), _canonical_host(host)


def _is_public_host(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as ex:
        raise EmailDiscoveryError("Le site de l'entreprise est inaccessible ou son domaine est introuvable.") from ex
    if not addresses:
        raise EmailDiscoveryError("Le domaine du site de l'entreprise ne renvoie aucune adresse.")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise EmailDiscoveryError("La recherche a été bloquée car le site ne pointe pas vers une adresse publique.")
    return True


def _is_same_site(url: str, base_host: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and _canonical_host(parsed.hostname) == base_host
        and parsed.port in (None, 443)
        and not parsed.username
        and not parsed.password
    )


def _fetch_page(url: str, base_host: str) -> tuple[str, str] | None:
    current = url
    for _ in range(4):
        if not _is_same_site(current, base_host):
            raise EmailDiscoveryError("Le site a redirigé vers un domaine différent; recherche interrompue.")
        parsed = urlsplit(current)
        if not _is_public_host(parsed.hostname or ""):
            raise EmailDiscoveryError("Le site n'est pas accessible publiquement.")
        try:
            response = requests.get(
                current,
                headers={"User-Agent": "BookJobContactFinder/1.0"},
                timeout=(3, 8),
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as ex:
            raise EmailDiscoveryError("Impossible de consulter le site officiel de l'entreprise.") from ex
        if response.is_redirect:
            location = response.headers.get("Location", "")
            response.close()
            if not location:
                return None
            current = urljoin(current, location)
            continue
        if response.status_code == 404:
            response.close()
            return None
        if not response.ok:
            status_code = response.status_code
            response.close()
            raise EmailDiscoveryError(f"Le site de l'entreprise a répondu avec une erreur HTTP {status_code}.")
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            response.close()
            return None
        try:
            content = bytearray()
            for chunk in response.iter_content(chunk_size=16_384):
                content.extend(chunk)
                if len(content) >= MAX_PAGE_BYTES:
                    break
            text = bytes(content[:MAX_PAGE_BYTES]).decode(response.encoding or "utf-8", errors="replace")
        except requests.RequestException as ex:
            raise EmailDiscoveryError("La lecture du site officiel a échoué.") from ex
        finally:
            response.close()
        return current, text
    raise EmailDiscoveryError("Le site de l'entreprise a effectué trop de redirections.")


def find_public_emails(site_url: str) -> list[dict[str, str]]:
    """Return unique email addresses and the exact page on which each was published."""
    homepage, base_host = _normalize_site_url(site_url)
    pending = [homepage]
    parsed_home = urlsplit(homepage)
    for path in ("/contact", "/contact-us", "/contactez-nous", "/nous-contacter", "/recrutement", "/careers"):
        pending.append(urlunsplit(("https", parsed_home.netloc, path, "", "")))

    found: dict[str, dict[str, str]] = {}
    visited = set()
    while pending and len(visited) < MAX_PAGES:
        page_url = pending.pop(0)
        if page_url in visited:
            continue
        visited.add(page_url)
        page = _fetch_page(page_url, base_host)
        if page is None:
            continue
        final_url, html = page
        parser = _PageParser()
        parser.feed(html)
        emails = set(EMAIL_PATTERN.findall(html))
        for href in parser.links:
            if href.lower().startswith("mailto:"):
                emails.update(EMAIL_PATTERN.findall(href[7:].split("?", 1)[0]))
            elif len(pending) + len(visited) < MAX_PAGES:
                link = urljoin(final_url, href)
                if _is_same_site(link, base_host) and any(word in urlsplit(link).path.lower() for word in CONTACT_WORDS):
                    pending.append(link)
        for email in emails:
            normalized = email.strip(".,;:")
            if normalized and normalized.lower() not in found:
                found[normalized.lower()] = {"email": normalized, "source": final_url}
    return sorted(
        found.values(),
        key=lambda item: (
            not any(word in item["source"].lower() for word in ("recrut", "career", "emploi", "job")),
            item["email"].lower(),
        ),
    )
