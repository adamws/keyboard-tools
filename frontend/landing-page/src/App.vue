<script setup>
</script>

<template>
  <div class="projects-container">
    <a href="https://editor.keyboard-tools.xyz" style="text-decoration: none; color: inherit;">
      <div class="project">
        <p class="project-name">Layout Editor</p>
      </div>
    </a>
    <a href="https://editor.keyboard-tools.xyz" style="text-decoration: none; color: inherit;">
      <div class="project">
        <p class="project-name">PCB Generator</p>
      </div>
    </a>
    <a href="https://github.com/adamws/kicad-kbplacer" style="text-decoration: none; color: inherit;">
      <div class="project">
        <p class="project-name">KiCad Plugin</p>
      </div>
    </a>
  </div>
</template>

<style scoped>
.projects-container {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
}
.project {
  border: 10px solid;
  border-color: #00ab91;
  width: 250px;
  height: 250px;
  margin: 20px;
  display: flex;
  justify-content: center;
  align-items: center;
}
.project:hover {
  border-color: black;
}
.project-name {
  color: black;
  font-size: 40px;
  text-align: left;
}
</style>
