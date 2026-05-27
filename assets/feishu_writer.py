import subprocess
import json
import time
import os
from typing import Optional


def _get_default_base_token() -> str:
    return os.environ.get("FEISHU_BASE_TOKEN", "")


def _get_default_table_id() -> str:
    return os.environ.get("FEISHU_TABLE_ID", "")


def _run_lark_cli(args: list) -> Optional[dict]:
    try:
        result = subprocess.run(
            ["lark-cli"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            shell=True,
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            print(f"  lark-cli 执行失败: {error_msg}")
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"stdout": result.stdout.strip()}
    except FileNotFoundError:
        print("  lark-cli 未安装或未找到")
        return None
    except Exception as e:
        print(f"  lark-cli 执行异常: {e}")
        return None


def write_record(
    fields: dict,
    base_token: Optional[str] = None,
    table_id: Optional[str] = None,
) -> bool:
    base_token = base_token or _get_default_base_token()
    table_id = table_id or _get_default_table_id()
    if not base_token or not table_id:
        print("  ❌ 未配置飞书 Base Token 或 Table ID")
        print("     请设置环境变量 FEISHU_BASE_TOKEN 和 FEISHU_TABLE_ID")
        print("     或在调用时传入 base_token 和 table_id 参数")
        return False
    args = [
        "base",
        "+create-record",
        base_token,
        table_id,
        "--fields",
        json.dumps(fields, ensure_ascii=False),
    ]
    result = _run_lark_cli(args)
    if result and (result.get("ok") or result.get("code") == 0):
        return True
    if result and result.get("error"):
        print(f"  飞书写入失败: {result['error']}")
    return False


def write_record_with_retry(
    fields: dict,
    base_token: Optional[str] = None,
    table_id: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: int = 1,
) -> bool:
    for attempt in range(max_retries):
        if write_record(fields, base_token, table_id):
            return True
        if attempt < max_retries - 1:
            print(f"  重试第 {attempt + 1} 次...")
            time.sleep(retry_delay)
    return False


def check_lark_cli_available() -> bool:
    result = _run_lark_cli(["--version"])
    return result is not None