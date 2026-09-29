const INLINE_TAGS = new Set(["b", "strong", "i", "em", "u"]);
const SAFE_MEDIA_PROTOCOLS = new Set(["http:", "https:"]);
const DROP_TAGS = new Set(["script", "style", "svg", "math", "iframe", "object", "embed", "template"]);
const MAX_RICH_TEXT_LENGTH = 100000;
const boundedHtml = (value) => String(value || "").slice(0, MAX_RICH_TEXT_LENGTH);

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const createContainer = () => {
  if (typeof document === "undefined") {
    return null;
  }
  // Template contents are inert: parsing must never load media or fire events.
  return document.createElement("template");
};

const normalizeSpanWithStyle = (element, content) => {
  const styleValue = (element.getAttribute("style") || "").toLowerCase();
  let result = content;

  if (
    styleValue.includes("font-weight") &&
    (styleValue.includes("bold") || /font-weight:\s*(6|7|8|9)00/.test(styleValue))
  ) {
    result = `<strong>${result}</strong>`;
  }
  if (styleValue.includes("font-style: italic")) {
    result = `<em>${result}</em>`;
  }
  if (
    styleValue.includes("text-decoration") &&
    styleValue.includes("underline")
  ) {
    result = `<u>${result}</u>`;
  }
  return result;
};

const sanitizeMediaSrc = (rawSrc) => {
  const src = (rawSrc || "").trim();
  if (!src) {
    return "";
  }
  try {
    const parsed = new URL(src, window.location.origin);
    if (
      SAFE_MEDIA_PROTOCOLS.has(parsed.protocol) &&
      parsed.origin === window.location.origin &&
      !parsed.username && !parsed.password &&
      (parsed.pathname.startsWith("/media/") || parsed.pathname.startsWith("/static/"))
    ) {
      return parsed.href;
    }
  } catch (_error) {
    return "";
  }
  return "";
};

const sanitizeNode = (node, depth = 0) => {
  if (depth > 100) return "";
  if (node.nodeType === 3) {
    return escapeHtml(node.textContent || "");
  }
  if (node.nodeType !== 1) {
    return "";
  }

  const tag = node.tagName.toLowerCase();
  if (DROP_TAGS.has(tag)) return "";
  if (tag === "br") {
    return "<br>";
  }

  const content = Array.from(node.childNodes).map((child) => sanitizeNode(child, depth + 1)).join("");
  if (INLINE_TAGS.has(tag)) {
    return `<${tag}>${content}</${tag}>`;
  }
  if (tag === "span") {
    return normalizeSpanWithStyle(node, content);
  }
  if (tag === "img") {
    const src = sanitizeMediaSrc(node.getAttribute("src"));
    return src ? `<img src="${escapeHtml(src)}" alt="" loading="lazy">` : "";
  }
  if (tag === "audio") {
    const src = sanitizeMediaSrc(node.getAttribute("src"));
    return src ? `<audio controls preload="none" src="${escapeHtml(src)}"></audio>` : "";
  }
  return content;
};

export const sanitizeInlineRichText = (rawHtml) => {
  const container = createContainer();
  if (!container) {
    return escapeHtml(boundedHtml(rawHtml));
  }
  container.innerHTML = boundedHtml(rawHtml);
  return Array.from(container.content.childNodes).map((node) => sanitizeNode(node)).join("").trim();
};

export const plainTextFromRichText = (rawHtml) => {
  const container = createContainer();
  if (!container) {
    return boundedHtml(rawHtml).trim();
  }
  container.innerHTML = sanitizeInlineRichText(rawHtml);
  return (container.content.textContent || "").replace(/\u00a0/g, " ").trim();
};

const splitEditorHtmlToRawLines = (rawHtml) => {
  const container = createContainer();
  if (!container) {
    return [];
  }
  container.innerHTML = boundedHtml(rawHtml);

  const blockTags = new Set(["DIV", "P", "LI"]);
  const hasBlockChildren = Array.from(container.content.children).some((child) =>
    blockTags.has(child.tagName),
  );

  const lines = [];
  if (!hasBlockChildren) {
    lines.push(container.innerHTML);
  } else {
    for (const childNode of container.content.childNodes) {
      if (childNode.nodeType === 3) {
        if ((childNode.textContent || "").trim()) {
          lines.push(escapeHtml(childNode.textContent || ""));
        }
        continue;
      }
      if (childNode.nodeType !== 1) {
        continue;
      }

      if (blockTags.has(childNode.tagName)) {
        lines.push(childNode.innerHTML);
      } else if (childNode.tagName === "BR") {
        lines.push("");
      } else {
        lines.push(childNode.outerHTML);
      }
    }
  }

  const splitByBreaks = [];
  for (const line of lines) {
    splitByBreaks.push(...String(line).split(/<br\s*\/?>/gi));
  }
  return splitByBreaks;
};

export const extractRichTextLines = (rawHtml) =>
  splitEditorHtmlToRawLines(rawHtml)
    .map((line) => sanitizeInlineRichText(line))
    .filter((line) => plainTextFromRichText(line).length > 0);
