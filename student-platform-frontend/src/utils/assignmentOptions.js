const titleCollator = new Intl.Collator("ru", { numeric: true, sensitivity: "base" });

// Dropdowns need the entire collection, not just the first API page.
export async function loadAssignmentOptions(api, filters) {
  const items = [];
  let page = 1;
  while (true) {
    const response = await api.filter({ ...filters, ordering: "title,id", page_size: 200, page });
    items.push(...(response.results ?? response));
    if (!(response.links?.next ?? response.next)) break;
    page += 1;
  }
  return items.sort((a, b) => titleCollator.compare(a.title ?? "", b.title ?? "") || a.id - b.id);
}
