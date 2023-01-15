<template>
  <el-row>
    <el-col class="setting-name" :span="4">Matrix:</el-col>
    <el-col :span="20">
      <el-radio-group v-model="matrixOption">
        <el-radio v-for="option in matrixOptions" :label="option" :key="option">{{option}}</el-radio>
      </el-radio-group>
    </el-col>
  </el-row>
  <el-row>
    <el-col class="setting-name" :span="4">Footprints:</el-col>
    <el-col :span="20">
      <el-radio-group v-model="switchFootprint">
        <el-radio v-for="option in switchFootprintOptions" :label="option" :key="option">{{option}}</el-radio>
      </el-radio-group>
    </el-col>
  </el-row>
  <el-row>
    <el-col class="setting-name" :span="4">Routing:</el-col>
    <el-col :span="20">
      <el-radio-group v-model="routingOption">
        <el-radio v-for="option in routingOptions" :label="option" :key="option">{{option}}</el-radio>
      </el-radio-group>
    </el-col>
  </el-row>
  <el-row>
    <el-col class="setting-name" :span="4">Controller circuit:</el-col>
    <el-col :span="20">
      <el-radio-group v-model="controllerCircuit">
        <el-radio v-for="option in controllerCircuitOptions" :label="option" :key="option">{{option}}</el-radio>
      </el-radio-group>
      <span style="color:#E6A23C;"> (experimental)</span>
    </el-col>
  </el-row>
</template>

<script>
export default {
  name: 'PcbSettings',
  data() {
    return {
      matrixOptions: ["Automatic", "Predefined"],
      switchFootprintOptions: ["MX", "Alps", "MX/Alps Hybrid"],
      routingOptions: ["Disabled", "Full"],
      controllerCircuitOptions: ["None", "ATmega32U4"],

      matrixOption: "Automatic",
      switchLibrary: "perigoso/keyswitch-kicad-library",
      switchFootprint: "MX",
      routingOption: "Disabled",
      controllerCircuit: "None",
    }
  },
  emits: ["settings"],
  methods: {
    getSettings() {
      this.$emit("settings", {
        "matrixOption": this.matrixOption,
        "switchLibrary": this.switchLibrary,
        "switchFootprint": this.switchFootprint,
        "routing": this.routingOption,
        "controllerCircuit": this.controllerCircuit,
        }
      );
    }
  }
};
</script>

<style scoped>

@media screen and (max-width: 800px) {
  .el-row {
    flex-direction: column;
  }
}

.el-row {
  margin-bottom: 4px;
}
.el-col {
  border-radius: 4px;
}
.setting-name {
  cursor: default;
}

</style>
