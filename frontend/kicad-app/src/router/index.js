import { createWebHistory, createRouter } from "vue-router";
import KicadHandler from "@/components/KicadHandler.vue";
import KleConverter from "@/components/KleConverter.vue";
import Help from "@/components/Help.vue";
import About from "@/components/About.vue";

const routes = [
  {
    path: "/",
    component: KicadHandler,
  },
  {
    path: "/kle-converter",
    component: KleConverter,
  },
  {
    path: "/help",
    component: Help,
  },
  {
    path: "/about",
    component: About,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
