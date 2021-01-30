<template>
  <div>
    <span>Switch library:</span>
    <span>
      <el-radio-group v-model="switchLibrary">
        <el-radio v-for="option in switchLibraryOptions" :label="option" :key="option">{{option}}</el-radio>
      </el-radio-group>
    </span>
  </div>
  <div>
    <span>Switch matrix routing:</span>
    <span>
      <el-radio-group v-model="routingOption">
        <el-radio v-for="option in routingOptions" :label="option" :key="option">{{option}}</el-radio>
      </el-radio-group>
    </span>
  </div>
</template>

<script>
export default {
  name: 'PcbSettings',
  data() {
    return {
      switchLibraryOptions: ["ai03-2725/MX_Alps_Hybrid", "perigoso/Switch_Keyboard"],
      routingOptions: ["Disabled", "Full"],

      switchLibrary: "perigoso/Switch_Keyboard",
      routingOption: "Disabled",
    }
  },
  emits: ["settings"],
  methods: {
    getSettings() {
      this.$emit("settings", {
        "switchLibrary": this.switchLibrary,
        "routing": this.routingOption,
        }
      );
    }
  }
};
</script>

<style scoped>
span {
  margin: 5px;
}
</style>
