const INLINE_TAGS = new Set(["b", "strong", "i", "em", "u"]);

const escapeHtml = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");

const createContainer = () => {
  if (typeof document === "undefined") {
    return null;
  }
  return document.createElement("div");
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

const sanitizeNode = (node) => {
  if (node.nodeType === 3) {
    return escapeHtml(node.textContent || "");
  }
  if (node.nodeType !== 1) {
    return "";
  }

  const tag = node.tagName.toLowerCase();
  if (tag === "br") {
    return "<br>";
  }

  const content = Array.from(node.childNodes).map(sanitizeNode).join("");
  if (INLINE_TAGS.has(tag)) {
    return `<${tag}>${content}</${tag}>`;
  }
  if (tag === "span") {
    return normalizeSpanWithStyle(node, content);
  }
  return content;
};

export const sanitizeInlineRichText = (rawHtml) => {
  const container = createContainer();
  if (!container) {
    return String(rawHtml || "");
  }
  container.innerHTML = rawHtml || "";
  return Array.from(container.childNodes).map(sanitizeNode).join("").trim();
};

export const plainTextFromRichText = (rawHtml) => {
  const container = createContainer();
  if (!container) {
    return String(rawHtml || "").trim();
  }
  container.innerHTML = rawHtml || "";
  return (container.textContent || "").replace(/\u00a0/g, " ").trim();
};

const splitEditorHtmlToRawLines = (rawHtml) => {
  const container = createContainer();
  if (!container) {
    return [];
  }
  container.innerHTML = rawHtml || "";

  const blockTags = new Set(["DIV", "P", "LI"]);
  const hasBlockChildren = Array.from(container.children).some((child) =>
    blockTags.has(child.tagName),
  );

  const lines = [];
  if (!hasBlockChildren) {
    lines.push(container.innerHTML);
  } else {
    for (const childNode of container.childNodes) {
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
