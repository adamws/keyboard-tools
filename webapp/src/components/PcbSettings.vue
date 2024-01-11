<script setup>
import { ref } from "vue";

const matrixOptions = ["Automatic", "Predefined"];
const switchFootprintOptions = ["MX", "Alps", "MX/Alps Hybrid", "Hotswap Kailh MX"];
const diodeFootprintOptions = ["SOD-123", "SOD-123F", "SOD-323", "SOD-323F"];
const routingOptions = ["Disabled", "Switch-Diode only", "Full"];
const controllerCircuitOptions = ["None", "ATmega32U4"];

const matrixOption = ref("Automatic");
const switchFootprint = ref("MX");
const diodeFootprint = ref("SOD-123");
const routingOption = ref("Disabled");
const controllerCircuit = ref("None");

const footprintsMapping = {
  "MX": "Switch_Keyboard_Cherry_MX:SW_Cherry_MX_PCB_{:.2f}u",
  "Alps": "Switch_Keyboard_Alps_Matias:SW_Alps_Matias_{:.2f}u",
  "MX/Alps Hybrid": "Switch_Keyboard_Hybrid:SW_Hybrid_Cherry_MX_Alps_{:.2f}u",
  "Hotswap Kailh MX": "Switch_Keyboard_Hotswap_Kailh:SW_Hotswap_Kailh_MX_{:.2f}u",
};

const getSettings = () => {
  return {
    matrixOption: matrixOption.value,
    switchFootprint: footprintsMapping[switchFootprint.value],
    diodeFootprint: "Diode_SMD:D_" + diodeFootprint.value,
    routing: routingOption.value,
    controllerCircuit: controllerCircuit.value,
  };
};

defineExpose({ getSettings });
</script>

<template>
  <div class="settings">
    <span class="setting-name row1">Switch Footprint:</span>
    <span v-for="option in switchFootprintOptions" class="row1">
      <el-radio v-model="switchFootprint" :label="option" :key="option">{{
        option
      }}</el-radio>
    </span>
    <span class="setting-name row2">Diode Footprint:</span>
    <span v-for="option in diodeFootprintOptions" class="row2">
      <el-radio v-model="diodeFootprint" :label="option" :key="option">{{
        option
      }}</el-radio>
    </span>
    <span class="setting-name row3">Matrix:</span>
    <span v-for="option in matrixOptions" class="row3">
      <el-radio v-model="matrixOption" :label="option" :key="option">{{
        option
      }}</el-radio>
    </span>
    <span class="setting-name row4">Routing:</span>
    <span v-for="option in routingOptions" class="row4">
      <el-radio v-model="routingOption" :label="option" :key="option">{{
        option
      }}</el-radio>
    </span>
    <span class="setting-name row5">Controller circuit:</span>
    <span v-for="option in controllerCircuitOptions" class="row5">
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
  grid-auto-columns: minmax(150px, auto);
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
.row5 {
  grid-row: 5;
}
</style>
