const PRIVATE_PREFIXES = ['attempt-draft:', 'question-draft:', 'import-undo:'];

export const clearPrivateStorage = () => {
  for (const storageName of ['localStorage', 'sessionStorage']) {
    try {
      const storage = window[storageName];
      for (const key of Object.keys(storage)) {
        if (PRIVATE_PREFIXES.some(prefix => key.startsWith(prefix))) storage.removeItem(key);
      }
    } catch { /* Storage may be disabled. */ }
  }
};

export const bindPrivateStorageUser = (userId) => {
  try {
    // Remove legacy persistent drafts; current drafts live only in this tab.
    for (const key of Object.keys(localStorage)) {
      if (PRIVATE_PREFIXES.some(prefix => key.startsWith(prefix))) localStorage.removeItem(key);
    }
    const previous = sessionStorage.getItem('private-storage-user');
    if (previous !== String(userId)) clearPrivateStorage();
    sessionStorage.setItem('private-storage-user', String(userId));
  } catch { /* Storage may be disabled. */ }
};
