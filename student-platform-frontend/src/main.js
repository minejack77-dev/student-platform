import { createApp } from "vue";
import "bootstrap";
import "bootstrap/dist/css/bootstrap.min.css";
import "./theme.css";

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

import App from "./App.vue";
import { i18n, initializeLocale } from "./i18n";
import router from "./router";
import { pinia } from "./stores";

import axios from "axios";

axios.defaults.xsrfHeaderName = "X-CSRFToken";
axios.defaults.xsrfCookieName = "csrftoken";
axios.defaults.withXSRFToken = true;
axios.defaults.withCredentials = true;
initializeLocale();

const app = createApp(App);

app.use(pinia);
app.use(i18n);
app.use(router);

app.mount("#app");
