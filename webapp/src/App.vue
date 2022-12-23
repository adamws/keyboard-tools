<template>
  <div id="app">
    <el-container>
      <el-header style="height: 80px;">
        <div><img :src="logo" height="60"/></div><div>Keyboard tools</div>
      </el-header>
      <el-main>
        <el-menu :default-active="$route.path" :router="true" mode="horizontal">
          <el-menu-item index="/" route="/">KiCad Project Generator</el-menu-item>
          <el-menu-item index="/kle-converter" route="/kle-converter">KLE converter</el-menu-item>
          <el-menu-item index="/help" route="/help">Help</el-menu-item>
          <el-menu-item index="/about" route="/about">About</el-menu-item>
        </el-menu>
        <br>
        <router-view />
      </el-main>
      <el-footer>
          <div><a href="https://github.com/adamws/keyboard-tools"><img :src="githubIcon"/></a></div>
      </el-footer>
    </el-container>
  </div>
</template>

<script>
import logo from './assets/logo.png'
import githubIcon from './assets/GitHub-Mark-32px.png'
export default {
  name: 'App',
  data() {
    return {
      logo: logo,
      githubIcon: githubIcon,
    };
  },
};
</script>

<style>
body {
  margin-top: 2%;
  padding-right: 5%;
  padding-left: 5%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

@media screen and (min-width: 800px) {
  body {
    padding-right: 5%;
    padding-left: 5%;
  }

}

@media screen and (min-width: 1600px) {
  body {
    padding-right: 10%;
    padding-left: 10%;
  }
}

@media screen and (max-width: 800px) {
  .el-menu--horizontal > .el-menu-item {
    height: 30px;
    line-height: 30px;
  }
}

code {
  font-family: source-code-pro, Menlo, Monaco, Consolas, "Courier New",
    monospace;
  background-color: #b3e6ff;
}


.el-header, .el-footer {
  text-align: center;
}

a {
  text-decoration: none;
}

</style>
