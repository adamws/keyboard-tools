<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import logo from "./assets/logo.png";
import githubIcon from "./assets/github-mark.svg";
import { Menu } from "@element-plus/icons-vue";

const logoSrc = ref(logo);
const githubIconSrc = ref(githubIcon);
const version = ref(__APP_VERSION__);
const menuIcon = Menu;
const isMenuCollapsed = ref(false);

const githubLink = ref("https://github.com/adamws/keyboard-tools");

const handleWindowResize = () => {
  isMenuCollapsed.value = window.innerWidth < 800;
};

onMounted(() => {
  handleWindowResize();
  window.addEventListener("resize", handleWindowResize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleWindowResize);
});
</script>

<template>
  <div id="app">
    <el-container>
      <el-header>
        <el-menu
          :default-active="$route.path"
          :router="true"
          :ellipsis="isMenuCollapsed"
          :ellipsis-icon="menuIcon"
          mode="horizontal">
          <div class="logo"><img :src="logo" height="40" alt="Logo" /></div>
          <div v-if="isMenuCollapsed" class="flex-grow" />
          <el-menu-item index="/" route="/"
            >KiCad Project Generator</el-menu-item
          >
          <el-menu-item index="/kle-converter" route="/kle-converter"
            >KLE converter</el-menu-item
          >
          <el-menu-item index="/about" route="/about">About</el-menu-item>
          <div v-if="!isMenuCollapsed" class="flex-grow" />
          <el-menu-item>
            <el-link href="/help" :underline="false" target="_blank">
              Docs
            </el-link>
          </el-menu-item>
          <el-menu-item>
            <el-link :href="githubLink" :underline="false" target="_blank">
              Visit on GitHub
              <img
                :src="githubIconSrc"
                height="18"
                alt="Github"
                style="padding-left: 5px" />
            </el-link>
          </el-menu-item>
          <el-menu-item class="version" disabled> v{{ version }} </el-menu-item>
        </el-menu>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<style>
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen",
    "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue",
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

code {
  font-family: source-code-pro, Menlo, Monaco, Consolas, "Courier New",
    monospace;
  background-color: #b3e6ff;
}

.el-header {
  text-align: center;
}

.version {
  cursor: default !important;
  opacity: 1 !important;
}

.el-message-box {
  max-width: fit-content;
  margin-right: 5%;
  margin-left: 5%;
}

.el-menu:not(.el-menu--collapse) .el-sub-menu__title {
  padding-right: var(--el-menu-base-level-padding) !important;
}

.logo {
  margin-right: 20px;
}

#app {
  height: 100%;
  min-width: 320px;
  max-width: 1920px;
  margin: auto;
}

a {
  text-decoration: none;
}

.flex-grow {
  flex-grow: 1;
}
</style>
