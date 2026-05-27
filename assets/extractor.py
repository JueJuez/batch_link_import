import re
from pathlib import Path
from typing import Set, Tuple, List

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

IMPORTED_FILE = Path(__file__).resolve().parent.parent / "imported.txt"


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


def load_imported_list() -> Set[str]:
    if not IMPORTED_FILE.exists():
        return set()
    result: Set[str] = set()
    with open(IMPORTED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                result.add(line.lower())
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


def parse_owner_repo(url: str) -> Tuple[str, str]:
    match = _match_url(normalize_url(url))
    if match:
        return match.group(1), _normalize(match.group(2))
    raise ValueError(f"Not a valid GitHub URL: {url}")