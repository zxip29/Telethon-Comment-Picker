/**
 * Client-side comment filters (applied only when checkboxes are enabled).
 */

export function dedupKey(comment) {
  if (comment.user_id != null) {
    return `id:${comment.user_id}`;
  }
  if (comment.username) {
    return `u:${comment.username.toLowerCase().replace(/^@/, "")}`;
  }
  return `d:${comment.display}`;
}

export function applyFilters(comments, options) {
  const { removeDuplicates, hideMedia, textOnly } = options;
  let list = [...comments];

  if (hideMedia) {
    list = list.filter((c) => !c.has_media);
  }

  if (textOnly) {
    list = list.filter((c) => c.has_text);
  }

  if (removeDuplicates) {
    const seen = new Set();
    list = list.filter((c) => {
      const key = dedupKey(c);
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

  return list;
}

export function escapeQuotes(text) {
  return String(text || "")
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"');
}

export function formatCommentLine(index, display, text) {
  return `no.${index} ${display} - "${escapeQuotes(text)}"`;
}

export function formatComments(comments) {
  return comments.map((c, i) =>
    formatCommentLine(i + 1, c.display, c.text)
  );
}

export function joinFormatted(lines) {
  return lines.join("\n");
}
