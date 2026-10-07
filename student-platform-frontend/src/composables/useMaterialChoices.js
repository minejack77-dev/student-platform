// Fetch every page for selectors; never silently hide options after page 1.
export async function allMaterialChoices(api, filters = {}) {
  const items = [];
  let page = 1;
  while (true) {
    const response = await api.filter({ ...filters, page, page_size: 200 });
    items.push(...(response.results ?? response));
    if (!response.links?.next) return items;
    page += 1;
  }
}
