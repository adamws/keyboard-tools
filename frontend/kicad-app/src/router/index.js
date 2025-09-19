import { createWebHistory, createRouter } from "vue-router";
import KicadHandler from "@/components/KicadHandler.vue";
import KleConverter from "@/components/KleConverter.vue";
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
    path: "/about",
    component: About,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
