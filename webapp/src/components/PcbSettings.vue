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
    <el-col class="setting-name" :span="4">Library:</el-col>
    <el-col :span="20">
      <el-radio-group v-model="switchLibrary">
        <el-radio v-for="option in switchLibraryOptions" :label="option" :key="option">{{option}}</el-radio>
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
</template>

<script>
export default {
  name: 'PcbSettings',
  data() {
    return {
      matrixOptions: ["Automatic", "Predefined"],
      switchLibraryOptions: ["perigoso/Switch_Keyboard", "ai03-2725/MX_Alps_Hybrid"],
      switchFootprintOptions: ["MX", "Alps", "MX/Alps Hybrid"],
      routingOptions: ["Disabled", "Full"],

      matrixOption: "Automatic",
      switchLibrary: "perigoso/Switch_Keyboard",
      switchFootprint: "MX",
      routingOption: "Disabled",
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
        }
      );
    }
  }
};
</script>

<style scoped>
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
