import time
from typing import Optional, Tuple

_API_HEADERS = {"User-Agent": "batch-link-import/1.0"}


def get_readme_url(owner: str, repo: str, branch: str = "main") -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md"


def get_github_api_url(owner: str, repo: str) -> str:
    return f"https://api.github.com/repos/{owner}/{repo}"


def stars_to_score(stars: int) -> int:
    if stars <= 10:
        return 1
    elif stars <= 100:
        return 2
    elif stars <= 500:
        return 3
    elif stars <= 1000:
        return 4
    elif stars <= 5000:
        return 5
    elif stars <= 10000:
        return 6
    elif stars <= 30000:
        return 7
    elif stars <= 100000:
        return 8
    else:
        return 9 if stars <= 500000 else 10


def _fetch_with_retry(url: str, timeout: int = 15) -> Tuple[Optional[str], Optional[str]]:
    try:
        import requests
    except ImportError:
        return None, "requests library not available"
    try:
        resp = requests.get(url, timeout=timeout, headers=_API_HEADERS)
        if resp.status_code == 200:
            return resp.text, None
        elif resp.status_code == 404:
            return None, "Not found (404)"
        elif resp.status_code == 403:
            return None, "Access denied (403)"
        else:
            return None, f"HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return None, "Request timed out"
    except requests.exceptions.ConnectionError:
        return None, "Connection error"
    except Exception as e:
        return None, f"Unexpected error: {e}"


def collect_project_data(
    owner: str, repo: str, max_retries: int = 3, retry_delay: int = 1
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    readme = None
    for attempt in range(max_retries):
        readme_url = get_readme_url(owner, repo)
        content, error = _fetch_with_retry(readme_url)
        if content is not None:
            readme = content
            break
        if error == "Not found (404)" and attempt == 0:
            readme_url = get_readme_url(owner, repo, branch="master")
            content, error = _fetch_with_retry(readme_url)
            if content is not None:
                readme = content
                break
        if error not in ("Not found (404)", "Access denied (403)"):
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
        return None, None, f"README fetch failed: {error}"

    stars = 0
    api_url = get_github_api_url(owner, repo)
    for attempt in range(max_retries):
        content, error = _fetch_with_retry(api_url)
        if content is not None:
            try:
                import json
                data = json.loads(content)
                stars = data.get("stargazers_count", 0)
                if stars is None:
                    stars = 0
                break
            except (json.JSONDecodeError, ValueError):
                pass
        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    return readme, stars, None