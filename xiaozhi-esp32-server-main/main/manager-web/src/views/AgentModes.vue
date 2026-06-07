<template>
  <div class="welcome">
    <HeaderBar />
    <div class="operation-bar">
      <el-button size="small" icon="el-icon-arrow-left" @click="goBack">返回角色配置</el-button>
      <h2 class="page-title" style="display:inline-block;margin-left:16px">对话模式配置</h2>
    </div>
    <div class="main-wrapper">
      <div class="content-panel">
        <div class="content-area">
          <el-card shadow="never">
            <div style="margin-bottom:12px">
              <el-button type="primary" size="small" @click="openDialog(null)">+ 新增模式</el-button>
            </div>
            <el-table :data="modeList" size="small" style="width:100%" v-loading="loading">
              <el-table-column prop="modeName" label="模式名称" width="130"></el-table-column>
              <el-table-column prop="modeCode" label="语音代码" width="130"></el-table-column>
              <el-table-column label="默认" width="70">
                <template slot-scope="scope">
                  <el-tag v-if="scope.row.isDefault===1" type="success" size="mini">默认</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="sort" label="排序" width="70"></el-table-column>
              <el-table-column prop="systemPrompt" label="Prompt 预览" show-overflow-tooltip></el-table-column>
              <el-table-column label="操作" width="200">
                <template slot-scope="scope">
                  <el-button size="mini" @click="openDialog(scope.row)">编辑</el-button>
                  <el-button size="mini" type="success" :disabled="scope.row.isDefault===1" @click="setDefault(scope.row)">设默认</el-button>
                  <el-button size="mini" type="danger" @click="deleteMode(scope.row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </div>
    </div>

    <el-dialog :title="dialogTitle" :visible.sync="dialogVisible" width="600px">
      <el-form :model="form" label-width="90px" size="small">
        <el-form-item label="模式名称">
          <el-input v-model="form.modeName" placeholder="如：活泼模式" maxlength="50" />
        </el-form-item>
        <el-form-item label="语音代码">
          <el-input v-model="form.modeCode" placeholder="如：lively" maxlength="50" />
        </el-form-item>
        <el-form-item label="系统Prompt">
          <el-input type="textarea" v-model="form.systemPrompt" rows="8" maxlength="2000" show-word-limit placeholder="该模式下的系统提示词" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.isDefault" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" :max="99" />
        </el-form-item>
      </el-form>
      <span slot="footer">
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" @click="saveMode">保存</el-button>
      </span>
    </el-dialog>

    <el-footer><version-footer /></el-footer>
  </div>
</template>

<script>
import Api from "@/apis/api";
import HeaderBar from "@/components/HeaderBar.vue";
import VersionFooter from "@/components/VersionFooter.vue";

export default {
  components: { HeaderBar, VersionFooter },
  data() {
    return {
      agentId: null,
      modeList: [],
      loading: false,
      dialogVisible: false,
      dialogTitle: "新增模式",
      form: { id: null, modeName: "", modeCode: "", systemPrompt: "", isDefault: 0, sort: 0 },
    };
  },
  mounted() {
    this.agentId = this.$route.query.agentId;
    if (this.agentId) this.fetchModes();
  },
  methods: {
    goBack() {
      this.$router.push({ path: "/role-config", query: { agentId: this.agentId } });
    },
    fetchModes() {
      this.loading = true;
      Api.agent.getModeList(this.agentId, ({ data }) => {
        this.loading = false;
        if (data.code === 0) this.modeList = data.data || [];
      });
    },
    openDialog(row) {
      if (row) {
        this.dialogTitle = "编辑模式";
        this.form = { id: row.id, modeName: row.modeName, modeCode: row.modeCode, systemPrompt: row.systemPrompt, isDefault: row.isDefault || 0, sort: row.sort || 0 };
      } else {
        this.dialogTitle = "新增模式";
        this.form = { id: null, modeName: "", modeCode: "", systemPrompt: "", isDefault: 0, sort: 0 };
      }
      this.dialogVisible = true;
    },
    saveMode() {
      if (!this.form.modeName) { this.$message.warning("请输入模式名称"); return; }
      if (!this.form.modeCode) { this.$message.warning("请输入语音代码"); return; }
      if (this.form.id) {
        Api.agent.updateMode(this.agentId, this.form.id, this.form, ({ data }) => {
          if (data.code === 0) { this.$message.success("保存成功"); this.dialogVisible = false; this.fetchModes(); }
          else this.$message.error(data.msg || "保存失败");
        });
      } else {
        Api.agent.saveMode(this.agentId, this.form, ({ data }) => {
          if (data.code === 0) { this.$message.success("新增成功"); this.dialogVisible = false; this.fetchModes(); }
          else this.$message.error(data.msg || "新增失败");
        });
      }
    },
    setDefault(row) {
      Api.agent.setDefaultMode(this.agentId, row.id, ({ data }) => {
        if (data.code === 0) { this.$message.success("已设为默认模式"); this.fetchModes(); }
        else this.$message.error(data.msg || "操作失败");
      });
    },
    deleteMode(row) {
      this.$confirm("确定删除模式「" + row.modeName + "」吗？", "提示", { type: "warning" }).then(() => {
        Api.agent.deleteMode(this.agentId, row.id, ({ data }) => {
          if (data.code === 0) { this.$message.success("删除成功"); this.fetchModes(); }
          else this.$message.error(data.msg || "删除失败");
        });
      }).catch(() => {});
    },
  },
};
</script>

<style scoped>
.operation-bar {
  padding: 16px 24px;
  display: flex;
  align-items: center;
}
.page-title {
  margin: 0;
  font-size: 18px;
}
</style>
