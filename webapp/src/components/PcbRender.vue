<script setup>
import { computed, ref } from "vue";
import { Switch } from "@element-plus/icons-vue";

const props = defineProps({
  source: String,
});
const isHovered = ref(false);
const isFrontVisible = ref(true);
const toggleImages = () => {
  isFrontVisible.value = !isFrontVisible.value;
};
</script>

<template>
  <div
    class="render-container"
    v-if="source !== ''"
    @mouseover="isHovered = true"
    @mouseleave="isHovered = false">
    <img class="render" v-show="isFrontVisible" :src="source + '/front'" />
    <img class="render" v-show="!isFrontVisible" :src="source + '/back'" />
    <el-button
      type="warning"
      class="toggle-button"
      v-show="isHovered"
      @click="toggleImages"
      :icon="Switch"
      round>
      Switch side</el-button
    >
  </div>
</template>

<style scoped>
.render-container {
  position: relative;
  width: 100%;
  height: 100%;
}
.render {
  width: inherit;
}
.toggle-button {
  position: absolute;
  top: 0;
  right: 0;
  margin-right: 7px;
  margin-top: 7px;
}
</style>
