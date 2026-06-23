import axios from "axios";
import { createI18n } from "vue-i18n";

import en from "./messages/en";
import ru from "./messages/ru";

const LOCALE_STORAGE_KEY = "student-platform-locale";
const DEFAULT_LOCALE = "en";
const SUPPORTED_LOCALES = ["en", "ru"];

const normalizeLocale = (value) => {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized.startsWith("ru")) {
    return "ru";
  }
  return DEFAULT_LOCALE;
};

const getInitialLocale = () => {
  if (typeof window === "undefined") {
    return DEFAULT_LOCALE;
  }

  const storedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  if (storedLocale) {
    return normalizeLocale(storedLocale);
  }

  return normalizeLocale(
    window.navigator.language || document.documentElement.lang || DEFAULT_LOCALE,
  );
};

export const i18n = createI18n({
  legacy: false,
  locale: getInitialLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    en,
    ru,
  },
});

export const localeOptions = SUPPORTED_LOCALES;

export const setAppLocale = (value) => {
  const locale = normalizeLocale(value);
  i18n.global.locale.value = locale;

  if (typeof window !== "undefined") {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    document.documentElement.lang = locale;
    document.cookie = `django_language=${locale}; path=/; max-age=31536000; SameSite=Lax`;
  }

  axios.defaults.headers.common["Accept-Language"] = locale;
  return locale;
};

export const initializeLocale = () => {
  setAppLocale(i18n.global.locale.value);
};
