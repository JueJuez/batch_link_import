import re
from typing import Set, Tuple, List

from assets.tracker import load_imported_list
from assets.storage import owner_repo_keys as _owner_repo_keys

GITHUB_URL_PATTERN = re.compile(
    r'https://github\.com/([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+?)(?:\.git)?(?=[/\s\)\]>]|$)'
)
GITHUB_SSH_PATTERN = re.compile(
    r'git@github\.com:([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+)\.git'
)

_NON_REPO_OWNERS = frozenset({
    "settings", "notifications", "dashboard", "explore", "marketplace",
    "pulls", "issues", "sponsors", "organizations", "new", "search",
    "collections", "topics", "trending", "about", "contact", "sites",
    "security", "features", "team", "enterprise", "pricing",
    "login", "signup", "join", "careers", "blog", "support",
    "community", "integrations", "events", "customer-stories",
})


def _normalize(repo: str) -> str:
    return repo.rstrip("/").removesuffix(".git")


def _is_valid_repo(owner: str) -> bool:
    return owner.lower() not in _NON_REPO_OWNERS and "." not in owner


def extract_github_urls(text: str) -> List[str]:
    raw_urls = set()
    for match in GITHUB_URL_PATTERN.finditer(text):
        owner, repo = match.group(1), _normalize(match.group(2))
        if _is_valid_repo(owner):
            raw_urls.add(f"https://github.com/{owner}/{repo}")
    for match in GITHUB_SSH_PATTERN.finditer(text):
        owner, repo = match.group(1), match.group(2)
        raw_urls.add(f"https://github.com/{owner}/{repo}")
    return sorted(raw_urls)


def _match_url(url: str):
    m = GITHUB_URL_PATTERN.match(url)
    if m:
        return m
    return GITHUB_SSH_PATTERN.match(url)


def normalize_url(url: str) -> str:
    match = _match_url(url)
    if match:
        return f"https://github.com/{match.group(1)}/{_normalize(match.group(2))}"
    return url


def owner_repo_key(url: str) -> str:
    match = _match_url(url)
    if match:
        return f"{match.group(1).lower()}/{_normalize(match.group(2)).lower()}"
    return url.lower()


def batch_deduplicate(urls: List[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for url in urls:
        key = owner_repo_key(url)
        if key not in seen:
            seen.add(key)
            result.append(normalize_url(url))
    return result


def filter_imported(
    urls: List[str],
) -> Tuple[List[str], List[str]]:
    imported = load_imported_list()
    new_urls: List[str] = []
    skipped: List[str] = []
    for url in urls:
        key = owner_repo_key(url)
        if key in imported:
            skipped.append(normalize_url(url))
        else:
            new_urls.append(normalize_url(url))
    return new_urls, skipped


def filter_pending(
    urls: List[str],
) -> Tuple[List[str], List[str]]:
    pending = _owner_repo_keys()
    if not pending:
        return list(urls), []
    new_urls: List[str] = []
    skipped: List[str] = []
    for url in urls:
        key = owner_repo_key(url)
        if key in pending:
            skipped.append(normalize_url(url))
        else:
            new_urls.append(normalize_url(url))
    return new_urls, skipped


def parse_owner_repo(url: str) -> Tuple[str, str]:
    match = _match_url(normalize_url(url))
    if match:
        return match.group(1), _normalize(match.group(2))
    raise ValueError(f"Not a valid GitHub URL: {url}")