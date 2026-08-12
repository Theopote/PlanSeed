"""报告用 SVG 消毒：只保留平面图所需标签/属性，拒绝脚本与外部引用。

正式导出路径仍应只引用 ProjectStore 候选；本层为 print/srcDoc 纵深防御。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

# PlanSeed serializer 实际用到的 + 常见安全几何标签
_ALLOWED_TAGS = frozenset(
    {
        "svg",
        "g",
        "path",
        "rect",
        "line",
        "polyline",
        "polygon",
        "circle",
        "ellipse",
        "text",
        "tspan",
        "defs",
        "clippath",
        "clipPath",
        "title",
        "desc",
        "marker",
        "symbol",
        "use",  # 仅允许 fragment href，见下
        "lineargradient",
        "radialgradient",
        "stop",
        "pattern",
        "mask",
    }
)

_FORBIDDEN_TAGS = frozenset(
    {
        "script",
        "foreignobject",
        "foreignObject",
        "iframe",
        "object",
        "embed",
        "image",  # 外部图/内嵌均可成向量
        "a",
        "animate",
        "animatetransform",
        "animatemotion",
        "set",
        "handler",
        "listener",
        "style",  # 避免 CSS expression / 外部 @import
    }
)

# 允许的属性前缀/名（小写比较）
_ALLOWED_ATTR = frozenset(
    {
        "id",
        "class",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "dx",
        "dy",
        "width",
        "height",
        "viewbox",
        "xmlns",
        "fill",
        "fill-opacity",
        "fill-rule",
        "stroke",
        "stroke-width",
        "stroke-opacity",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-dasharray",
        "stroke-dashoffset",
        "opacity",
        "transform",
        "d",
        "points",
        "font-size",
        "font-family",
        "font-weight",
        "font-style",
        "text-anchor",
        "dominant-baseline",
        "letter-spacing",
        "clip-path",
        "clip-rule",
        "marker-start",
        "marker-mid",
        "marker-end",
        "gradientunits",
        "gradienttransform",
        "spreadmethod",
        "offset",
        "stop-color",
        "stop-opacity",
        "fx",
        "fy",
        "data-room-id",
        "data-floor-id",
        "overflow",
        "preserveaspectratio",
        "version",
    }
)

_HREF_ATTRS = frozenset({"href", "xlink:href", "{http://www.w3.org/1999/xlink}href"})

_JS_SCHEME = re.compile(r"javascript:", re.I)
_URL_SCHEME = re.compile(r"^\s*(https?:|data:|file:|//)", re.I)
_CSS_URL = re.compile(r"url\s*\(\s*['\"]?\s*([^'\")\s]*)['\"]?\s*\)", re.I)


def _local_tag(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag


def _attr_key(name: str) -> str:
    if name.startswith("{"):
        uri, local = name[1:].split("}", 1)
        if uri == "http://www.w3.org/1999/xlink" and local == "href":
            return "xlink:href"
        return local.lower()
    return name.lower()


def _safe_attr_value(value: str) -> bool:
    """Reject external url() paint servers and scheme-prefixed values."""
    if _URL_SCHEME.search(value):
        return False
    for match in _CSS_URL.finditer(value):
        inner = (match.group(1) or "").strip()
        if not inner.startswith("#"):
            return False
    return True


def _safe_href(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    if _JS_SCHEME.match(v) or _URL_SCHEME.match(v):
        return False
    # 仅允许同文档 fragment（如 #clip）
    return v.startswith("#")


def _sanitize_element(el: ET.Element) -> ET.Element | None:
    tag = _local_tag(el.tag)
    tag_l = tag.lower()
    if tag_l in {t.lower() for t in _FORBIDDEN_TAGS} or tag_l not in {
        t.lower() for t in _ALLOWED_TAGS
    }:
        return None

    # 规范标签名（去掉命名空间），保留 svg 根 xmlns
    out = ET.Element(tag)
    for raw_k, raw_v in el.attrib.items():
        key = _attr_key(raw_k)
        val = str(raw_v)
        if key.startswith("on"):
            continue
        if _JS_SCHEME.search(val):
            continue
        if key in _HREF_ATTRS or key.endswith(":href"):
            if not _safe_href(val):
                continue
            out.set("href", val)  # 统一为 href fragment
            continue
        if key.startswith("xmlns"):
            out.set(raw_k if raw_k.startswith("xmlns") else key, val)
            continue
        if key not in _ALLOWED_ATTR and not key.startswith("data-"):
            continue
        if key not in ("xmlns",) and not _safe_attr_value(val):
            continue
        out.set(key, val)

    if el.text and el.text.strip():
        out.text = el.text
    for child in list(el):
        cleaned = _sanitize_element(child)
        if cleaned is not None:
            out.append(cleaned)
            if child.tail and child.tail.strip():
                cleaned.tail = child.tail
    if el.tail and el.tail.strip() and out.tail is None:
        # tail 挂在父级子节点上处理
        pass
    return out


class SvgSanitizeError(ValueError):
    """SVG 无法解析或消毒后为空。"""


def sanitize_report_svg(raw: str) -> str:
    """
    返回可内嵌于报告 HTML 的 SVG 字符串。
    解析失败或消毒后无内容 → SvgSanitizeError（报告 fail loudly）。
    """
    text = (raw or "").strip()
    if not text:
        raise SvgSanitizeError("SVG 为空")
    from packages.schema.limits import API_LIMITS

    if len(text) > API_LIMITS.max_svg_chars:
        raise SvgSanitizeError("SVG 超过大小上限")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise SvgSanitizeError(f"SVG 解析失败：{exc}") from exc

    cleaned = _sanitize_element(root)
    if cleaned is None or _local_tag(cleaned.tag).lower() != "svg":
        raise SvgSanitizeError("SVG 根元素非法或被移除")

    # 确保 xmlns，便于独立预览/打印
    if "xmlns" not in cleaned.attrib:
        cleaned.set("xmlns", "http://www.w3.org/2000/svg")

    body = ET.tostring(cleaned, encoding="unicode")
    if not body.strip():
        raise SvgSanitizeError("SVG 消毒后为空")
    return body
