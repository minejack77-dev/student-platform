import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { pinia } from "@/stores";

const routes = [
  {
    name: "login",
    path: "/login",
    component: () => import("@/views/LoginPage.vue"),
    meta: { guestOnly: true },
  },
  {
    name: "teacher-home",
    path: "/",
    component: () => import("@/views/TeacherHomePage.vue"),
    meta: { requiresAuth: true, roles: ["teacher"] }, // Дополнительная информация о маршруте
  },
  {
    name: "student-home",
    path: "/student",
    component: () => import("@/views/StudentHomePage.vue"),
    meta: { requiresAuth: true, roles: ["student"] },
  },
  {
    path: "/group/:id",
    redirect: (to) => ({ name: "group-overview", params: { id: to.params.id } }),
  },
  {
    name: "group-overview",
    path: "/group/:id/overview",
    props: true,
    component: () => import("@/views/GroupOverview.vue"),
    meta: { requiresAuth: true, roles: ["teacher"] },
  },
  {
    name: "group-details",
    path: "/group/:id/details",
    props: true,
    component: () => import("@/views/GroupDetails.vue"),
    meta: { requiresAuth: true, roles: ["teacher"] },
  },
  {
    name: "subject-detail",
    path: "/subject/:id",
    props: true,
    component: () => import("@/views/SubjectDetail.vue"),
    meta: { requiresAuth: true, roles: ["teacher"] },
  },
  {
    name: "topic-detail",
    path: "/topic/:id",
    props: true,
    component: () => import("@/views/TopicDetail.vue"),
    meta: { requiresAuth: true, roles: ["teacher"] },
  },
  {
    name: "attempt-detail",
    path: "/attempt/:id",
    props: true,
    component: () => import("@/views/AttemptDetail.vue"),
    meta: { requiresAuth: true, roles: ["student"] },
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

const defaultRouteByRole = (role) => {
  if (role === "student") {
    return { name: "student-home" };
  }
  return { name: "teacher-home" };
};

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia);
  await authStore.initialize(); // Пробуем понять есть ли у пользователся активная сессия

  if (to.meta.guestOnly && authStore.isAuthenticated) { // Для авторизованных пользователей не нужно показывать страницу входа
    return defaultRouteByRole(authStore.role); // Отправляем на гланую страницу пользователя
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) { // Правило для защищенных страниц
    return {
      name: "login",
      query: { redirect: to.fullPath },
    };
  }

  const allowedRoles = to.meta.roles;
  if (allowedRoles?.length && !allowedRoles.includes(authStore.role)) { // Ограничение маршрута по ролям
    return defaultRouteByRole(authStore.role);
  }

  return true;
});

export default router;
