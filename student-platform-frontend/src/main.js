import { createApp } from "vue";
import "bootstrap";
import "bootstrap/dist/css/bootstrap.min.css";
import "./theme.css";
import { registerSW } from "virtual:pwa-register";

registerSW({
  immediate: true,
});

import App from "./App.vue";
import router from "./router";
import { pinia } from "./stores";

import axios from "axios";

axios.defaults.xsrfHeaderName = "X-CSRFToken";
axios.defaults.xsrfCookieName = "csrftoken";
axios.defaults.withXSRFToken = true;
axios.defaults.withCredentials = true;

const app = createApp(App);

app.use(pinia);
app.use(router);

app.mount("#app");
