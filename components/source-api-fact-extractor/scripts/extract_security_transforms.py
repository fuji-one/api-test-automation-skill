from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from extract_call_chain import find_method
from extract_java_api import UNKNOWN, JavaClass, JavaMethod, SourceFile, evidence


SECURITY_CONFIG_KEY_RE = re.compile(
    r"(?P<key>[A-Za-z0-9_.-]*(?:secret|password|passwd|pwd|token|key|aes-key|callbackSecret|apiSecretKey)[A-Za-z0-9_.-]*)\s*[:=]\s*(?P<value>[^\n\r]+)",
    flags=re.IGNORECASE,
)


def build_security_transforms(
    apis: list[dict[str, Any]],
    classes: dict[str, JavaClass],
    files: list[SourceFile],
    call_chains: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    unique_classes = {id(value): value for value in classes.values()}
    class_by_name = {java_class.name: java_class for java_class in unique_classes.values()}
    api_transforms: dict[str, list[dict[str, Any]]] = {}

    for api in apis:
        api_id = api["api_id"]
        transforms: list[dict[str, Any]] = []
        for chain_item in call_chains.get(api_id, []):
            java_class = class_by_name.get(chain_item.get("class_name", ""))
            if not java_class:
                continue
            method = find_method(java_class, chain_item.get("method_name", ""))
            if not method:
                continue
            transforms.extend(scan_method_security_transforms(java_class, method, api_id))
        api_transforms[api_id] = dedupe_transforms(assign_transform_ids(api_id, transforms))

    project_transforms = dedupe_transforms(
        assign_transform_ids(
            "PROJECT",
            [
                transform
                for java_class in unique_classes.values()
                for method in java_class.methods
                for transform in scan_method_security_transforms(java_class, method, "PROJECT")
            ],
        )
    )
    secret_config_refs = collect_secret_config_refs(files)
    return {
        "api_transforms": api_transforms,
        "project_transforms": project_transforms,
        "secret_config_refs": secret_config_refs,
        "summary": {
            "api_security_transform_count": sum(len(items) for items in api_transforms.values()),
            "project_security_transform_count": len(project_transforms),
            "secret_config_ref_count": len(secret_config_refs),
        },
    }


def scan_method_security_transforms(java_class: JavaClass, method: JavaMethod, api_id: str) -> list[dict[str, Any]]:
    body = method.body or ""
    transforms: list[dict[str, Any]] = []
    transforms.extend(match_call_transforms(java_class, method, api_id, body))
    transforms.extend(match_context_transforms(java_class, method, api_id, body))
    return transforms


def match_call_transforms(
    java_class: JavaClass,
    method: JavaMethod,
    api_id: str,
    body: str,
) -> list[dict[str, Any]]:
    specs = [
        {
            "pattern": r"\bCryptoUtils\.encrypt\s*\(",
            "transform_type": "FIELD_ENCRYPT",
            "algorithm": UNKNOWN,
            "input_role": "plain_value",
            "output_role": "cipher_text",
            "deterministic": UNKNOWN,
            "reversible": UNKNOWN,
            "requires_secret": "YES",
            "config_key": UNKNOWN,
            "execution_impact": "请求明文字段会在该工具调用点被加密；具体算法、可逆性和密钥来源需继续追踪实现或配置绑定。",
            "script_assertion_strategy": "算法和密钥来源确认前，不得猜测固定密文；应通过同一业务接口或已确认的加密适配器准备数据。",
        },
        {
            "pattern": r"\bCryptoUtils\.decrypt\s*\(",
            "transform_type": "FIELD_DECRYPT",
            "algorithm": UNKNOWN,
            "input_role": "cipher_text",
            "output_role": "plain_value",
            "deterministic": UNKNOWN,
            "reversible": UNKNOWN,
            "requires_secret": "YES",
            "config_key": UNKNOWN,
            "execution_impact": "服务端会在该工具调用点解密字段后再用于校验或下游调用；具体算法和密钥来源需继续追踪。",
            "script_assertion_strategy": "算法和密钥来源确认前，应通过前置接口生成真实密文，不能按工具类名猜测加密参数。",
        },
        {
            "pattern": r"\b(?:HashUtils\.sha256|DigestUtil\.sha256Hex)\s*\(",
            "transform_type": "FIELD_HASH",
            "algorithm": "SHA-256_HEX",
            "input_role": "plain_value",
            "output_role": "hash_value",
            "deterministic": "YES",
            "reversible": "NO",
            "requires_secret": "NO",
            "config_key": "NONE",
            "execution_impact": "请求明文字段会生成 SHA-256 哈希，通常用于唯一索引或查询。",
            "script_assertion_strategy": "执行脚本断言哈希字段时应对明文计算 SHA-256 后比对，不能期待数据库保存明文。",
        },
        {
            "pattern": r"\b(?:HashUtils\.md5|DigestUtil\.md5Hex(?:16)?)\s*\(",
            "transform_type": "FIELD_HASH",
            "algorithm": "MD5_HEX",
            "input_role": "plain_value",
            "output_role": "hash_value",
            "deterministic": "YES",
            "reversible": "NO",
            "requires_secret": "NO",
            "config_key": "NONE",
            "execution_impact": "源码使用 MD5 派生字段或路径，通常用于标识混淆而非安全存储。",
            "script_assertion_strategy": "执行脚本如需断言派生路径或字段，应按源码 MD5 规则计算期望值。",
        },
        {
            "pattern": r"\b(?:PasswordUtils\.encode|passwordPort\.encode|BCrypt\.hashpw)\s*\(",
            "transform_type": "PASSWORD_HASH",
            "algorithm": "BCRYPT",
            "input_role": "raw_password",
            "output_role": "password_hash",
            "deterministic": "NO",
            "reversible": "NO",
            "requires_secret": "NO",
            "config_key": "NONE",
            "execution_impact": "密码哈希带随机 salt，同一明文每次生成的密文不同。",
            "script_assertion_strategy": "执行脚本不能断言固定哈希值，应断言非明文、非空，并通过 matches 或登录链路验证。",
        },
        {
            "pattern": r"\b(?:PasswordUtils\.matches|passwordPort\.matches|BCrypt\.checkpw)\s*\(",
            "transform_type": "PASSWORD_VERIFY",
            "algorithm": "BCRYPT",
            "input_role": "raw_password_and_hash",
            "output_role": "boolean",
            "deterministic": "YES",
            "reversible": "NO",
            "requires_secret": "NO",
            "config_key": "NONE",
            "execution_impact": "服务端使用 BCrypt 校验明文密码和已有哈希。",
            "script_assertion_strategy": "执行脚本应通过接口行为验证密码正确或错误分支，不直接构造固定哈希。",
        },
        {
            "pattern": r"\bredisTokenPort\.createToken\s*\(",
            "transform_type": "TOKEN_GENERATE",
            "algorithm": UNKNOWN,
            "input_role": "user_id",
            "output_role": "login_token",
            "deterministic": UNKNOWN,
            "reversible": "NO",
            "requires_secret": "NO",
            "config_key": UNKNOWN,
            "execution_impact": "登录 token 由服务端生成；仅凭端口方法名不能确认随机算法、存储介质或配置键。",
            "script_assertion_strategy": "执行脚本必须从登录响应提取 token，并在后续请求中复用；不要自行构造 JWT。",
        },
        {
            "pattern": r"\bsignWith\s*\(",
            "transform_type": "JWT_SIGN",
            "algorithm": UNKNOWN,
            "input_role": "claims",
            "output_role": "signed_jwt",
            "deterministic": "NO",
            "reversible": "NO",
            "requires_secret": "YES",
            "config_key": UNKNOWN,
            "execution_impact": "源码存在 JWT 签名调用，具体签名算法和密钥来源需从参数及配置绑定继续追踪。",
            "script_assertion_strategy": "除非算法和密钥来源已由源码或执行配置确认，否则脚本应通过登录接口获取 token。",
        },
        {
            "pattern": r"\b(?:verifyWith|parseSignedClaims)\s*\(",
            "transform_type": "JWT_VERIFY",
            "algorithm": UNKNOWN,
            "input_role": "signed_jwt",
            "output_role": "claims_or_invalid",
            "deterministic": "YES",
            "reversible": "NO",
            "requires_secret": "YES",
            "config_key": UNKNOWN,
            "execution_impact": "服务端会校验 JWT 签名和有效期。",
            "script_assertion_strategy": "执行脚本应使用服务端签发 token；非法 token 用例可构造篡改签名或过期 token。",
        },
        {
            "pattern": r"\bgeneratePresignedUrl\s*\(",
            "transform_type": "PRESIGNED_URL_GENERATE",
            "algorithm": UNKNOWN,
            "input_role": "object_key_and_expire_time",
            "output_role": "presigned_url",
            "deterministic": "NO",
            "reversible": "NO",
            "requires_secret": "YES",
            "config_key": UNKNOWN,
            "execution_impact": "预签名 URL 由存储 SDK 生成，提供商、凭证配置键和签名细节需继续追踪。",
            "script_assertion_strategy": "执行脚本应调用接口获取预签名 URL，只断言 URL 非空、有效期语义和关键字段，不硬编码完整 URL。",
        },
        {
            "pattern": r"\bTencentUtil\.genUserSig\s*\(",
            "transform_type": "EXTERNAL_USER_SIG_GENERATE",
            "algorithm": "TENCENT_RTC_USER_SIG",
            "input_role": "user_id_and_sdk_secret",
            "output_role": "user_sig",
            "deterministic": "NO",
            "reversible": "NO",
            "requires_secret": "YES",
            "config_key": UNKNOWN,
            "execution_impact": "RTC UserSig 由腾讯 SDK 密钥生成并可缓存。",
            "script_assertion_strategy": "执行脚本应调用接口获取 UserSig，只断言非空和缓存/过期行为，不自行伪造。",
        },
        {
            "pattern": r"\b(?:ApplePayValidator\.verify|googlePayValidator\.verify)\s*\(",
            "transform_type": "EXTERNAL_RECEIPT_VERIFY",
            "algorithm": "PAYMENT_RECEIPT_VERIFY",
            "input_role": "receipt_or_purchase_token",
            "output_role": "verified_result",
            "deterministic": "UNKNOWN",
            "reversible": "NO",
            "requires_secret": "YES",
            "config_key": UNKNOWN,
            "execution_impact": "支付验签依赖 Apple/Google 外部凭证和真实票据。",
            "script_assertion_strategy": "执行脚本应使用沙箱票据或 mock 支付适配器；不能凭源码生成真实 purchaseToken 或 receipt。",
        },
    ]
    transforms: list[dict[str, Any]] = []
    for spec in specs:
        for match in re.finditer(spec["pattern"], body):
            if spec["transform_type"] == "TOKEN_GENERATE" and not token_context(java_class, method, body, match.start()):
                continue
            transforms.append(build_transform(java_class, method, api_id, body, match, spec))
    return transforms


def match_context_transforms(
    java_class: JavaClass,
    method: JavaMethod,
    api_id: str,
    body: str,
) -> list[dict[str, Any]]:
    transforms: list[dict[str, Any]] = []
    if re.search(r"Mac\.getInstance\s*\(\s*[\"']HmacSHA256[\"']\s*\)", body):
        transforms.append(
            context_transform(
                java_class,
                method,
                api_id,
                body,
                "SIGNATURE_VERIFY",
                "HMAC_SHA256_BASE64",
                "request_body_and_secret",
                "signature_header",
                "YES",
                "NO",
                "YES",
                UNKNOWN,
                "接口会使用 HMAC-SHA256 + Base64 校验回调签名。",
                "执行脚本正向回调用例必须使用源码绑定的实际密钥对原始 body 生成 Sign header；负向用例可使用错误签名。",
            )
        )
    if re.search(r"MessageDigest\.getInstance\s*\(\s*[\"']SHA-1[\"']\s*\)", body):
        transforms.append(
            context_transform(
                java_class,
                method,
                api_id,
                body,
                "SIGNATURE_GENERATE",
                "SHA1_CHECKSUM",
                "secret_nonce_cur_time",
                "checksum_header",
                "YES",
                "NO",
                "YES",
                UNKNOWN,
                "源码按 SHA1(secret + nonce + curTime) 生成外部请求 CheckSum。",
                "执行脚本如直连外部 API 或校验出站请求，应按源码顺序计算 CheckSum。",
            )
        )
    if re.search(r"\bUUID\.randomUUID\s*\(", body) and token_context(java_class, method, body, 0):
        transforms.append(
            context_transform(
                java_class,
                method,
                api_id,
                body,
                "TOKEN_GENERATE",
                "UUID_RANDOM",
                "server_runtime",
                "random_token",
                "NO",
                "NO",
                "NO",
                "NONE",
                "源码使用 UUID 生成随机 token 或随机标识。",
                "执行脚本应从接口响应或数据库读取实际值，不要预测 UUID。",
            )
        )
    return transforms


def build_transform(
    java_class: JavaClass,
    method: JavaMethod,
    api_id: str,
    body: str,
    match: re.Match[str],
    spec: dict[str, str],
) -> dict[str, Any]:
    line = method.line + body.count("\n", 0, match.start())
    open_paren = body.find("(", match.start())
    return {
        "transform_id": "",
        "api_id": api_id,
        "scope": "PROJECT" if api_id == "PROJECT" else "API",
        "class_name": java_class.name,
        "method_name": method.name,
        "transform_type": spec["transform_type"],
        "algorithm": spec["algorithm"],
        "input_role": spec["input_role"],
        "output_role": spec["output_role"],
        "source_expression": first_argument(body, open_paren),
        "target_expression": assignment_target(body, match.start()),
        "deterministic": spec["deterministic"],
        "reversible": spec["reversible"],
        "requires_secret": spec["requires_secret"],
        "config_key": spec["config_key"],
        "execution_impact": spec["execution_impact"],
        "script_assertion_strategy": spec["script_assertion_strategy"],
        "evidence": evidence(java_class.path, java_class.name, method.name, line),
    }


def context_transform(
    java_class: JavaClass,
    method: JavaMethod,
    api_id: str,
    body: str,
    transform_type: str,
    algorithm: str,
    input_role: str,
    output_role: str,
    deterministic: str,
    reversible: str,
    requires_secret: str,
    config_key: str,
    execution_impact: str,
    script_assertion_strategy: str,
) -> dict[str, Any]:
    return {
        "transform_id": "",
        "api_id": api_id,
        "scope": "PROJECT" if api_id == "PROJECT" else "API",
        "class_name": java_class.name,
        "method_name": method.name,
        "transform_type": transform_type,
        "algorithm": algorithm,
        "input_role": input_role,
        "output_role": output_role,
        "source_expression": UNKNOWN,
        "target_expression": UNKNOWN,
        "deterministic": deterministic,
        "reversible": reversible,
        "requires_secret": requires_secret,
        "config_key": config_key,
        "execution_impact": execution_impact,
        "script_assertion_strategy": script_assertion_strategy,
        "evidence": evidence(java_class.path, java_class.name, method.name, method.line),
    }


def first_argument(text: str, open_paren: int) -> str:
    if open_paren < 0 or open_paren >= len(text) or text[open_paren] != "(":
        return UNKNOWN
    args = arguments_text(text, open_paren)
    if not args:
        return UNKNOWN
    first = split_top_level_args(args)[0].strip()
    return first or UNKNOWN


def arguments_text(text: str, open_paren: int) -> str:
    depth = 0
    in_string: str | None = None
    escaped = False
    start = open_paren + 1
    for idx in range(open_paren, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in {"'", '"'}:
            in_string = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start:idx].strip()
    return ""


def split_top_level_args(text: str) -> list[str]:
    args: list[str] = []
    start = 0
    depth = 0
    angle_depth = 0
    in_string: str | None = None
    escaped = False
    for idx, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in {"'", '"'}:
            in_string = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(0, angle_depth - 1)
        elif char == "," and not depth and not angle_depth:
            args.append(text[start:idx])
            start = idx + 1
    args.append(text[start:])
    return args


def assignment_target(text: str, match_start: int) -> str:
    statement_start = max(text.rfind("\n", 0, match_start), text.rfind(";", 0, match_start)) + 1
    prefix = text[statement_start:match_start]
    match = re.search(r"(?:[\w<>\[\].?,]+\s+)?(?P<target>[A-Za-z_]\w*)\s*=\s*$", prefix.strip())
    return match.group("target") if match else UNKNOWN


def token_context(java_class: JavaClass, method: JavaMethod, body: str, offset: int) -> bool:
    window = body[max(0, offset - 120): offset + 160].lower()
    context = f"{java_class.name} {method.name} {window}".lower()
    return "token" in context or "jwt" in context or "usersig" in context


def assign_transform_ids(api_id: str, transforms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, int] = defaultdict(int)
    result: list[dict[str, Any]] = []
    for transform in transforms:
        transform_type = transform.get("transform_type", "SECURITY")
        grouped[transform_type] += 1
        prefix = "PROJECT-SEC" if api_id == "PROJECT" else sanitize_api_id(api_id)
        result.append(
            {
                **transform,
                "transform_id": f"{prefix}:{transform_type}:{grouped[transform_type]:03d}",
            }
        )
    return result


def sanitize_api_id(api_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:/-]+", "-", api_id)


def dedupe_transforms(transforms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in transforms:
        key = (
            item.get("scope", UNKNOWN),
            item.get("transform_type", UNKNOWN),
            item.get("algorithm", UNKNOWN),
            item.get("class_name", UNKNOWN),
            item.get("method_name", UNKNOWN),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def collect_secret_config_refs(files: list[SourceFile]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for source in files:
        if source.path.suffix not in {".yml", ".yaml", ".properties"}:
            continue
        current_path: list[str] = []
        for line_no, raw_line in enumerate(source.text.splitlines(), start=1):
            line = strip_inline_comment(raw_line).rstrip()
            if not line.strip():
                continue
            key_path = yaml_key_path(current_path, line)
            match = SECURITY_CONFIG_KEY_RE.search(line.strip())
            if not match:
                continue
            config_key = key_path or match.group("key")
            if not is_sensitive_config_key(config_key):
                continue
            refs.append(
                {
                    "config_key": config_key,
                    "secret_ref": f"config.{config_key}",
                    "sensitivity": sensitivity_of_key(config_key),
                    "value_visible": "YES" if match.group("value").strip() else "UNKNOWN",
                    "config_value_masked": mask_secret_value(match.group("value")),
                    "execution_impact": "该配置可能参与加密、签名、Token、外部凭证或数据库连接。",
                    "script_strategy": "执行脚本不应硬编码该值；需要由环境变量、测试配置或密钥管理系统注入。",
                    "evidence": f"{source.rel_path}:{line_no} | config.{config_key}",
                }
            )
    return dedupe_config_refs(refs)


def yaml_key_path(current_path: list[str], line: str) -> str:
    match = re.match(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_.-]+)\s*:", line)
    if not match:
        return ""
    indent = len(match.group("indent"))
    level = indent // 2
    key = match.group("key")
    if len(current_path) > level:
        current_path[:] = current_path[:level]
    if len(current_path) == level:
        current_path.append(key)
    else:
        current_path[:] = current_path[:level] + [key]
    return ".".join(current_path)


def sensitivity_of_key(config_key: str) -> str:
    lowered = config_key.lower()
    if any(token in lowered for token in ("secret", "password", "passwd", "pwd", "aes-key", "apikey", "api-secret")):
        return "HIGH"
    if any(token in lowered for token in ("token", "key")):
        return "MEDIUM"
    return "LOW"


def is_sensitive_config_key(config_key: str) -> bool:
    lowered = config_key.lower()
    non_secret_tokens = (
        "max-token",
        "max-tokens",
        "max_tokens",
        "token-limit",
        "token_limit",
        "tokens-per",
    )
    if any(token in lowered for token in non_secret_tokens):
        return False
    return any(
        token in lowered
        for token in (
            "secret",
            "password",
            "passwd",
            "pwd",
            "token",
            "access_token",
            "aes-key",
            "apikey",
            "api-secret",
            "api-secret-key",
            "secretkey",
            "secret-key",
        )
    )


def strip_inline_comment(raw_line: str) -> str:
    in_string: str | None = None
    escaped = False
    for idx, char in enumerate(raw_line):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in {"'", '"'}:
            in_string = char
            continue
        if char == "#" and (idx == 0 or raw_line[idx - 1].isspace()):
            return raw_line[:idx]
    return raw_line


def normalize_config_value(value: str) -> str:
    stripped = value.strip().strip("\"'")
    return stripped or UNKNOWN


def mask_secret_value(value: str) -> str:
    stripped = normalize_config_value(value)
    if stripped == UNKNOWN:
        return UNKNOWN
    if len(stripped) <= 8:
        return "*" * len(stripped)
    return stripped[:3] + "*" * (len(stripped) - 6) + stripped[-3:]


def dedupe_config_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for ref in refs:
        key = (ref.get("config_key", UNKNOWN), ref.get("evidence", UNKNOWN))
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result
