import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/", component: () => import("@/views/TeacherHomePage.vue") },
  {
    name: "group-detail",
    path: "/group/:id",
    props: true,
    component: () => import("@/views/GroupDetail.vue"),
  },
  {
    name: "subject-detail",
    path: "/subject/:id",
    props: true,
    component: () => import("@/views/SubjectDetail.vue"),
  },
  {
    name: "topic-detail",
    path: "/topic/:id",
    props: true,
    component: () => import("@/views/TopicDetail.vue"),
  },
  {
    name: "attempt-detail",
    path: "/attempt/:id",
    props: true,
    component: () => import("@/views/AttemptDetail.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;
