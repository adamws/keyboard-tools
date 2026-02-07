<script setup>
</script>

<template>
  <div class="projects-container">
    <a href="https://editor.keyboard-tools.xyz">
      <div class="project size-2u">
        <p class="project-name">Layout Editor with Plate and PCB generators</p>
      </div>
    </a>
    <a href="https://github.com/adamws/kicad-kbplacer">
      <div class="project size-1u">
        <p class="project-name">KiCad Plugin</p>
      </div>
    </a>
  </div>
</template>

<style scoped>
.projects-container {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
}
.projects-container > a {
  text-decoration: none;
  color: inherit;
}
.project {
  border: 10px solid;
  border-color: #00ab91;
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
.size-1u {
  width: 250px;
  height: 250px;
}
.size-2u {
  width: 500px;
  height: 250px;
}
@media (max-width: 624px) {
  .size-2u {
    width: 250px;
    height: 500px;
  }
}
</style>
