import { i18n } from '@/i18n';

export function apiError(error, fallback = 'ux.serverError') {
  const { t } = i18n.global;
  if (!error?.response) return t('ux.networkError');
  const data = error.response.data || {};
  const details = JSON.stringify(data);
  if (/A test with this title already exists/.test(details)) return t('materialsFlow.duplicateTitle');
  if (/Choose today or a future date/.test(details)) return t('materialsFlow.futureDate');
  if (/default folder is inactive|default topic is inactive|Choose an active topic/.test(details)) return t('materialsFlow.inactiveTopic');
  const keys = { task_not_ready: 'taskNotReady', attempt_closed: 'attemptClosed',
    incomplete_submission: 'incompleteSubmission', invalid_file: 'invalidFile',
    protected_import: 'protectedImport', confirm_unanswered: 'incompleteSubmission' };
  if (keys[data.code]) return t(`ux.${keys[data.code]}`, data);
  if (/already has student attempts|already have student attempts/.test(details)) return t('ux.protectedSchedule');
  if (fallback === 'ux.loginError' && [400, 401, 403].includes(error.response.status)) return t('ux.loginError');
  if (error.response.status === 403) return t('ux.accessDenied');
  if (data.detail === 'Invalid username or password.') return t('ux.loginError');
  // Never expose raw exceptions or server debug pages to the user.
  return t(fallback);
}
