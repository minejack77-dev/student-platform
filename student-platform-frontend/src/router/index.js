import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/", component: () => import("@/views/TeacherHomePage.vue") },
  {
    name: "group-detail",
    path: "/group/:id",
    props: true,
    component: () => import("@/views/GroupDetail.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;
