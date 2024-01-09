<script setup>
import { ref } from "vue";

const matrixOptions = ["Automatic", "Predefined"];
const switchFootprintOptions = ["MX", "Alps", "MX/Alps Hybrid"];
const routingOptions = ["Disabled", "Full"];
const controllerCircuitOptions = ["None", "ATmega32U4"];

const matrixOption = ref("Automatic");
const switchFootprint = ref("MX");
const routingOption = ref("Disabled");
const controllerCircuit = ref("None");

const getSettings = () => {
  return {
    matrixOption: matrixOption.value,
    switchLibrary: "kiswitch/keyswitch-kicad-library",
    switchFootprint: switchFootprint.value,
    routing: routingOption.value,
    controllerCircuit: controllerCircuit.value,
  };
};

defineExpose({ getSettings });
</script>

<template>
  <div class="settings">
    <span class="setting-name row1">Matrix:</span>
    <span v-for="option in matrixOptions" class="row1">
      <el-radio v-model="matrixOption" :label="option" :key="option">{{
        option
      }}</el-radio>
    </span>
    <span class="setting-name row2">Footprints:</span>
    <span v-for="option in switchFootprintOptions" class="row2">
      <el-radio v-model="switchFootprint" :label="option" :key="option">{{
        option
      }}</el-radio>
    </span>
    <span class="setting-name row3">Routing:</span>
    <span v-for="option in routingOptions" class="row3">
      <el-radio v-model="routingOption" :label="option" :key="option">{{
        option
      }}</el-radio>
    </span>
    <span class="setting-name row4">Controller circuit:</span>
    <span v-for="option in controllerCircuitOptions" class="row4">
      <el-radio v-model="controllerCircuit" :label="option" :key="option">
        {{ option }}
        <span v-if="option != 'None'" style="display: flex; color: #e6a23c">
          (experimental)</span
        >
      </el-radio>
    </span>
  </div>
</template>

<style scoped>
.settings {
  display: grid;
  max-width: 600px;
  grid-auto-columns: minmax(100px, auto);
  gap: 10px;
  align-items: center;
}
.setting-name {
  cursor: default;
}
.row1 {
  grid-row: 1;
}
.row2 {
  grid-row: 2;
}
.row3 {
  grid-row: 3;
}
.row4 {
  grid-row: 4;
}
</style>
