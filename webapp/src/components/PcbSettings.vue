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
  <el-row>
    <el-col class="setting-name" :span="4">Matrix:</el-col>
    <el-col v-for="option in matrixOptions" :span="3">
      <el-radio v-model="matrixOption" :label="option" :key="option">{{
        option
      }}</el-radio>
    </el-col>
  </el-row>
  <el-row>
    <el-col class="setting-name" :span="4">Footprints:</el-col>
    <el-col v-for="option in switchFootprintOptions" :span="3">
      <el-radio v-model="switchFootprint" :label="option" :key="option">{{
        option
      }}</el-radio>
    </el-col>
  </el-row>
  <el-row>
    <el-col class="setting-name" :span="4">Routing:</el-col>
    <el-col v-for="option in routingOptions" :span="3">
      <el-radio v-model="routingOption" :label="option" :key="option">{{
        option
      }}</el-radio>
    </el-col>
  </el-row>
  <el-row>
    <el-col class="setting-name" :span="4">Controller circuit:</el-col>
    <el-col v-for="option in controllerCircuitOptions" :span="3">
      <el-radio v-model="controllerCircuit" :label="option" :key="option">
        {{ option }}
        <span v-if="option != 'None'" style="color: #e6a23c">
          (experimental)</span
        >
      </el-radio>
    </el-col>
  </el-row>
</template>

<style scoped>
@media screen and (max-width: 800px) {
  .el-row {
    flex-direction: column;
  }
}
.el-row {
  align-items: center;
  margin-bottom: 4px;
}
.el-col {
  border-radius: 4px;
}
.setting-name {
  cursor: default;
}
</style>
