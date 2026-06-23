import { computed } from "vue";
import { useI18n } from "vue-i18n";

export const useLocaleFormatting = () => {
  const { locale } = useI18n();

  const localeTag = computed(() => (locale.value === "ru" ? "ru-RU" : "en-US"));

  const formatWithLocale = (date, options) => {
    if (!date) {
      return "";
    }
    return new Intl.DateTimeFormat(localeTag.value, options).format(date);
  };

  const createCollator = (options) => new Intl.Collator(localeTag.value, options);

  return {
    locale,
    localeTag,
    formatWithLocale,
    createCollator,
  };
};
