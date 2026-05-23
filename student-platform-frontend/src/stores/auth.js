import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { Auth } from "@/api.js";
import { subscribeToPush } from "@/composables/usePushNotifications.js";

export const useAuthStore = defineStore("auth", () => {
  const user = ref(null);
  const initialized = ref(false);
  const loading = ref(false);

  const isAuthenticated = computed(() => Boolean(user.value));
  const role = computed(() => user.value?.role ?? null);

  const clearUser = () => {
    user.value = null;
  };

  const setUser = (payload) => {
    user.value = payload;
  };

  const fetchMe = async () => {
    try {
      const payload = await Auth.me();
      setUser(payload);
      return payload;
    } catch (error) {
      const status = error?.response?.status;
      if (status === 401 || status === 403) {
        clearUser();
        return null;
      }
      throw error;
    } finally {
      initialized.value = true;
    }
  };

  const initialize = async () => {
    if (initialized.value || loading.value) {
      return user.value;
    }

    loading.value = true;
    try {
      return await fetchMe();
    } finally {
      loading.value = false;
    }
  };

  const login = async (credentials) => {
    await Auth.fetchCsrf(); // Получаем CSRF токен с бэка
    const payload = await Auth.login(credentials); // Авторизуем пользователя
    setUser(payload); // Сохраняем пользователя внутри store
    initialized.value = true;
    if (payload?.role === "student") {
      subscribeToPush().catch(() => {});
    }
    return payload;
  };

  const logout = async () => {
    await Auth.fetchCsrf();
    try {
      await Auth.logout();
      clearUser();
      initialized.value = true;
      return true;
    } catch (error) {
      await fetchMe();
      if (!user.value) {
        return true;
      }
      throw error;
    }
  };

  return {
    user,
    role,
    loading,
    initialized,
    isAuthenticated,
    initialize,
    fetchMe,
    login,
    logout,
  };
});
