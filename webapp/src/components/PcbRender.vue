<script setup>
import { ref, defineProps, watch } from "vue";
import { Minus, Plus, Switch } from "@element-plus/icons-vue";

const props = defineProps({
  source: String,
});

const isHovered = ref(false);
const isFrontVisible = ref(true);
const scale = ref(1);
const isDragging = ref(false);
const lastMouseX = ref(0);
const lastMouseY = ref(0);
const imagePositionX = ref(0);
const imagePositionY = ref(0);

const toggleImages = () => {
  isFrontVisible.value = !isFrontVisible.value;
};

const handleZoomIn = () => {
  scale.value = Math.min(scale.value + 0.25, 5);
};

const handleZoomOut = () => {
  scale.value = Math.max(scale.value - 0.25, 0.5);
};

const handleMouseDown = (event) => {
  // Left Click
  if (event.button === 0) {
    isDragging.value = true;
    lastMouseX.value = event.clientX;
    lastMouseY.value = event.clientY;
    event.preventDefault(); // Prevent default browser behavior
  }
};

const handleMouseMove = (event) => {
  if (isDragging.value) {
    const deltaX = event.clientX - lastMouseX.value;
    const deltaY = event.clientY - lastMouseY.value;

    // Adjust the image position based on the mouse movement
    imagePositionX.value += deltaX / scale.value;
    imagePositionY.value += deltaY / scale.value;

    // Update the last mouse position
    lastMouseX.value = event.clientX;
    lastMouseY.value = event.clientY;
  }
};

const handleMouseUp = () => {
  isDragging.value = false;
};

const handleMouseLeave = () => {
  isDragging.value = false;
  isHovered.value = false;
};

const resetZoomAndPosition = () => {
  scale.value = 1;
  imagePositionX.value = 0;
  imagePositionY.value = 0;
};

watch(
  () => props.source,
  (newSource, oldSource) => {
    if (newSource === "") {
      resetZoomAndPosition();
    }
  },
);
</script>

<template>
  <div
    class="render-container"
    v-if="source !== ''"
    @mouseover="isHovered = true"
    @mouseleave="handleMouseLeave"
    @mousedown="handleMouseDown"
    @mousemove="handleMouseMove"
    @mouseup="handleMouseUp"
    style="overflow: hidden; cursor: grab">
    <div
      class="image-container"
      :style="{
        transform: `scale(${scale}) translate(${imagePositionX}px, ${imagePositionY}px)`,
      }">
      <img class="render" v-show="isFrontVisible" :src="source + '/front'" />
      <img class="render" v-show="!isFrontVisible" :src="source + '/back'" />
    </div>
    <el-button
      class="zoom-in-button"
      v-show="isHovered"
      @click="handleZoomIn"
      :icon="Plus"
      circle>
    </el-button>
    <el-button
      class="zoom-out-button"
      v-show="isHovered"
      @click="handleZoomOut"
      :icon="Minus"
      circle>
    </el-button>
    <el-button
      type="warning"
      class="toggle-button"
      v-show="isHovered"
      @click="toggleImages"
      :icon="Switch"
      round>
      Switch side
    </el-button>
    <el-button
      type="info"
      class="reset-button"
      v-show="isHovered"
      @click="resetZoomAndPosition"
      round>
      Reset
    </el-button>
  </div>
</template>

<style scoped>
.render-container {
  position: relative;
  width: 100%;
  height: 100%;
}
.image-container {
  transition: transform 0.2s ease;
  max-width: 100%;
  max-height: 100%;
}
.render {
  width: 100%;
}
.toggle-button,
.reset-button {
  position: absolute;
  top: 0;
  right: 0;
}
.toggle-button {
  margin-top: 7px;
  margin-right: 7px;
}
.reset-button {
  margin-top: 42px;
  margin-right: 7px;
}
.zoom-in-button,
.zoom-out-button {
  position: absolute;
  top: 0;
  left: 0;
}
.zoom-in-button {
  margin-top: 7px;
  margin-left: 7px;
}
.zoom-out-button {
  margin-top: 42px;
  margin-left: 7px;
}
</style>
