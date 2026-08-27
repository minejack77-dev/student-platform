import { precacheAndRoute, cleanupOutdatedCaches } from "workbox-precaching";
import { clientsClaim } from "workbox-core";

self.skipWaiting();
clientsClaim();
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// Получает уведомление
self.addEventListener("push", (event) => {
  const data = event.data?.json() ?? {};
  const title = data.head ?? "Учебный портал";
  const options = {
    body: data.body ?? "",
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Открывает сайт, когда студент кликает по уведомлению
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow("/"));
});
