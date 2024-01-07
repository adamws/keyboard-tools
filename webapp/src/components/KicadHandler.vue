<script setup>
import { computed, h, reactive, ref } from "vue";
import { ElMessageBox } from "element-plus";
import { UploadFilled } from "@element-plus/icons-vue";
import axios from "axios";
import PcbRender from "@/components/PcbRender.vue";
import PcbSettings from "@/components/PcbSettings.vue";
import * as kle from "@ijprest/kle-serial";

const apiEndpoint = `${import.meta.env.VITE_WORKER_URL}/api/pcb`;

const state = reactive({
  taskId: "",
  taskStatus: "",
  polling: null,
  progressBarStatus: "",
  progressBarPercentage: 0,
  svgSource: "",
});

const pcbSettingsRef = ref(null);
const loadingCfg = computed(() => {
  if (state.polling !== null) {
    if (state.taskStatus === "PENDING") {
      return { text: "Waiting for worker..." };
    }
    if (state.taskStatus === "PROGRESS") {
      return { text: "Building..." };
    }
    return { text: " " };
  }
  return false;
});

function showFailAlert(message) {
  setProgressBarFailState();
  ElMessageBox.alert(message, {
    confirmButtonText: "OK",
    type: "error",
  });
}

function showTaskStatusFailAlert(message) {
  let stackTrace = message.exc_message
    .split("\n")
    .map((line) => h("p", { style: "line-height: normal" }, line.trim()));
  message = h("p", null, [
    h(
      "span",
      { style: "color: var(--el-color-error); font-weight: bold" },
      "An unexpected error occurred. "
    ),
    h(
      "span",
      null,
      "Please try again. If the error persists, you can submit the issue with the following details at "
    ),
    h(
      "a",
      { href: "https://github.com/adamws/keyboard-tools/issues/new" },
      "GitHub"
    ),
    h("span", null, ":"),
    h(
      "p",
      {
        style: "margin-top: 10px; font-family: monospace; font-size: small",
      },
      stackTrace
    ),
  ]);
  showFailAlert(message);
}

function triggerUpload() {
  state.taskStatus = "";
  state.progressBarStatus = "";
  state.progressBarPercentage = 0;
  state.svgSource = "";
  document.getElementById("file").click();
}

function setProgressBarFailState() {
  state.progressBarPercentage = 100;
  state.progressBarStatus = "exception";
}

function getTaskStatus() {
  axios
    .get(`${apiEndpoint}/${state.taskId}`)
    .then((res) => {
      state.taskStatus = res.data.task_status;
      state.progressBarPercentage = res.data.task_result.percentage;
      if (state.taskStatus !== "PENDING" && state.taskStatus !== "PROGRESS") {
        if (state.taskStatus === "SUCCESS") {
          state.svgSource = `${apiEndpoint}/${state.taskId}/render`;
        } else {
          showTaskStatusFailAlert(res.data.task_result);
        }
        clearInterval(state.polling);
        state.polling = null;
      }
    })
    .catch(() => {
      showFailAlert("Unexpected exception when fetching task status");
      clearInterval(state.polling);
      state.polling = null;
    });
}

function getResultUrl() {
  return `${apiEndpoint}/${state.taskId}/result`;
}

function uploadLayout() {
  let file = document.getElementById("file").files[0];

  let reader = new FileReader();
  reader.readAsText(file, "UTF-8");
  reader.onload = (evt) => {
    if (file.type !== "application/json") {
      showFailAlert("Unsupported file type");
      return;
    }

    let keyboard;
    try {
      const result = evt.target.result;
      keyboard = kle.Serial.deserialize(JSON.parse(result));
    } catch (error) {
      showFailAlert(error.toString());
      return;
    }

    if (keyboard.keys.length > 150) {
      let message = h("p", null, [
        h(
          "p",
          { style: "color: var(--el-color-error); font-weight: bold" },
          "Layouts exceeding 150 keys not supported."
        ),
        h(
          "p",
          null,
          "Sorry, we are unable to process your request. This keyboard is too big and could overload our server."
        ),
      ]);
      showFailAlert(message);
      return;
    }

    let settings = pcbSettingsRef.value.getSettings();

    axios
      .post(`${apiEndpoint}`, { layout: keyboard, settings: settings })
      .then((res) => {
        if (res.status === 202) {
          state.taskId = res.data.task_id;

          state.polling = setInterval(() => {
            getTaskStatus();
          }, 1000);
        } else {
          showFailAlert("Request rejected");
        }
      })
      .catch((error) => {
        if (error.response) {
          const data = error.response.data;
          if (data.error) {
            showFailAlert(data.error);
          } else {
            showFailAlert("Unexpected error");
          }
        } else {
          showFailAlert("Unexpected error");
        }
      });
  };
  reader.onerror = (evt) => {
    console.error(evt);
  };
}
</script>

<template>
  <div v-loading="loadingCfg">
    <div>
      Generate KiCad project with layout from
      <a href="http://www.keyboard-layout-editor.com">keyboard-layout-editor</a
      >:
    </div>
    <br />
    <PcbSettings ref="pcbSettingsRef" />
    <br />
    <div>
      <span>
        <el-button type="primary" @click="triggerUpload" :icon="UploadFilled">
          Upload layout
        </el-button>
        <input
          type="file"
          id="file"
          accept=".json"
          v-on:change="uploadLayout"
          style="display: none" />
      </span>
      <span>
        Looking for inspiration? Check out
        <a href="https://adamws.github.io/keyboard-pcbs/">layout gallery</a>.
      </span>
    </div>
  </div>
  <div style="margin-top: 15px">
    <div>
      <el-progress
        :stroke-width="6"
        :percentage="state.progressBarPercentage"
        :status="state.progressBarStatus"
        :color="'#409eff'"
        v-if="state.taskId !== ''"></el-progress>
    </div>
    <br />
    <div>
      <PcbRender :source="state.svgSource" />
      <a
        id="download"
        v-bind:href="getResultUrl()"
        v-if="state.taskStatus === 'SUCCESS'">
        <el-button id="download-btn" type="success">Download project</el-button>
      </a>
    </div>
  </div>
</template>

<style scoped></style>
