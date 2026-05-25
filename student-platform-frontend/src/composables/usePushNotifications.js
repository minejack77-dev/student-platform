import axios from "axios";

const VAPID_PUBLIC_KEY = "BJ39jwrakF1hgrdNAVGYkbK1yEgBYfGY0p7XjEUxR_Um4xW0nsSaSPv2zy-nKqPzCHTGhWh11kKJqs244LqakMM=";

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

export async function subscribeToPush() {
  // Проверяем поддерживает ли браузере Service Worker или Push API
  if (!("serviceWorker" in navigator)) {
    throw new Error("serviceWorker not supported");
  }
  if (!("PushManager" in window)) {
    throw new Error("PushManager not supported");
  }
  if (!("Notification" in window)) {
    throw new Error("Notification not supported");
  }

  // Всплывающее окно разрешить уведомления
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Permission denied: " + permission);
  }

  // Ждем, когда SW станет активным
  const registration = await navigator.serviceWorker.ready;
  // Создаем подписку в браузере
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
  });

  // Отправляем подписку на бэкенд
  const sub = subscription.toJSON();
  await axios.post("/webpush/save_information", {
    status_type: "subscribe",
    subscription: sub,
    browser: navigator.userAgent.includes("Firefox") ? "firefox" : "chrome",
    group: "",
  });
}
