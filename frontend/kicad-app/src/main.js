import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/theme-chalk/index.css";
import "./style.css";
import App from "./App.vue";
import router from "./router";

const app = createApp(App);
app.use(ElementPlus);
app.use(router);
app.mount("#app");
