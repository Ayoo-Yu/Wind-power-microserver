<template>
  <div class="report-management">
    <!-- 动态渐变背景 -->
    <div class="gradient-background"></div>
    
    <!-- 页面标题 -->
    <div class="page-title">
      <p>数据上报配置与管理</p>
    </div>

    <!-- 调度器状态卡片 -->
    <el-card class="info-card scheduler-status-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="el-icon-timer"></i> 自动上报调度器</span>
          <div class="scheduler-controls">
            <el-tag :type="schedulerStatus.running ? 'success' : 'danger'" size="small">
              {{ schedulerStatus.running ? '运行中' : '已停止' }}
            </el-tag>
            <el-button 
              v-if="!schedulerStatus.running"
              type="success" 
              size="small" 
              @click="startScheduler"
              :loading="schedulerLoading">
              <i class="el-icon-video-play"></i> 启动
            </el-button>
            <el-button 
              v-else
              type="warning" 
              size="small" 
              @click="stopScheduler"
              :loading="schedulerLoading">
              <i class="el-icon-video-pause"></i> 停止
            </el-button>
            <el-button 
              type="primary" 
              size="small" 
              @click="refreshSchedulerStatus"
              :loading="schedulerLoading">
              <i class="el-icon-refresh"></i> 刷新
            </el-button>
          </div>
        </div>
      </template>
      
      <div class="scheduler-info">
        <div class="info-item">
          <span class="info-label">上报策略:</span>
          <span class="info-value">每分钟检查，长期预测按定时时间执行，其他类型保持15分钟间隔</span>
        </div>
        <div class="info-item">
          <span class="info-label">检查时间:</span>
          <span class="info-value">每分钟第45秒</span>
        </div>
        <div class="info-item" v-if="schedulerStatus.next_report_times.length > 0">
          <span class="info-label">下次检查:</span>
          <span class="info-value">{{ schedulerStatus.next_report_times[0] }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">状态说明:</span>
          <span class="info-value">调度器在后端运行，前端关闭后仍会自动上报</span>
        </div>
      </div>
    </el-card>

    <!-- 主要内容区域 -->
    <div class="content-container">
      
      <!-- 上报数据质量统计卡片 -->
      <el-card class="info-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span><i class="el-icon-data-analysis"></i> 上报数据质量统计</span>
            <div class="stats-controls">
              <el-select v-model="statsQuery.farm_code" placeholder="全部场站" clearable size="small" style="width: 140px; margin-right: 10px;" @change="fetchStatistics">
                <el-option 
                  v-for="farm in windFarms" 
                  :key="farm.farm_code" 
                  :label="farm.farm_name" 
                  :value="farm.farm_code">
                </el-option>
              </el-select>
              <el-date-picker
                v-model="statsQuery.month"
                type="month"
                placeholder="选择月份"
                size="small"
                style="width: 120px; margin-right: 10px;"
                format="YYYY-MM"
                value-format="YYYY-MM"
                @change="fetchStatistics">
              </el-date-picker>
              <el-button type="primary" size="small" @click="fetchStatistics" :loading="statsLoading">
                <i class="el-icon-search"></i> 查询
              </el-button>
            </div>
          </div>
        </template>
        <div v-loading="statsLoading">
          <el-row :gutter="20" class="stats-summary">
            <el-col :xs="12" :sm="6">
              <div class="stat-box">
                <div class="stat-label">本日数据完整率</div>
                <div class="stat-value" :class="getRateColor(dailyStats.completeness_rate)">{{ formatRate(dailyStats.completeness_rate) }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="6">
              <div class="stat-box">
                <div class="stat-label">本日上报及时率</div>
                <div class="stat-value" :class="getRateColor(dailyStats.timeliness_rate)">{{ formatRate(dailyStats.timeliness_rate) }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="6">
              <div class="stat-box">
                <div class="stat-label">本月数据完整率</div>
                <div class="stat-value" :class="getRateColor(monthlyStats.completeness_rate)">{{ formatRate(monthlyStats.completeness_rate) }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="6">
              <div class="stat-box">
                <div class="stat-label">本月上报及时率</div>
                <div class="stat-value" :class="getRateColor(monthlyStats.timeliness_rate)">{{ formatRate(monthlyStats.timeliness_rate) }}</div>
              </div>
            </el-col>
          </el-row>
          <el-table :data="statistics" style="width: 100%; margin-top: 20px;" max-height="250" empty-text="暂无数据">
            <el-table-column prop="date" label="日期" width="100" sortable fixed></el-table-column>
            <el-table-column prop="farm_name" label="场站" width="120" show-overflow-tooltip>
              <template #default="scope">
                {{ getFarmNameFromCode(statsQuery.farm_code || scope.row.farm_code) }}
              </template>
            </el-table-column>
            <el-table-column prop="overall_completeness_rate" label="总体完整率(%)" align="center" width="140">
              <template #default="scope">
                <span :class="getRateColor(scope.row.overall_completeness_rate)">{{ formatRate(scope.row.overall_completeness_rate, false) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="overall_timeliness_rate" label="总体及时率(%)" align="center" width="140">
               <template #default="scope">
                <span :class="getRateColor(scope.row.overall_timeliness_rate)">{{ formatRate(scope.row.overall_timeliness_rate, false) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="分类型统计" max-width="400" align="center">
              <template #default="scope">
                <div class="type-stats-container">
                  <div v-for="(typeData, reportType) in scope.row.types" :key="reportType" class="type-stat-item">
                    <el-tag :type="getReportTypeColor(reportType)" size="small" class="type-tag">
                      {{ getReportTypeName(reportType) }}
                    </el-tag>
                    <span class="stat-text">完整率: <span :class="getRateColor(typeData.completeness_rate)">{{ formatRate(typeData.completeness_rate, false) }}%</span></span>
                    <span class="stat-text">及时率: <span :class="getRateColor(typeData.timeliness_rate)">{{ formatRate(typeData.timeliness_rate, false) }}%</span></span>
                  </div>
                  <div v-if="Object.keys(scope.row.types).length === 0" class="no-data">
                    暂无数据
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="notes" label="备注" min-width="200" show-overflow-tooltip align="center">
              <template #default="scope">
                {{ scope.row.notes || '所有上报均正常' }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>

      <!-- 风电场站管理卡片 -->
      <el-card class="info-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span><i class="el-icon-office-building"></i> 风电场站管理</span>
            <el-button type="primary" size="small" @click="showAddFarmDialog">
              <i class="el-icon-plus"></i> 添加场站
            </el-button>
          </div>
        </template>
        
        <el-table :data="windFarms" style="width: 100%" v-loading="farmsLoading">
          <el-table-column prop="farm_code" label="场站编码" max-width="140"></el-table-column>
          <el-table-column prop="farm_name" label="场站名称" max-width="140" show-overflow-tooltip></el-table-column>
          <el-table-column prop="capacity" label="装机容量(MW)" max-width="140" align="center">
            <template #default="scope">
              {{ scope.row.capacity || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="location" label="地理位置" max-width="140" show-overflow-tooltip></el-table-column>
          <el-table-column prop="is_active" label="状态" max-width="140" align="center">
            <template #default="scope">
              <el-tag :type="scope.row.is_active ? 'success' : 'danger'">
                {{ scope.row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" max-width="360" align="center" fixed="right">
            <template #default="scope">
              <div class="action-buttons">
                <el-button 
                  size="small" 
                  @click="editFarm(scope.row)" 
                  type="primary"
                  plain
                  class="action-btn">
                  <el-icon><Edit /></el-icon>
                  编辑
                </el-button>
                <el-button 
                  size="small" 
                  @click="viewFarmConfigs(scope.row)" 
                  type="success"
                  plain
                  class="action-btn">
                  <el-icon><Setting /></el-icon>
                  配置
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 上报配置管理卡片 -->
      <el-card class="info-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span><i class="el-icon-setting"></i> 上报配置管理</span>
            <div>
              <el-select v-model="selectedFarmId" placeholder="选择场站" @change="fetchConfigs" clearable style="margin-right: 10px;">
                <el-option 
                  v-for="farm in windFarms" 
                  :key="farm.id" 
                  :label="farm.farm_name" 
                  :value="farm.id">
                </el-option>
              </el-select>
              <el-button type="primary" size="small" @click="showAddConfigDialog">
                <i class="el-icon-plus"></i> 添加配置
              </el-button>
            </div>
          </div>
        </template>
        
        <el-table :data="reportConfigs" style="width: 100%" v-loading="configsLoading">
          <el-table-column prop="farm_name" label="场站" max-width="140" show-overflow-tooltip></el-table-column>
          <el-table-column prop="report_type" label="上报类型" max-width="140" align="center">
            <template #default="scope">
              <el-tag :type="getReportTypeColor(scope.row.report_type)">
                {{ getReportTypeName(scope.row.report_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="目标地址" max-width="140" show-overflow-tooltip align="center">
            <template #default="scope">
              {{ scope.row.target_ip }}:{{ scope.row.target_port }}
            </template>
          </el-table-column>
          <el-table-column label="上报设置" max-width="140" align="center">
            <template #default="scope">
              <div v-if="scope.row.report_type === 'forecast_long'">
                <div style="font-size: 12px; color: #909399;">定时时间</div>
                <div>{{ scope.row.report_time || '09:00' }}</div>
              </div>
              <div v-else>
                <div style="font-size: 12px; color: #909399;">周期(分钟)</div>
                <div>{{ scope.row.report_interval && scope.row.report_interval > 0 ? scope.row.report_interval : 15 }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="is_enabled" label="状态" max-width="140" align="center">
            <template #default="scope">
              <el-switch 
                v-model="scope.row.is_enabled" 
                @change="toggleConfig(scope.row)">
              </el-switch>
            </template>
          </el-table-column>
          <el-table-column prop="last_report_time" label="最后上报" max-width="140" align="center">
            <template #default="scope">
              {{ formatDateTime(scope.row.last_report_time) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" max-width="360" align="center" fixed="right">
            <template #default="scope">
              <div class="action-buttons">
                <el-button 
                  size="small" 
                  @click="editConfig(scope.row)" 
                  type="primary"
                  plain
                  class="action-btn">
                  <el-icon><Edit /></el-icon>
                  编辑
                </el-button>
                <el-button 
                  size="small" 
                  @click="previewReport(scope.row)" 
                  type="warning"
                  plain
                  class="action-btn"
                  :loading="previewLoading">
                  <el-icon><View /></el-icon>
                  预览上报
                </el-button>
                <el-button 
                  size="small" 
                  @click="deleteConfig(scope.row)" 
                  type="danger"
                  plain 
                  class="action-btn">
                  <el-icon><Delete /></el-icon>
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 上报日志查询卡片 -->
      <el-card class="info-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span><i class="el-icon-document-copy"></i> 上报日志</span>
            
            <!-- 查询条件和刷新按钮 -->
            <div class="log-query-controls">
              <el-form :inline="true" :model="logQuery" size="small" class="log-query-form">
                <el-form-item>
                  <el-select v-model="logQuery.farm_code" placeholder="全部场站" clearable style="width: 130px;">
                    <el-option 
                      v-for="farm in windFarms" 
                      :key="farm.farm_code" 
                      :label="farm.farm_name" 
                      :value="farm.farm_code">
                    </el-option>
                  </el-select>
                </el-form-item>
                <el-form-item>
                  <el-select v-model="logQuery.report_type" placeholder="全部类型" clearable style="width: 140px;">
                    <el-option-group label="功率数据">
                      <el-option label="实际功率" value="actual"></el-option>
                      <el-option label="超短期预测" value="forecast_short"></el-option>
                      <el-option label="长期预测" value="forecast_long"></el-option>
                      <el-option label="理论功率" value="theoretical_power"></el-option>
                      <el-option label="可用功率" value="available_power"></el-option>
                    </el-option-group>
                    <el-option-group label="单机数据">
                      <el-option label="单机风速" value="wind_speed"></el-option>
                      <el-option label="单机功率" value="turbine_power"></el-option>
                    </el-option-group>
                    <el-option-group label="运行信息">
                      <el-option label="气象信息" value="weather"></el-option>
                      <el-option label="装机容量" value="installed_capacity"></el-option>
                      <el-option label="可用容量" value="available_capacity"></el-option>
                    </el-option-group>
                  </el-select>
                </el-form-item>
                <el-form-item>
                  <el-select v-model="logQuery.status" placeholder="全部状态" clearable style="width: 110px;">
                    <el-option label="成功" value="success"></el-option>
                    <el-option label="失败" value="failed"></el-option>
                    <el-option label="超时" value="timeout"></el-option>
                  </el-select>
                </el-form-item>
                <el-form-item>
                  <el-date-picker
                    v-model="logQuery.dateRange"
                    type="datetimerange"
                    range-separator="至"
                    start-placeholder="开始时间"
                    end-placeholder="结束时间"
                    format="YYYY-MM-DD HH:mm"
                    value-format="YYYY-MM-DDTHH:mm:ss"
                    style="width: 280px;">
                  </el-date-picker>
                </el-form-item>
                <el-form-item>
                  <el-button type="success" @click="searchLogs"><el-icon><Search /></el-icon>查询</el-button>
                  <el-button @click="resetLogQuery"><el-icon><RefreshLeft /></el-icon>重置</el-button>
                  <el-button type="success" @click="refreshLogs"><el-icon><Refresh /></el-icon>刷新</el-button>
                </el-form-item>
              </el-form>
            </div>
          </div>
        </template>

        <!-- 日志表格 -->
        <el-table :data="reportLogs" style="width: 100%" v-loading="logsLoading">
          <el-table-column prop="farm_code" label="场站" max-width="140" show-overflow-tooltip>
            <template #default="scope">
              {{ getFarmNameFromCode(scope.row.farm_code) }}
            </template>
          </el-table-column>
          <el-table-column prop="report_type" label="类型" max-width="140" align="center">
            <template #default="scope">
              <el-tag :type="getReportTypeColor(scope.row.report_type)" size="mini">
                {{ getReportTypeName(scope.row.report_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="report_time" label="上报时间" max-width="140" align="center">
            <template #default="scope">
              {{ formatDateTime(scope.row.report_time) }}
            </template>
          </el-table-column>
          <el-table-column prop="data_count" label="数据量" max-width="140" align="center"></el-table-column>
          <el-table-column prop="status" label="状态" max-width="140" align="center">
            <template #default="scope">
              <el-tag :type="getStatusColor(scope.row.status)" size="mini">
                {{ getStatusName(scope.row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="execution_time" label="耗时(秒)" max-width="140" align="center">
            <template #default="scope">
              {{ scope.row.execution_time ? scope.row.execution_time.toFixed(2) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="response_code" label="响应码" max-width="140" align="center"></el-table-column>
          <el-table-column label="详情" max-width="140" align="center" fixed="right">
            <template #default="scope">
              <el-button 
                size="mini"
                @click="viewLogDetail(scope.row)" 
                type="text"
                style="width: 100%;">查看</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <el-pagination
          v-model:current-page="logPagination.page"
          v-model:page-size="logPagination.per_page"
          :page-sizes="[10, 20, 50, 100]"
          :total="logPagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
          style="margin-top: 20px; text-align: right;">
        </el-pagination>
      </el-card>
    </div>

    <!-- 添加/编辑场站对话框 -->
    <el-dialog 
      v-model="farmDialogVisible" 
      :title="farmDialogTitle" 
      width="500px"
      @close="resetFarmForm">
      <el-form :model="farmForm" :rules="farmRules" ref="farmFormRef" label-width="100px">
        <el-form-item label="场站编码" prop="farm_code">
          <el-input v-model="farmForm.farm_code" :disabled="farmForm.id"></el-input>
        </el-form-item>
        <el-form-item label="场站名称" prop="farm_name">
          <el-input v-model="farmForm.farm_name"></el-input>
        </el-form-item>
        <el-form-item label="装机容量" prop="capacity">
          <el-input v-model.number="farmForm.capacity" type="number" placeholder="单位：MW"></el-input>
        </el-form-item>
        <el-form-item label="地理位置" prop="location">
          <el-input v-model="farmForm.location"></el-input>
        </el-form-item>
        <el-form-item label="启用状态" prop="is_active">
          <el-switch v-model="farmForm.is_active"></el-switch>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="farmDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveFarm" :loading="farmSaving">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 添加/编辑配置对话框 -->
    <el-dialog 
      v-model="configDialogVisible" 
      :title="configDialogTitle" 
      width="600px"
      @close="resetConfigForm">
      <el-form :model="configForm" :rules="configRules" ref="configFormRef" label-width="120px">
        <el-form-item label="风电场站" prop="farm_id">
          <el-select v-model="configForm.farm_id" placeholder="选择场站">
            <el-option 
              v-for="farm in windFarms" 
              :key="farm.id" 
              :label="farm.farm_name" 
              :value="farm.id">
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="上报类型" prop="report_type">
          <el-select v-model="configForm.report_type" placeholder="选择上报类型" @change="handleReportTypeChange">
            <el-option-group label="功率数据">
              <el-option label="实际功率上报" value="actual"></el-option>
              <el-option label="超短期预测上报" value="forecast_short"></el-option>
              <el-option label="长期预测上报（每日定时）" value="forecast_long"></el-option>
              <el-option label="理论功率上报" value="theoretical_power"></el-option>
              <el-option label="可用功率上报" value="available_power"></el-option>
            </el-option-group>
            <el-option-group label="单机数据">
              <el-option label="单机风速上报" value="wind_speed"></el-option>
              <el-option label="单机功率上报" value="turbine_power"></el-option>
            </el-option-group>
            <el-option-group label="运行信息">
              <el-option label="气象信息上报" value="weather"></el-option>
              <el-option label="装机容量上报" value="installed_capacity"></el-option>
              <el-option label="可用容量上报" value="available_capacity"></el-option>
            </el-option-group>
          </el-select>
          <div v-if="configForm.report_type === 'forecast_long'" style="font-size: 12px; color: #909399; margin-top: 5px;">
            <i class="el-icon-info"></i> 长期预测每天只需定时上报一次，通常在每天上午进行
          </div>
          <div v-else-if="configForm.report_type" style="font-size: 12px; color: #909399; margin-top: 5px;">
            <i class="el-icon-info"></i> 此类型采用周期性上报，需设置上报间隔时间
          </div>
        </el-form-item>
        <el-form-item label="目标IP" prop="target_ip">
          <el-input v-model="configForm.target_ip" placeholder="192.168.1.100"></el-input>
        </el-form-item>
        <el-form-item label="目标端口" prop="target_port">
          <el-input v-model.number="configForm.target_port" type="number" placeholder="8080"></el-input>
        </el-form-item>
        <el-form-item label="上报周期" prop="report_interval" v-if="configForm.report_type !== 'forecast_long'">
          <el-input v-model.number="configForm.report_interval" type="number" placeholder="15">
            <template #append>分钟</template>
          </el-input>
        </el-form-item>
        <el-form-item label="定时时间" prop="report_time" v-if="configForm.report_type === 'forecast_long'">
          <el-time-picker 
            v-model="configForm.report_time" 
            format="HH:mm" 
            value-format="HH:mm"
            placeholder="09:00">
          </el-time-picker>
          <div style="font-size: 12px; color: #909399; margin-top: 5px;">
            长期预测每天定时上报一次，无需设置周期
          </div>
        </el-form-item>
        <el-form-item label="数据格式" prop="report_format">
          <el-select v-model="configForm.report_format">
            <el-option label="JSON" value="json"></el-option>
            <el-option label="XML" value="xml"></el-option>
            <el-option label="CSV" value="csv"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="超时时间" prop="timeout_seconds">
          <el-input v-model.number="configForm.timeout_seconds" type="number">
            <template #append>秒</template>
          </el-input>
        </el-form-item>
        <el-form-item label="重试次数" prop="retry_count">
          <el-input v-model.number="configForm.retry_count" type="number"></el-input>
        </el-form-item>
        <el-form-item label="启用状态" prop="is_enabled">
          <el-switch v-model="configForm.is_enabled"></el-switch>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="configDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveConfig" :loading="configSaving">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 日志详情对话框 -->
    <el-dialog v-model="logDetailVisible" title="上报日志详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="场站编码">{{ currentLog.farm_code }}</el-descriptions-item>
        <el-descriptions-item label="上报类型">
          <el-tag :type="getReportTypeColor(currentLog.report_type)">
            {{ getReportTypeName(currentLog.report_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="上报时间">{{ formatDateTime(currentLog.report_time) }}</el-descriptions-item>
        <el-descriptions-item label="数据条数">{{ currentLog.data_count }}</el-descriptions-item>
        <el-descriptions-item label="执行状态">
          <el-tag :type="getStatusColor(currentLog.status)">
            {{ getStatusName(currentLog.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="响应码">{{ currentLog.response_code || '-' }}</el-descriptions-item>
        <el-descriptions-item label="执行时间">{{ currentLog.execution_time ? currentLog.execution_time.toFixed(2) + '秒' : '-' }}</el-descriptions-item>
        <el-descriptions-item label="配置ID">{{ currentLog.config_id }}</el-descriptions-item>
      </el-descriptions>
      
      <div style="margin-top: 20px;" v-if="currentLog.response_message">
        <h4>响应消息：</h4>
        <el-input 
          type="textarea" 
          :value="currentLog.response_message" 
          :rows="4" 
          readonly>
        </el-input>
      </div>
      
      <div style="margin-top: 20px;" v-if="currentLog.error_message">
        <h4>错误信息：</h4>
        <el-input 
          type="textarea" 
          :value="currentLog.error_message" 
          :rows="4" 
          readonly>
        </el-input>
      </div>
    </el-dialog>

    <!-- 预览上报数据对话框 -->
    <el-dialog 
      v-model="previewDialogVisible" 
      title="预览上报数据" 
      width="80%" 
      :close-on-click-modal="false">
      
      <div v-if="previewData.config_info">
        <!-- 配置信息 -->
        <el-card class="preview-card" shadow="never">
          <template #header>
            <span class="preview-section-title">配置信息</span>
          </template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="场站名称">{{ previewData.config_info.farm_name }}</el-descriptions-item>
            <el-descriptions-item label="场站编码">{{ previewData.config_info.farm_code }}</el-descriptions-item>
            <el-descriptions-item label="上报类型">
              <el-tag :type="getReportTypeColor(previewData.config_info.report_type)">
                {{ getReportTypeName(previewData.config_info.report_type) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="目标地址">{{ previewData.config_info.target_url }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 数据概览 -->
        <el-card class="preview-card" shadow="never" style="margin-top: 15px;">
          <template #header>
            <span class="preview-section-title">数据概览</span>
          </template>
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="总记录数">{{ previewData.data_summary.total_records }}</el-descriptions-item>
            <el-descriptions-item label="有效数据">
              <el-tag :type="previewData.data_summary.has_data ? 'success' : 'warning'">
                {{ previewData.data_summary.has_data ? '是' : '否' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="空值记录">{{ previewData.data_summary.empty_records }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 数据内容 -->
        <el-card class="preview-card" shadow="never" style="margin-top: 15px;">
          <template #header>
            <div class="preview-section-header">
              <span class="preview-section-title">
                数据内容
                <span v-if="isPaginated" class="pagination-info">
                  (第 {{ currentPage }} 页，共 {{ Math.ceil(totalRows / pageSize) }} 页，总计 {{ totalRows }} 行)
                </span>
              </span>
              <div class="preview-controls">
                <!-- 长期预测只显示JSON视图，其他类型可以切换视图 -->
                <el-button-group size="small" v-if="previewData.config_info?.report_type !== 'forecast_long'">
                  <el-button 
                    :type="!showRawData ? 'primary' : ''" 
                    @click="showRawData = false">
                    表格视图
                  </el-button>
                  <el-button 
                    :type="showRawData ? 'primary' : ''" 
                    @click="showRawData = true">
                    JSON视图
                  </el-button>
                </el-button-group>
                <!-- 长期预测显示说明 -->
                <div v-else class="forecast-long-tip">
                  <el-tag type="info" size="small">
                    长期预测数据量大，仅支持JSON视图编辑
                  </el-tag>
                </div>
                <el-button size="small" @click="addDataRow" type="success" style="margin-left: 10px;" 
                           v-if="!isPaginated && previewData.config_info?.report_type !== 'forecast_long'">
                  <el-icon><Plus /></el-icon>
                  添加行
                </el-button>
                <!-- 表格视图下显示重置按钮 -->
                <el-button size="small" @click="resetEditableData" style="margin-left: 5px;"
                           v-if="previewData.config_info?.report_type !== 'forecast_long'">
                  <el-icon><Refresh /></el-icon>
                  重置
                </el-button>
              </div>
            </div>
          </template>

          <!-- 表格视图 (长期预测不显示表格视图) -->
          <div v-if="!showRawData && previewData.config_info?.report_type !== 'forecast_long'">
            <!-- 动态表格 -->
            <el-table 
              :data="editableData" 
              border 
              size="small" 
              :max-height="getTableMaxHeight()"
              :key="`table-${previewData.config_info?.id || 'default'}-${isPaginated ? currentPage : 'single'}`"
              lazy>
              <el-table-column label="序号" type="index" width="60" fixed="left"></el-table-column>
              
              <!-- 动态列渲染 -->
              <template v-if="previewData.data_structure">
                <el-table-column 
                  v-for="column in previewData.data_structure.columns" 
                  :key="column.key"
                  :label="column.label"
                  :width="getColumnWidth(column)"
                  :fixed="column.key === 'time' ? 'left' : false">
                  <template #default="scope">
                    <!-- 时间编辑器 -->
                    <el-date-picker
                      v-if="column.type === 'datetime' && column.editable"
                      v-model="scope.row[column.key]"
                      type="datetime"
                      placeholder="选择时间"
                      format="YYYY-MM-DD HH:mm:ss"
                      value-format="YYYY-MM-DDTHH:mm:ss"
                      size="small"
                      style="width: 100%;">
                    </el-date-picker>
                    
                    <!-- 数值编辑器 -->
                    <el-input-number
                      v-else-if="column.type === 'number' && column.editable"
                      v-model="scope.row[column.key]"
                      :precision="2"
                      size="small"
                      style="width: 100%;"
                      @change="handleValueChange(scope.row, column.key, $event)">
                    </el-input-number>
                    
                    <!-- 数据来源标签 -->
                    <el-tag 
                      v-else-if="column.key === 'data_source'"
                      :type="scope.row.data_source === 'database' ? 'success' : 
                             scope.row.data_source === 'empty' ? 'warning' : 'info'"
                      size="small">
                      {{ scope.row.data_source === 'database' ? '数据库' : 
                         scope.row.data_source === 'empty' ? '空值' : '手动' }}
                    </el-tag>
                    
                    <!-- 只读文本 -->
                    <span v-else>{{ scope.row[column.key] || '-' }}</span>
                  </template>
                </el-table-column>
              </template>
              
              <!-- 操作列 -->
              <el-table-column label="操作" width="80" fixed="right" v-if="!previewData.data_structure?.supports_bulk_edit || editableData.length < 50">
                <template #default="scope">
                  <el-button 
                    size="mini" 
                    type="danger" 
                    @click="removeDataRow(scope.$index)"
                    :icon="Delete">
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            
            <!-- 分页组件 -->
            <div v-if="isPaginated" class="pagination-container">
              <el-pagination
                v-model:current-page="currentPage"
                :page-size="pageSize"
                :total="totalRows"
                layout="prev, pager, next, jumper, total"
                @current-change="handlePageChange"
                :small="true">
              </el-pagination>
              <div class="page-tips">
                <el-alert
                  title="分页提示：长期预测数据已分成20页（每页48行），修改当前页数据后会自动保存，切换页面或提交时会合并所有页面的数据"
                  type="info"
                  :closable="false"
                  show-icon
                  size="small">
                </el-alert>
              </div>
            </div>
            
            <!-- 批量操作提示 -->
            <div v-if="!isPaginated && previewData.data_structure?.supports_bulk_edit && editableData.length >= 50" 
                 class="bulk-edit-tip">
              <el-alert
                title="数据量较大，建议使用JSON视图进行批量编辑"
                type="info"
                :closable="false"
                show-icon>
              </el-alert>
            </div>
          </div>

          <!-- JSON视图 -->
          <div v-if="showRawData || previewData.config_info?.report_type === 'forecast_long'">
            <!-- 长期预测专用说明 -->
            <div v-if="previewData.config_info?.report_type === 'forecast_long'" class="forecast-long-tip">
              <el-alert
                title="长期预测数据编辑说明"
                type="info"
                :closable="false"
                show-icon>
                                 <template #default>
                   <p>• 数据格式：960行JSON数组，每行包含时间(time)、功率值(value)、数据来源(data_source)</p>
                   <p>• 编辑技巧：可使用Ctrl+F搜索特定时间或值，支持批量查找替换</p>
                   <p>• 智能处理：修改value为非零值时，data_source会自动从"empty"变为"manual"</p>
                   <p>• 保存方式：编辑完成后按Ctrl+S保存，或点击下方的"应用JSON修改"按钮</p>
                   <p>• 时间范围：明天00:00到第10天23:45，每15分钟一个数据点（北京时间）</p>
                 </template>
              </el-alert>
            </div>
            
            <el-input
              v-model="editableDataJson"
              type="textarea"
              :rows="15"
              :placeholder="previewData.config_info?.report_type === 'forecast_long' ? 
                          '长期预测数据（960行）：可直接编辑JSON格式的数据，支持Ctrl+S保存修改...' : 
                          '编辑JSON数据...'"
              @keydown="handleJsonKeydown">
            </el-input>
            
            <!-- JSON操作按钮 -->
            <div class="json-actions" style="margin-top: 10px;">
              <el-button size="small" type="primary" @click="updateEditableDataFromJson">
                <el-icon><Refresh /></el-icon>
                应用JSON修改
              </el-button>
              <el-button size="small" @click="resetEditableData" style="margin-left: 10px;">
                <el-icon><Refresh /></el-icon>
                重置为原始数据
              </el-button>
            </div>
          </div>
        </el-card>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="previewDialogVisible = false">取消</el-button>
          <el-button @click="executeManualReport(false)" type="primary">
            使用原始数据上报
          </el-button>
          <el-button @click="executeManualReport(true)" type="warning">
            使用修改后数据上报
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Setting, Delete, View, Plus, Refresh, Search, RefreshLeft } from '@element-plus/icons-vue'
import axios from '../api/axios'

export default {
  name: 'ReportManagement',
  components: {
    Edit,
    Setting,
    Delete,
    View,
    Plus,
    Refresh,
    Search,
    RefreshLeft
  },
  setup() {
    // 保存原始的console.error用于清理
    const originalError = console.error
    
    // 数据定义
    const windFarms = ref([])
    const reportConfigs = ref([])
    const reportLogs = ref([])
    
    const farmsLoading = ref(false)
    const configsLoading = ref(false)
    const logsLoading = ref(false)
    
    const selectedFarmId = ref(null)
    
    // 调度器状态
    const schedulerStatus = ref({
      running: false,
      next_report_times: []
    })
    const schedulerLoading = ref(false)
    
    // 上报数据质量统计
    const statsLoading = ref(false)
    const statsQuery = reactive({
      farm_code: null,
      month: new Date().toISOString().slice(0, 7), // 默认当前月
    })
    const statistics = ref([])
    const dailyStats = ref({ completeness_rate: null, timeliness_rate: null })
    const monthlyStats = ref({ completeness_rate: null, timeliness_rate: null })
    
    // 场站对话框
    const farmDialogVisible = ref(false)
    const farmSaving = ref(false)
    const farmForm = reactive({
      id: null,
      farm_code: '',
      farm_name: '',
      capacity: null,
      location: '',
      is_active: true
    })
    
    const farmRules = {
      farm_code: [{ required: true, message: '请输入场站编码', trigger: 'blur' }],
      farm_name: [{ required: true, message: '请输入场站名称', trigger: 'blur' }]
    }
    
    // 配置对话框
    const configDialogVisible = ref(false)
    const configSaving = ref(false)
    const configForm = reactive({
      id: null,
      farm_id: null,
      report_type: '',
      target_ip: '',
      target_port: null,
      report_interval: 15,
      report_time: null,
      report_format: 'json',
      timeout_seconds: 30,
      retry_count: 3,
      is_enabled: true
    })
    
    // 动态配置验证规则
    const configRules = computed(() => {
      const baseRules = {
        farm_id: [{ required: true, message: '请选择风电场站', trigger: 'change' }],
        report_type: [{ required: true, message: '请选择上报类型', trigger: 'change' }],
        target_ip: [{ required: true, message: '请输入目标IP', trigger: 'blur' }],
        target_port: [{ required: true, message: '请输入目标端口', trigger: 'blur' }]
      }
      
      // 根据上报类型动态添加必填规则
      if (configForm.report_type === 'forecast_long') {
        // 长期预测需要定时时间，不需要上报周期
        baseRules.report_time = [{ required: true, message: '请选择定时时间', trigger: 'blur' }]
      } else {
        // 其他类型需要上报周期
        baseRules.report_interval = [{ required: true, message: '请输入上报周期', trigger: 'blur' }]
      }
      
      return baseRules
    })
    
    // 日志查询
    const logQuery = reactive({
      farm_code: '',
      report_type: '',
      status: '',
      dateRange: null
    })
    
    const logPagination = reactive({
      page: 1,
      per_page: 20,
      total: 0
    })
    
    // 日志详情
    const logDetailVisible = ref(false)
    const currentLog = ref({})
    
    // 预览上报数据
    const previewDialogVisible = ref(false)
    const previewData = ref({})
    const previewLoading = ref(false)
    const editableData = ref([])
    const showRawData = ref(false)
    
    // 分页相关状态
    const currentPage = ref(1)
    const pageSize = ref(48)
    const totalRows = ref(0)
    const allEditableData = ref([])  // 存储所有数据
    const isPaginated = ref(false)   // 是否启用分页
    
    // 计算属性
    const farmDialogTitle = computed(() => {
      return farmForm.id ? '编辑风电场站' : '添加风电场站'
    })
    
    const configDialogTitle = computed(() => {
      return configForm.id ? '编辑上报配置' : '添加上报配置'
    })
    
    // JSON编辑相关
    const editableDataJson = computed({
      get() {
        let dataToStringify
        if (isPaginated.value) {
          syncCurrentPageToAll()
          dataToStringify = allEditableData.value
        } else {
          dataToStringify = editableData.value
        }
        
        // 如果是超短期预测，确保字段顺序正确
        if (previewData.value.config_info?.report_type === 'forecast_short') {
          const orderedData = dataToStringify.map(item => {
            const orderedItem = {
              time: item.time,
              data_source: item.data_source,
              wp_pred2: item.wp_pred2,
              wp_pred3: item.wp_pred3,
              wp_pred4: item.wp_pred4,
              wp_pred5: item.wp_pred5,
              wp_pred6: item.wp_pred6,
              wp_pred7: item.wp_pred7,
              wp_pred8: item.wp_pred8,
              wp_pred9: item.wp_pred9,
              wp_pred10: item.wp_pred10,
              wp_pred11: item.wp_pred11,
              wp_pred12: item.wp_pred12,
              wp_pred13: item.wp_pred13,
              wp_pred14: item.wp_pred14,
              wp_pred15: item.wp_pred15,
              wp_pred16: item.wp_pred16,
              wp_pred17: item.wp_pred17
            }
            return orderedItem
          })
          return JSON.stringify(orderedData, null, 2)
        }
        
        return JSON.stringify(dataToStringify, null, 2)
      },
      set(value) {
        try {
          const parsed = JSON.parse(value)
          if (isPaginated.value) {
            allEditableData.value = parsed
            updateCurrentPageData()
          } else {
            editableData.value = parsed
          }
        } catch (e) {
          console.warn('JSON格式错误:', e)
        }
      }
    })
    
    const updateEditableDataFromJson = () => {
      // 手动应用JSON修改
      try {
        const parsed = JSON.parse(editableDataJson.value)
        
        // 自动处理数据来源字段：检查每个数据项，如果值被修改为非空但数据来源仍为empty，则自动设为manual
        const reportType = previewData.value.config_info?.report_type
        
        if (reportType === 'forecast_long') {
          parsed.forEach(item => {
            if (item.data_source === 'empty' && item.value !== null && item.value !== undefined && item.value !== 0) {
              item.data_source = 'manual'
            } else if (item.data_source === 'manual' && (item.value === null || item.value === undefined || item.value === 0)) {
              item.data_source = 'empty'
            }
          })
        } else if (reportType === 'actual') {
          parsed.forEach(item => {
            // 检查value或wp_true字段
            const powerValue = item.value !== undefined ? item.value : item.wp_true
            if (item.data_source === 'empty' && powerValue !== null && powerValue !== undefined && powerValue !== 0) {
              item.data_source = 'manual'
              // 同步更新两个字段
              if (item.value !== undefined) item.wp_true = item.value
              if (item.wp_true !== undefined) item.value = item.wp_true
            } else if (item.data_source === 'manual' && (powerValue === null || powerValue === undefined || powerValue === 0)) {
              item.data_source = 'empty'
            }
          })
        } else if (reportType === 'forecast_short') {
          parsed.forEach(item => {
            // 检查所有wp_pred字段（数据库字段为wp_pred2-wp_pred17）
            let hasNonZeroValue = false
            for (let i = 2; i <= 17; i++) {
              const predValue = item[`wp_pred${i}`]
              if (predValue !== null && predValue !== undefined && predValue !== 0) {
                hasNonZeroValue = true
                break
              }
            }
            if (item.data_source === 'empty' && hasNonZeroValue) {
              item.data_source = 'manual'
            } else if (item.data_source === 'manual' && !hasNonZeroValue) {
              item.data_source = 'empty'
            }
          })
        }
        
        if (isPaginated.value) {
          allEditableData.value = parsed
          updateCurrentPageData()
        } else {
          editableData.value = parsed
        }
        ElMessage.success('JSON数据已更新，数据来源已自动调整')
      } catch (e) {
        ElMessage.error('JSON格式错误，请检查语法')
      }
    }
    
    // 处理JSON编辑器的键盘事件
    const handleJsonKeydown = (event) => {
      // Ctrl+S 保存
      if (event.ctrlKey && event.key === 's') {
        event.preventDefault() // 阻止浏览器默认的保存行为
        updateEditableDataFromJson()
      }
    }
    
    // 分页相关方法
    const updateCurrentPageData = () => {
      if (!isPaginated.value) return
      
      // 使用requestAnimationFrame避免ResizeObserver循环
      requestAnimationFrame(() => {
        const start = (currentPage.value - 1) * pageSize.value
        const end = start + pageSize.value
        editableData.value = allEditableData.value.slice(start, end)
      })
    }
    
    const handlePageChange = (page) => {
      // 同步当前页数据到全量数据
      syncCurrentPageToAll()
      
      // 使用requestAnimationFrame来避免循环
      requestAnimationFrame(() => {
        currentPage.value = page
        updateCurrentPageData()
      })
    }
    
    const syncCurrentPageToAll = () => {
      if (!isPaginated.value) return
      
      const start = (currentPage.value - 1) * pageSize.value
      // 将当前页的修改同步回全量数据
      for (let i = 0; i < editableData.value.length; i++) {
        if (start + i < allEditableData.value.length) {
          allEditableData.value[start + i] = { ...editableData.value[i] }
        }
      }
    }
    
    const getAllDataForSubmit = () => {
      if (isPaginated.value) {
        syncCurrentPageToAll()
        return allEditableData.value
      } else {
        return editableData.value
      }
    }
    
    // 获取风电场站列表
    const fetchFarms = async () => {
      farmsLoading.value = true
      try {
        console.log('开始获取风电场站列表...')
        const response = await axios.get('/api/report/farms')
        console.log('风电场站列表响应:', response.data)
        windFarms.value = response.data
      } catch (error) {
        console.error('获取风电场站列表失败:', error)
        if (error.response?.status === 405) {
          ElMessage.error('API路由配置错误，请检查后端服务')
        } else if (error.response?.status === 401) {
          ElMessage.error('认证失败，请重新登录')
        } else {
          ElMessage.error('获取风电场站列表失败: ' + (error.response?.data?.error || error.message))
        }
      } finally {
        farmsLoading.value = false
      }
    }
    
    // 获取上报配置列表
    const fetchConfigs = async () => {
      configsLoading.value = true
      try {
        const params = {}
        if (selectedFarmId.value) {
          params.farm_id = selectedFarmId.value
        }
        
        const response = await axios.get('/api/report/configs', {
          params
        })
        reportConfigs.value = response.data.map(config => ({
          ...config,
          reporting: false // 添加手动上报状态
        }))
      } catch (error) {
        console.error('获取上报配置列表失败:', error)
        ElMessage.error('获取上报配置列表失败')
      } finally {
        configsLoading.value = false
      }
    }
    
    // 获取调度器状态
    const fetchSchedulerStatus = async () => {
      try {
        const response = await axios.get('/api/report/scheduler/status')
        schedulerStatus.value = response.data
      } catch (error) {
        console.error('获取调度器状态失败:', error)
        ElMessage.error('获取调度器状态失败')
      }
    }
    
    // 启动调度器
    const startScheduler = async () => {
      schedulerLoading.value = true
      try {
        const response = await axios.post('/api/report/scheduler/start')
        ElMessage.success(response.data.message)
        await fetchSchedulerStatus()
      } catch (error) {
        console.error('启动调度器失败:', error)
        ElMessage.error('启动调度器失败')
      } finally {
        schedulerLoading.value = false
      }
    }
    
    // 停止调度器
    const stopScheduler = async () => {
      schedulerLoading.value = true
      try {
        const response = await axios.post('/api/report/scheduler/stop')
        ElMessage.success(response.data.message)
        await fetchSchedulerStatus()
      } catch (error) {
        console.error('停止调度器失败:', error)
        ElMessage.error('停止调度器失败')
      } finally {
        schedulerLoading.value = false
      }
    }
    
    // 刷新调度器状态
    const refreshSchedulerStatus = async () => {
      schedulerLoading.value = true
      try {
        await fetchSchedulerStatus()
        ElMessage.success('调度器状态已刷新')
      } catch (error) {
        console.error('刷新调度器状态失败:', error)
        ElMessage.error('刷新调度器状态失败')
      } finally {
        schedulerLoading.value = false
      }
    }

    // 获取上报日志
    const fetchLogs = async () => {
      logsLoading.value = true
      try {
        const params = {
          page: logPagination.page,
          per_page: logPagination.per_page
        }
        
        if (logQuery.farm_code) params.farm_code = logQuery.farm_code
        if (logQuery.report_type) params.report_type = logQuery.report_type
        if (logQuery.status) params.status = logQuery.status
        if (logQuery.dateRange && logQuery.dateRange.length === 2) {
          params.start_date = logQuery.dateRange[0]
          params.end_date = logQuery.dateRange[1]
        }
        
        const response = await axios.get('/api/report/logs', {
          params
        })
        
        reportLogs.value = response.data.logs
        logPagination.total = response.data.total
      } catch (error) {
        console.error('获取上报日志失败:', error)
        ElMessage.error('获取上报日志失败')
      } finally {
        logsLoading.value = false
      }
    }
    
    // 显示添加场站对话框
    const showAddFarmDialog = () => {
      resetFarmForm()
      farmDialogVisible.value = true
    }
    
    // 编辑场站
    const editFarm = (farm) => {
      Object.assign(farmForm, farm)
      farmDialogVisible.value = true
    }
    
    // 保存场站
    const saveFarm = async () => {
      farmSaving.value = true
      try {
        if (farmForm.id) {
          // 更新
          await axios.put(`/api/report/farms/${farmForm.id}`, farmForm)
          ElMessage.success('场站更新成功')
        } else {
          // 创建
          await axios.post('/api/report/farms', farmForm)
          ElMessage.success('场站创建成功')
        }
        farmDialogVisible.value = false
        await fetchFarms()
      } catch (error) {
        console.error('保存场站失败:', error)
        ElMessage.error(error.response?.data?.error || '保存场站失败')
      } finally {
        farmSaving.value = false
      }
    }
    
    // 重置场站表单
    const resetFarmForm = () => {
      Object.assign(farmForm, {
        id: null,
        farm_code: '',
        farm_name: '',
        capacity: null,
        location: '',
        is_active: true
      })
    }
    
    // 查看场站配置
    const viewFarmConfigs = (farm) => {
      selectedFarmId.value = farm.id
      fetchConfigs()
    }
    
    // 显示添加配置对话框
    const showAddConfigDialog = () => {
      resetConfigForm()
      if (selectedFarmId.value) {
        configForm.farm_id = selectedFarmId.value
      }
      configDialogVisible.value = true
    }
    
    // 编辑配置
    const editConfig = (config) => {
      Object.assign(configForm, config)
      
      // 编辑时确保字段正确显示
      if (config.report_type === 'forecast_long') {
        // 长期预测：确保有定时时间，设置特殊的上报周期值
        if (!configForm.report_time && config.report_time) {
          configForm.report_time = config.report_time
        }
        configForm.report_interval = -1
      } else {
        // 其他类型：确保有上报周期，清空定时时间
        if (!configForm.report_interval && config.report_interval) {
          configForm.report_interval = config.report_interval
        }
        configForm.report_time = null
      }
      
      configDialogVisible.value = true
    }
    
    // 保存配置
    const saveConfig = async () => {
      configSaving.value = true
      try {
        // 准备保存的数据
        const saveData = { ...configForm }
        
        // 长期预测类型特殊处理
        if (saveData.report_type === 'forecast_long') {
          // 长期预测不需要上报周期，设为特殊值-1表示不使用周期
          saveData.report_interval = -1
          // 确保有定时时间
          if (!saveData.report_time) {
            saveData.report_time = '09:00'
          }
        } else {
          // 其他类型不需要定时时间
          saveData.report_time = null
          // 确保有上报周期
          if (!saveData.report_interval) {
            saveData.report_interval = 15
          }
        }
        
        if (configForm.id) {
          // 更新
          await axios.put(`/api/report/configs/${configForm.id}`, saveData)
          ElMessage.success('配置更新成功')
        } else {
          // 创建
          await axios.post('/api/report/configs', saveData)
          ElMessage.success('配置创建成功')
        }
        configDialogVisible.value = false
        await fetchConfigs()
      } catch (error) {
        console.error('保存配置失败:', error)
        ElMessage.error(error.response?.data?.error || '保存配置失败')
      } finally {
        configSaving.value = false
      }
    }
    
    // 重置配置表单
    const resetConfigForm = () => {
      Object.assign(configForm, {
        id: null,
        farm_id: null,
        report_type: '',
        target_ip: '',
        target_port: null,
        report_interval: 15,  // 非长期预测的默认值
        report_time: null,
        report_format: 'json',
        timeout_seconds: 30,
        retry_count: 3,
        is_enabled: true
      })
    }
    
    // 监听上报类型变化，调整表单字段
    const handleReportTypeChange = () => {
      if (configForm.report_type === 'forecast_long') {
        // 长期预测：设置特殊的上报周期值，设置默认定时时间
        configForm.report_interval = -1
        if (!configForm.report_time) {
          configForm.report_time = '09:00'  // 默认上午9点
        }
      } else {
        // 其他类型：设置默认上报周期，清空定时时间
        if (!configForm.report_interval || configForm.report_interval === -1) {
          configForm.report_interval = 15
        }
        if (configForm.report_type !== 'forecast_long') {
          configForm.report_time = null
        }
      }
    }
    
    // 切换配置启用状态
    const toggleConfig = async (config) => {
      try {
        await axios.put(`/api/report/configs/${config.id}`, {
          is_enabled: config.is_enabled
        })
        ElMessage.success(config.is_enabled ? '配置已启用' : '配置已禁用')
      } catch (error) {
        console.error('更新配置状态失败:', error)
        config.is_enabled = !config.is_enabled // 回滚状态
        ElMessage.error('更新配置状态失败')
      }
    }
    
    // 删除配置
    const deleteConfig = async (config) => {
      try {
        await ElMessageBox.confirm('确定要删除这个上报配置吗？', '确认删除', {
          type: 'warning'
        })
        
        await axios.delete(`/api/report/configs/${config.id}`)
        
        ElMessage.success('配置删除成功')
        await fetchConfigs()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除配置失败:', error)
          ElMessage.error('删除配置失败')
        }
      }
    }
    
    // 预览上报数据
    const previewReport = async (config) => {
      previewLoading.value = true
      try {
        const response = await axios.post('/api/report/preview-report', {
          config_id: config.id
        })
        
        previewData.value = response.data
        let dataToEdit = response.data.payload.data || []
        
        // 如果数据库中没有数据，则根据不同类型生成模板数据
        if (dataToEdit.length === 0) {
          console.log(`数据库中没有找到${getReportTypeName(config.report_type)}数据，使用模板数据`)
          
          if (config.report_type === 'forecast_long') {
            dataToEdit = generateLongForecastTemplate()
            ElMessage.info('长期预测：已自动设置为明天00:00开始的10天数据（北京时间）')
          } else if (config.report_type === 'forecast_short') {
            dataToEdit = generateShortForecastTemplate()
            ElMessage.info('超短期预测：已自动设置为下一个15分钟整点时刻（北京时间）')
          } else if (config.report_type === 'actual') {
            dataToEdit = generateActualPowerTemplate()
            ElMessage.info('实际功率：已自动设置为上一个15分钟整点时刻（北京时间，实发数据）')
          } else if (config.report_type === 'wind_speed') {
            dataToEdit = generateWindSpeedTemplate()
          } else if (config.report_type === 'turbine_power') {
            dataToEdit = generateTurbinePowerTemplate()
          } else if (config.report_type === 'weather') {
            dataToEdit = generateWeatherTemplate()
          } else if (config.report_type === 'installed_capacity') {
            dataToEdit = generateInstalledCapacityTemplate()
          } else if (config.report_type === 'available_capacity') {
            dataToEdit = generateAvailableCapacityTemplate()
          } else if (config.report_type === 'theoretical_power') {
            dataToEdit = generateTheoreticalPowerTemplate()
            ElMessage.info('理论功率：已自动设置为上一个15分钟整点时刻（北京时间）')
          } else if (config.report_type === 'available_power') {
            dataToEdit = generateAvailablePowerTemplate()
            ElMessage.info('可用功率：已自动设置为上一个15分钟整点时刻（北京时间）')
          }
        } else {
          console.log(`数据库中找到${dataToEdit.length}条${getReportTypeName(config.report_type)}数据`)
        }
        
        // 处理分页逻辑和视图模式
        if (config.report_type === 'forecast_long') {
          // 长期预测强制使用JSON视图，避免表格渲染导致的ResizeObserver错误
          showRawData.value = true
          isPaginated.value = false // 不使用分页，直接在JSON中编辑
          editableData.value = JSON.parse(JSON.stringify(dataToEdit))
          totalRows.value = dataToEdit.length
        } else {
          // 其他类型默认表格视图，可以切换
          showRawData.value = false
          isPaginated.value = false
          editableData.value = JSON.parse(JSON.stringify(dataToEdit))
          totalRows.value = dataToEdit.length
        }
        
        // 使用requestAnimationFrame来避免ResizeObserver循环
        await new Promise(resolve => {
          // 首先设置对话框可见
          previewDialogVisible.value = true
          
          // 使用双重requestAnimationFrame确保DOM完全渲染
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              resolve()
            })
          })
        })
      } catch (error) {
        console.error('预览上报数据失败:', error)
        ElMessage.error(error.response?.data?.error || '预览上报数据失败')
      } finally {
        previewLoading.value = false
      }
    }
    
    // 生成长期预测模板数据
    const generateLongForecastTemplate = () => {
      const template = []
      
      // 计算起始时间：明天的00:00:00（长期预测通常从第二天开始，北京时间）
      const beijingNow = getBeijingTime()
      const tomorrow = new Date(beijingNow)
      tomorrow.setUTCDate(beijingNow.getUTCDate() + 1)
      tomorrow.setUTCHours(0, 0, 0, 0)
      
      // 生成10天的数据，每天96个点（24小时 * 4个15分钟），总共960行数据
      for (let day = 0; day < 10; day++) {
        for (let hour = 0; hour < 24; hour++) {
          for (let quarter = 0; quarter < 4; quarter++) {
            const time = new Date(tomorrow)
            time.setUTCDate(tomorrow.getUTCDate() + day)
            time.setUTCHours(hour)
            time.setUTCMinutes(quarter * 15)
            
            template.push({
              time: beijingTimeToISOString(time),
              value: 0,
              data_source: 'template'
            })
          }
        }
      }
      
      return template
    }
    
    // 生成超短期预测模板数据
    const generateShortForecastTemplate = () => {
      const beijingNow = getBeijingTime()
      
      // 计算下一个15分钟整点时刻（北京时间）
      const nextQuarter = new Date(beijingNow)
      const minutes = beijingNow.getUTCMinutes() // 使用UTC方法获取北京时间的分钟
      const quarterMinutes = Math.ceil(minutes / 15) * 15
      
      if (quarterMinutes >= 60) {
        nextQuarter.setUTCHours(beijingNow.getUTCHours() + 1)
        nextQuarter.setUTCMinutes(0)
      } else {
        nextQuarter.setUTCMinutes(quarterMinutes)
      }
      nextQuarter.setUTCSeconds(0)
      nextQuarter.setUTCMilliseconds(0)
      
              // 只生成一行数据，包含下一个15分钟整点时刻和16个预测值字段
        const row = {
          time: beijingTimeToISOString(nextQuarter),
          data_source: 'template',
          // 按顺序添加预测值字段（数据库字段为wp_pred2-wp_pred17）
          wp_pred2: 0,
          wp_pred3: 0,
          wp_pred4: 0,
          wp_pred5: 0,
          wp_pred6: 0,
          wp_pred7: 0,
          wp_pred8: 0,
          wp_pred9: 0,
          wp_pred10: 0,
          wp_pred11: 0,
          wp_pred12: 0,
          wp_pred13: 0,
          wp_pred14: 0,
          wp_pred15: 0,
          wp_pred16: 0,
          wp_pred17: 0
        }
      
      return [row]
    }
    
    // 生成实际功率模板数据
    const generateActualPowerTemplate = () => {
      const beijingNow = getBeijingTime()
      
      // 计算上一个15分钟整点时刻（实际功率是过去的数据，北京时间）
      const prevQuarter = new Date(beijingNow)
      const minutes = beijingNow.getUTCMinutes()
      const quarterMinutes = Math.floor(minutes / 15) * 15
      
      prevQuarter.setUTCMinutes(quarterMinutes)
      prevQuarter.setUTCSeconds(0)
      prevQuarter.setUTCMilliseconds(0)
      
      // 如果当前时间就是整点，则取前一个15分钟
      if (minutes === quarterMinutes && beijingNow.getUTCSeconds() === 0 && beijingNow.getUTCMilliseconds() === 0) {
        prevQuarter.setUTCMinutes(prevQuarter.getUTCMinutes() - 15)
        if (prevQuarter.getUTCMinutes() < 0) {
          prevQuarter.setUTCHours(prevQuarter.getUTCHours() - 1)
          prevQuarter.setUTCMinutes(45)
        }
      }
      
      // 只生成一行数据，包含上一个15分钟整点时刻的实际功率值
      const row = {
        time: beijingTimeToISOString(prevQuarter),
        value: 0,
        wp_true: 0,  // 添加兼容性字段
        data_source: 'template'
      }
      
      return [row]
    }
    
    // 生成单机风速模板数据
    const generateWindSpeedTemplate = () => {
      const template = []
      const beijingNow = getBeijingTime()
      
      // 生成当前北京时间的数据，作为后备模板（3台风机）
      for (let i = 1; i <= 3; i++) {
        template.push({
          time: beijingTimeToISOString(beijingNow),
          turbine_id: `WT${i.toString().padStart(2, '0')}`,
          wind_speed: 0,
          wind_direction: 0,
          nacelle_position: 0,
          data_source: 'template'
        })
      }
      
      return template
    }
    
    // 生成单机功率模板数据
    const generateTurbinePowerTemplate = () => {
      const template = []
      const beijingNow = getBeijingTime()
      
      // 生成当前北京时间的数据，作为后备模板（3台风机）
      for (let i = 1; i <= 3; i++) {
        template.push({
          time: beijingTimeToISOString(beijingNow),
          turbine_id: `WT${i.toString().padStart(2, '0')}`,
          active_power: 0,
          reactive_power: 0,
          power_factor: 0,
          rotor_speed: 0,
          generator_speed: 0,
          blade_angle: 0,
          turbine_status: '正常',
          data_source: 'template'
        })
      }
      
      return template
    }
    
    // 生成气象信息模板数据
    const generateWeatherTemplate = () => {
      const template = []
      const beijingNow = getBeijingTime()
      
      template.push({
        time: beijingTimeToISOString(beijingNow),
        temperature: 0,
        humidity: 0,
        pressure: 0,
        wind_speed_avg: 0,
        wind_speed_max: 0,
        wind_direction: 0,
        visibility: 0,
        precipitation: 0,
        weather_condition: '晴',
        data_source: 'template'
      })
      
      return template
    }
    
    // 生成装机容量模板数据
    const generateInstalledCapacityTemplate = () => {
      const template = []
      const beijingNow = getBeijingTime()
      
      template.push({
        time: beijingTimeToISOString(beijingNow),
        total_capacity: 0,
        turbine_count: 0,
        turbine_capacity: 0,
        commissioning_date: beijingTimeToISOString(beijingNow),
        remarks: '',
        data_source: 'template'
      })
      
      return template
    }
    
    // 生成可用容量模板数据
    const generateAvailableCapacityTemplate = () => {
      const template = []
      const beijingNow = getBeijingTime()
      
      template.push({
        time: beijingTimeToISOString(beijingNow),
        available_capacity: 0,
        maintenance_capacity: 0,
        fault_capacity: 0,
        limited_capacity: 0,
        availability_rate: 0,
        maintenance_turbines: 0,
        fault_turbines: 0,
        data_source: 'template'
      })
      
      return template
    }
    
    // 生成理论功率模板数据
    const generateTheoreticalPowerTemplate = () => {
      const beijingNow = getBeijingTime()
      
      // 计算上一个15分钟整点时刻（理论功率通常基于历史数据计算，北京时间）
      const prevQuarter = new Date(beijingNow)
      const minutes = beijingNow.getUTCMinutes()
      const quarterMinutes = Math.floor(minutes / 15) * 15
      
      prevQuarter.setUTCMinutes(quarterMinutes)
      prevQuarter.setUTCSeconds(0)
      prevQuarter.setUTCMilliseconds(0)
      
      // 如果当前时间就是整点，则取前一个15分钟
      if (minutes === quarterMinutes && beijingNow.getUTCSeconds() === 0 && beijingNow.getUTCMilliseconds() === 0) {
        prevQuarter.setUTCMinutes(prevQuarter.getUTCMinutes() - 15)
        if (prevQuarter.getUTCMinutes() < 0) {
          prevQuarter.setUTCHours(prevQuarter.getUTCHours() - 1)
          prevQuarter.setUTCMinutes(45)
        }
      }
      
      const template = []
      template.push({
        time: beijingTimeToISOString(prevQuarter),
        theoretical_power: 0,
        wind_speed_hub: 0,
        air_density: 0,
        power_curve_factor: 0,
        wake_loss_factor: 0,
        availability_factor: 0,
        data_source: 'template'
      })
      
      return template
    }
    
    // 生成可用功率模板数据
    const generateAvailablePowerTemplate = () => {
      const beijingNow = getBeijingTime()
      
      // 计算上一个15分钟整点时刻（可用功率通常基于历史状态数据，北京时间）
      const prevQuarter = new Date(beijingNow)
      const minutes = beijingNow.getUTCMinutes()
      const quarterMinutes = Math.floor(minutes / 15) * 15
      
      prevQuarter.setUTCMinutes(quarterMinutes)
      prevQuarter.setUTCSeconds(0)
      prevQuarter.setUTCMilliseconds(0)
      
      // 如果当前时间就是整点，则取前一个15分钟
      if (minutes === quarterMinutes && beijingNow.getUTCSeconds() === 0 && beijingNow.getUTCMilliseconds() === 0) {
        prevQuarter.setUTCMinutes(prevQuarter.getUTCMinutes() - 15)
        if (prevQuarter.getUTCMinutes() < 0) {
          prevQuarter.setUTCHours(prevQuarter.getUTCHours() - 1)
          prevQuarter.setUTCMinutes(45)
        }
      }
      
      const template = []
      template.push({
        time: beijingTimeToISOString(prevQuarter),
        available_power: 0,
        grid_constraint: 0,
        environmental_constraint: 0,
        maintenance_constraint: 0,
        operational_constraint: 0,
        grid_availability: 0,
        constraint_reason: '',
        data_source: 'template'
      })
      
      return template
    }
    
    // 执行手动上报
    const executeManualReport = async (useCustomData = false) => {
      try {
        const payload = {
          config_id: previewData.value.config_info.id
        }
        
        if (useCustomData) {
          payload.data = getAllDataForSubmit()
        }
        
        await axios.post('/api/report/manual-report', payload)
        
        ElMessage.success(`手动上报执行成功${useCustomData ? '（使用自定义数据）' : ''}`)
        previewDialogVisible.value = false
        await fetchConfigs() // 刷新配置列表
        await fetchLogs() // 刷新日志列表
      } catch (error) {
        console.error('手动上报失败:', error)
        ElMessage.error(error.response?.data?.error || '手动上报失败')
      }
    }
    
    // 添加数据行
    const addDataRow = () => {
      const reportType = previewData.value.config_info?.report_type
      const beijingNow = getBeijingTime()
      let newRow = {
        time: beijingTimeToISOString(beijingNow),
        data_source: 'manual'
      }
      
      if (reportType === 'actual' || reportType === 'forecast_long') {
        newRow.value = 0
      } else if (reportType === 'forecast_short') {
        // 为超短期预测按顺序添加16个预测值（数据库字段为wp_pred2-wp_pred17）
        newRow = {
          time: beijingTimeToISOString(beijingNow),
          data_source: 'manual',
          wp_pred2: 0,
          wp_pred3: 0,
          wp_pred4: 0,
          wp_pred5: 0,
          wp_pred6: 0,
          wp_pred7: 0,
          wp_pred8: 0,
          wp_pred9: 0,
          wp_pred10: 0,
          wp_pred11: 0,
          wp_pred12: 0,
          wp_pred13: 0,
          wp_pred14: 0,
          wp_pred15: 0,
          wp_pred16: 0,
          wp_pred17: 0
        }
      }
      
      // 使用防抖更新
      debouncedTableUpdate(() => {
        editableData.value.push(newRow)
      })
    }
    
    // 获取表格最大高度
    const getTableMaxHeight = () => {
      const dataLength = editableData.value?.length || 0
      // 为长期预测数据设置更合理的高度
      if (isPaginated.value) return 400 // 分页时固定高度，减少渲染压力
      if (dataLength > 20) return 380
      if (dataLength > 10) return 320
      if (dataLength > 5) return 280
      return 200
    }
    
    // 获取列宽
    const getColumnWidth = (column) => {
      if (column.key === 'time') return 180
      if (column.key === 'data_source') return 100
      if (column.type === 'number') return 120
      return 100
    }
    
    // 删除数据行
    const removeDataRow = (index) => {
      // 使用防抖更新
      debouncedTableUpdate(() => {
        editableData.value.splice(index, 1)
      })
    }
    
    // 重置数据
    const resetEditableData = () => {
      const originalData = previewData.value.payload.data || []
      if (isPaginated.value) {
        allEditableData.value = JSON.parse(JSON.stringify(originalData))
        updateCurrentPageData()
      } else {
        editableData.value = JSON.parse(JSON.stringify(originalData))
      }
    }
    
    // 搜索日志
    const searchLogs = () => {
      logPagination.page = 1
      fetchLogs()
    }
    
    // 重置日志查询
    const resetLogQuery = () => {
      Object.assign(logQuery, {
        farm_code: '',
        report_type: '',
        status: '',
        dateRange: null
      })
      logPagination.page = 1
      fetchLogs()
    }
    
    // 刷新日志
    const refreshLogs = () => {
      fetchLogs()
    }
    
    // 查看日志详情
    const viewLogDetail = (log) => {
      currentLog.value = log
      logDetailVisible.value = true
    }
    
    // 分页处理
    const handleSizeChange = (val) => {
      logPagination.per_page = val
      logPagination.page = 1
      fetchLogs()
    }
    
    const handleCurrentChange = (val) => {
      logPagination.page = val
      fetchLogs()
    }
    
    // 工具函数
    const getReportTypeName = (type) => {
      const types = {
        'actual': '实际功率',
        'forecast_short': '超短期预测',
        'forecast_long': '长期预测',
        'wind_speed': '单机风速',
        'turbine_power': '单机功率',
        'weather': '气象信息',
        'installed_capacity': '装机容量',
        'available_capacity': '可用容量',
        'theoretical_power': '理论功率',
        'available_power': '可用功率'
      }
      return types[type] || type
    }
    
    const getReportTypeColor = (type) => {
      const colors = {
        'actual': 'success',
        'forecast_short': 'warning',
        'forecast_long': 'info',
        'wind_speed': 'primary',
        'turbine_power': 'success',
        'weather': 'info',
        'installed_capacity': 'warning',
        'available_capacity': 'danger',
        'theoretical_power': 'primary',
        'available_power': 'success'
      }
      return colors[type] || ''
    }
    
    const getStatusName = (status) => {
      const statuses = {
        'success': '成功',
        'failed': '失败',
        'timeout': '超时'
      }
      return statuses[status] || status
    }
    
    const getStatusColor = (status) => {
      const colors = {
        'success': 'success',
        'failed': 'danger',
        'timeout': 'warning'
      }
      return colors[status] || ''
    }
    
    const formatDateTime = (dateTime) => {
      if (!dateTime) return '-'
      try {
        return new Date(dateTime).toLocaleString('zh-CN')
      } catch {
        return dateTime
      }
    }
    
    // 防抖相关
    let tableUpdateTimer = null
    const debouncedTableUpdate = (fn) => {
      if (tableUpdateTimer) {
        clearTimeout(tableUpdateTimer)
      }
      tableUpdateTimer = setTimeout(() => {
        requestAnimationFrame(fn)
      }, 10)
    }
    
    // 获取北京时间的工具函数
    const getBeijingTime = (date = null) => {
      const targetDate = date || new Date()
      // 获取北京时间（UTC+8）
      const beijingTime = new Date(targetDate.getTime() + (8 * 60 * 60 * 1000))
      return beijingTime
    }
    
    // 将北京时间转换为ISO字符串（但保持北京时区的数值）
    const beijingTimeToISOString = (beijingDate) => {
      const year = beijingDate.getUTCFullYear()
      const month = String(beijingDate.getUTCMonth() + 1).padStart(2, '0')
      const day = String(beijingDate.getUTCDate()).padStart(2, '0')
      const hours = String(beijingDate.getUTCHours()).padStart(2, '0')
      const minutes = String(beijingDate.getUTCMinutes()).padStart(2, '0')
      const seconds = String(beijingDate.getUTCSeconds()).padStart(2, '0')
      return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`
    }
    
    // 处理数值变化，自动更新数据来源
    const handleValueChange = (row, columnKey, newValue) => {
      // 如果是实际功率的value字段，同时更新wp_true字段以保持兼容性
      if (columnKey === 'value' && previewData.value.config_info?.report_type === 'actual') {
        row.wp_true = newValue
      }
      
      // 当用户修改数值时，自动将data_source从'empty'改为'manual'
      if (row.data_source === 'empty' && newValue !== null && newValue !== undefined && newValue !== '') {
        row.data_source = 'manual'
        ElMessage.success('数据来源已自动更新为"手动"')
      }
      // 如果用户将值改为空，则设置为empty
      else if ((newValue === null || newValue === undefined || newValue === '') && row.data_source === 'manual') {
        row.data_source = 'empty'
      }
    }
    
    // 生命周期
    onMounted(async () => {
      await fetchFarms()
      await fetchConfigs()
      await fetchLogs()
      await fetchSchedulerStatus()
      await fetchStatistics()
      
      // 全局ResizeObserver错误处理 - 使用debounce和requestAnimationFrame
      const handleResizeObserverError = (e) => {
        if (e.message && e.message.includes('ResizeObserver loop completed with undelivered notifications')) {
          e.preventDefault()
          e.stopPropagation()
          return false
        }
      }
      
      // 添加错误监听器
      window.addEventListener('error', handleResizeObserverError, { passive: true })
      
      // 重写console.error来过滤ResizeObserver错误
      console.error = function(...args) {
        if (args[0] && args[0].toString().includes('ResizeObserver loop completed with undelivered notifications')) {
          return // 静默忽略这个错误
        }
        originalError.apply(console, args)
      }
    })
    
    // 组件卸载时清理
    onUnmounted(() => {
      // 清理定时器
      if (tableUpdateTimer) {
        clearTimeout(tableUpdateTimer)
        tableUpdateTimer = null
      }
      
      // 恢复原始的console.error
      console.error = originalError
    })
    
    // 获取统计数据
    const fetchStatistics = async () => {
      statsLoading.value = true
      try {
        const params = {}
        if (statsQuery.farm_code) {
          params.farm_code = statsQuery.farm_code
        }
        if (statsQuery.month) {
          params.month = statsQuery.month
        }

        const response = await axios.get('/api/report/statistics', { params })
        
        // 设置今日统计
        dailyStats.value = response.data.today_stats || { completeness_rate: null, timeliness_rate: null }
        
        // 设置月度统计
        monthlyStats.value = response.data.monthly_summary || { completeness_rate: null, timeliness_rate: null }
        
        // 设置每日统计列表
        statistics.value = response.data.daily_stats || []

      } catch (error) {
        console.error('获取统计数据失败:', error)
        ElMessage.error('获取统计数据失败')
        // Clear data on error
        statistics.value = []
        dailyStats.value = { completeness_rate: null, timeliness_rate: null }
        monthlyStats.value = { completeness_rate: null, timeliness_rate: null }
      } finally {
        statsLoading.value = false
      }
    }
    
    // 格式化比率显示
    const formatRate = (rate, showUnit = true) => {
      if (rate === null || typeof rate === 'undefined') {
        return 'N/A'
      }
      const fixedRate = Number(rate).toFixed(2)
      return showUnit ? `${fixedRate}%` : fixedRate
    }

    // 根据比率获取颜色
    const getRateColor = (rate) => {
      if (rate === null || typeof rate === 'undefined') {
        return ''
      }
      if (rate >= 99) {
        return 'rate-high'
      }
      if (rate >= 95) {
        return 'rate-mid'
      }
      return 'rate-low'
    }
    
    // 根据场站编码获取场站名称
    const getFarmNameFromCode = (farmCode) => {
      if (!farmCode) {
        return '全部场站'
      }
      const farm = windFarms.value.find(f => f.farm_code === farmCode)
      return farm ? farm.farm_name : farmCode
    }
    
    return {
      // 数据
      windFarms,
      reportConfigs,
      reportLogs,
      farmsLoading,
      configsLoading,
      logsLoading,
      selectedFarmId,
      
      // 调度器相关
      schedulerStatus,
      schedulerLoading,
      
      // 上报数据质量统计
      statsLoading,
      statsQuery,
      statistics,
      dailyStats,
      monthlyStats,

      // 场站对话框
      farmDialogVisible,
      farmDialogTitle,
      farmForm,
      farmRules,
      farmSaving,
      
      // 配置对话框
      configDialogVisible,
      configDialogTitle,
      configForm,
      configRules,
      configSaving,
      
      // 日志查询
      logQuery,
      logPagination,
      logDetailVisible,
      currentLog,
      
      // 预览相关
      previewDialogVisible,
      previewData,
      previewLoading,
      editableData,
      showRawData,
      editableDataJson,
      
      // 分页相关
      currentPage,
      pageSize,
      totalRows,
      allEditableData,
      isPaginated,
      
      // 方法
      fetchFarms,
      fetchConfigs,
      fetchLogs,
      fetchSchedulerStatus,
      fetchStatistics,
      startScheduler,
      stopScheduler,
      refreshSchedulerStatus,
      showAddFarmDialog,
      editFarm,
      saveFarm,
      resetFarmForm,
      viewFarmConfigs,
      showAddConfigDialog,
      editConfig,
      saveConfig,
      resetConfigForm,
      handleReportTypeChange,
      toggleConfig,
      deleteConfig,
      previewReport,
      executeManualReport,
      addDataRow,
      removeDataRow,
      resetEditableData,
      updateEditableDataFromJson,
      handleJsonKeydown,
      generateLongForecastTemplate,
      generateShortForecastTemplate,
      generateActualPowerTemplate,
      generateWindSpeedTemplate,
      generateTurbinePowerTemplate,
      generateWeatherTemplate,
      generateInstalledCapacityTemplate,
      generateAvailableCapacityTemplate,
      generateTheoreticalPowerTemplate,
      generateAvailablePowerTemplate,
      getTableMaxHeight,
      getColumnWidth,
      updateCurrentPageData,
      handlePageChange,
      syncCurrentPageToAll,
      getAllDataForSubmit,
      searchLogs,
      resetLogQuery,
      refreshLogs,
      viewLogDetail,
      handleSizeChange,
      handleCurrentChange,
      
      // 工具函数
      getReportTypeName,
      getReportTypeColor,
      getStatusName,
      getStatusColor,
      formatDateTime,
      formatRate,
      getRateColor,
      handleValueChange,
      getFarmNameFromCode
    }
  }
}
</script>

<style scoped>
.report-management {
  position: relative;
  min-height: 100vh;
  padding: 20px;
  overflow: hidden;
}

/* 动态渐变背景 */
.gradient-background {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
  background-size: 400% 400%;
  animation: gradientShift 15s ease infinite;
  z-index: -1;
}

@keyframes gradientShift {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

/* 页面标题 */
.page-title {
  text-align: center;
  margin-bottom: 30px;
  color: white;
  text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.page-title h1 {
  font-size: 1.8em;
  margin-bottom: 10px;
  font-weight: 600;
}

.page-title p {
  font-size: 1em;
  opacity: 0.9;
  margin: 0;
}

/* 内容容器 */
.content-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: relative;
  z-index: 1;
}

/* 信息卡片 */
.info-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 15px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.info-card :deep(.el-card__header) {
  background: transparent;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: #333;
  flex-wrap: nowrap;
  gap: 10px;
}

.card-header i {
  margin-right: 8px;
  color: #409EFF;
}

.card-header > div {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
  min-width: 0;
  flex-shrink: 0;
}

/* 确保选择框和按钮在同一行 */
.card-header .el-select {
  min-width: 120px;
  width: auto;
}

.card-header .el-button {
  white-space: nowrap;
  flex-shrink: 0;
}

/* 查询表单 */
.query-form {
  margin-bottom: 20px;
  padding: 20px;
  background: rgba(240, 248, 255, 0.8);
  border-radius: 8px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

/* 表格样式 */
.info-card :deep(.el-table) {
  background: transparent;
}

.info-card :deep(.el-table__header) {
  background: rgba(248, 249, 250, 0.8);
}

.info-card :deep(.el-table__body tr:hover > td) {
  background-color: rgba(64, 158, 255, 0.1) !important;
}

/* 对话框样式 */
:deep(.el-dialog) {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 15px;
}

:deep(.el-dialog__header) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 15px 15px 0 0;
  margin: 0;
  padding: 20px;
}

:deep(.el-dialog__title) {
  color: white;
  font-weight: 600;
}

:deep(.el-dialog__body) {
  padding: 20px;
}

:deep(.el-dialog__footer) {
  padding: 10px 20px 20px;
  text-align: right;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.dialog-footer .el-button {
  margin-left: 0;
}

/* 表单样式优化 */
:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: #333;
}

:deep(.el-input) {
  width: 100%;
}

:deep(.el-select) {
  width: 100%;
}

:deep(.el-switch) {
  margin-top: 5px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .report-management {
    padding: 10px;
  }
  
  .page-title h1 {
    font-size: 1.5em;
  }
  
  .page-title p {
    font-size: 0.9em;
  }
  
  .card-header {
    flex-direction: column;
    gap: 10px;
  }
  
  .query-form :deep(.el-form--inline) {
    display: flex;
    flex-direction: column;
  }
  
  .query-form :deep(.el-form-item) {
    width: 100%;
    margin-right: 0;
  }
  
  /* 移动端对话框优化 */
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 5vh auto;
  }
  
  :deep(.el-dialog__header) {
    padding: 15px;
  }
  
  :deep(.el-dialog__body) {
    padding: 15px;
  }
  
  .dialog-footer {
    flex-direction: column;
    align-items: stretch;
  }
  
  .dialog-footer .el-button {
    margin-bottom: 10px;
  }
  
  .dialog-footer .el-button:last-child {
    margin-bottom: 0;
  }
}

/* 按钮和操作样式 */
.el-button--mini {
  padding: 5px 8px;
  font-size: 12px;
}

/* 全局按钮样式 - 去掉边框，文字居中 */
:deep(.el-button) {
  border: none !important;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  text-align: center;
  padding: 8px 16px;
  gap: 6px; /* 图标和文字之间的间隙 */
}

:deep(.el-button:hover) {
  border: none !important;
}

:deep(.el-button:focus) {
  border: none !important;
}

:deep(.el-button:active) {
  border: none !important;
}

:deep(.el-button.is-plain) {
  border: none !important;
}

:deep(.el-button.is-plain:hover) {
  border: none !important;
}

:deep(.el-button.is-plain:focus) {
  border: none !important;
}

:deep(.el-button.is-plain:active) {
  border: none !important;
}

/* 按钮组样式 */
:deep(.el-button-group .el-button) {
  border: none !important;
}

:deep(.el-button-group .el-button:hover) {
  border: none !important;
}

:deep(.el-button-group .el-button:focus) {
  border: none !important;
}

:deep(.el-button-group .el-button:active) {
  border: none !important;
}

/* 小按钮样式 */
:deep(.el-button--small) {
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  border: none !important;
  padding: 6px 12px;
  gap: 4px;
  min-height: 28px;
}

:deep(.el-button--mini) {
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  border: none !important;
  padding: 4px 8px;
  gap: 3px;
  min-height: 24px;
}

/* 按钮内图标样式 */
:deep(.el-button i) {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

:deep(.el-button .el-icon) {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* 调度器控制按钮特殊样式 */
.scheduler-controls .el-button {
  min-width: 70px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px 12px;
}

/* 统计查询按钮样式 */
.stats-controls .el-button {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 4px !important;
  padding: 6px 12px !important;
  min-height: 28px !important;
  border: none !important;
  text-align: center !important;
  line-height: 1 !important;
}

/* 强制覆盖统计区域的查询按钮样式 */
.stats-controls :deep(.el-button) {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 4px !important;
  padding: 6px 12px !important;
  min-height: 28px !important;
  border: none !important;
  text-align: center !important;
  line-height: 1 !important;
  box-sizing: border-box !important;
}

.stats-controls :deep(.el-button i) {
  margin: 0 !important;
  line-height: 1 !important;
}

/* 卡片头部按钮样式 */
.card-header .el-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px 12px;
  min-height: 28px;
}

/* 确保所有按钮内容垂直居中 */
:deep(.el-button span) {
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* 强制按钮内容居中 */
:deep(.el-button) {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

:deep(.el-button--small) {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

:deep(.el-button--mini) {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

/* 按钮loading状态样式 */
:deep(.el-button.is-loading) {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

/* 移除Element Plus默认的边距和填充 */
:deep(.el-button > *) {
  margin: 0;
  vertical-align: middle;
}

/* 确保图标和文字在同一行 */
:deep(.el-button .el-icon + span),
:deep(.el-button i + span) {
  margin-left: 4px;
}

/* 处理只有图标的按钮 */
:deep(.el-button .el-icon:only-child),
:deep(.el-button i:only-child) {
  margin: 0;
}

/* Element Plus icon属性按钮特殊处理 */
:deep(.el-button[class*="el-icon-"]) {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 6px 12px !important;
  gap: 6px !important;
}

:deep(.el-button[class*="el-icon-"]:before) {
  margin-right: 6px;
  line-height: 1;
  vertical-align: middle;
}

/* 统计查询按钮特别处理 */
.stats-controls .el-button[class*="el-icon-"] {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 6px 12px !important;
  min-height: 28px !important;
  gap: 6px !important;
}

/* 强制所有按钮内容居中 - 更强的选择器 */
:deep(.el-button),
:deep(.el-button--primary),
:deep(.el-button--success),
:deep(.el-button--warning),
:deep(.el-button--danger),
:deep(.el-button--info) {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center !important;
}

:deep(.el-button--small),
:deep(.el-button--mini) {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center !important;
}

/* 状态标签样式 */
.el-tag {
  font-weight: 500;
}

/* 分页样式 */
:deep(.el-pagination) {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  :deep(.el-pagination) {
    justify-content: center;
  }
  
  :deep(.el-pagination .el-pager li) {
    min-width: 30px;
    height: 30px;
    line-height: 30px;
  }
}

/* 操作按钮样式优化 */
.action-buttons {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: nowrap;
  justify-content: center;
  padding: 4px 0;
}

.action-btn {
  margin: 0 !important;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 12px;
  min-width: 60px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: all 0.3s ease;
  border: none !important;
  white-space: nowrap;
  line-height: 1;
  box-sizing: border-box;
}

.action-btn .el-icon {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.action-btn i {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* 编辑按钮特殊样式 - 白色字体，无边框 */
.action-btn.el-button--primary.is-plain {
  color: #fff !important;
  border: none !important;
  background-color: rgba(255, 255, 255, 0.1) !important;
}

.action-btn.el-button--primary.is-plain:hover {
  color: #fff !important;
  background-color: rgba(255, 255, 255, 0.2) !important;
  border: none !important;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

/* 上报按钮样式 */
.action-btn.el-button--warning.is-plain:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(230, 162, 60, 0.3);
  border: none !important;
}

/* 删除按钮样式 */
.action-btn.el-button--danger.is-plain:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(245, 108, 108, 0.3);
  border: none !important;
}

.action-btn .el-icon {
  font-size: 12px;
  margin-right: 0;
}

.action-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

/* 响应式按钮样式 */
@media (max-width: 768px) {
  .action-buttons {
    flex-direction: column;
    gap: 4px;
    align-items: stretch;
  }
  
  .action-btn {
    width: 100%;
    justify-content: center;
    font-size: 11px;
    padding: 5px 8px;
    height: 26px;
  }
}

/* 日志查询头部样式 */
.log-header {
  flex-direction: column !important;
  align-items: flex-start !important;
  gap: 15px !important;
}

.log-query-section {
  width: 100%;
}

.header-form {
  margin: 0;
}

.header-form :deep(.el-form-item) {
  margin-bottom: 0;
  margin-right: 15px;
}

.header-form :deep(.el-form-item__label) {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}

.header-form .el-select {
  width: 120px;
}

.header-form .el-date-picker {
  width: 280px;
}

/* 响应式日志查询 */
@media (max-width: 1200px) {
  .log-header {
    flex-direction: column !important;
  }
  
  .header-form :deep(.el-form--inline .el-form-item) {
    display: block;
    margin-right: 0;
    margin-bottom: 10px;
  }
  
  .header-form .el-select,
  .header-form .el-date-picker {
    width: 100%;
  }
}

/* 调度器状态卡片样式 */
.scheduler-status-card {
  margin-bottom: 20px;
}

.scheduler-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
}

.scheduler-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 15px;
  padding: 10px 0;
}

.scheduler-info .info-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
}

.scheduler-info .info-label {
  font-weight: 500;
  color: #666;
  min-width: 80px;
  margin-right: 10px;
}

.scheduler-info .info-value {
  color: #333;
  flex: 1;
}

/* 响应式调度器状态 */
@media (max-width: 768px) {
  .scheduler-controls {
    flex-wrap: wrap;
    gap: 5px;
  }
  
  .scheduler-info {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  
  .scheduler-info .info-item {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .scheduler-info .info-label {
    min-width: auto;
    margin-right: 0;
    margin-bottom: 5px;
  }
}

/* 预览对话框样式 */
.preview-card {
  margin-bottom: 15px;
}

.preview-section-title {
  font-weight: 600;
  color: #409EFF;
  font-size: 16px;
}

.preview-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  flex-wrap: wrap;
  gap: 10px;
}

.preview-controls {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
}

.preview-card :deep(.el-card__header) {
  padding: 12px 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  border-bottom: 1px solid #e4e7ed;
}

.preview-card :deep(.el-card__body) {
  padding: 15px 20px;
}

/* 表格编辑样式 */
.preview-card :deep(.el-table) {
  border-radius: 6px;
  overflow: hidden;
}

.preview-card :deep(.el-input-number) {
  width: 100%;
}

.preview-card :deep(.el-date-editor) {
  width: 100%;
}

/* 批量编辑提示 */
.bulk-edit-tip {
  margin-top: 15px;
}

/* 分页相关样式 */
.pagination-container {
  margin-top: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}

.pagination-info {
  font-size: 12px;
  color: #666;
  font-weight: normal;
  margin-left: 10px;
}

.page-tips {
  width: 100%;
  max-width: 600px;
}

/* 固定列样式 */
.preview-card :deep(.el-table__fixed) {
  box-shadow: 2px 0 6px -1px rgba(0, 0, 0, 0.1);
}

.preview-card :deep(.el-table__fixed-right) {
  box-shadow: -2px 0 6px -1px rgba(0, 0, 0, 0.1);
}

/* 长期预测提示样式 */
.forecast-long-tip {
  display: flex;
  align-items: center;
  margin-left: 10px;
}

/* 长期预测指导说明 */
.forecast-long-guide {
  margin-bottom: 15px;
}

.forecast-long-guide p {
  margin: 5px 0;
  font-size: 13px;
  line-height: 1.4;
}

/* JSON操作按钮 */
.json-actions {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  padding: 10px 0;
  border-top: 1px solid #e4e7ed;
  margin-top: 10px !important;
}

/* 响应式预览对话框 */
@media (max-width: 768px) {
  .preview-section-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .preview-controls {
    width: 100%;
    justify-content: flex-start;
  }
  
  .forecast-long-tip {
    margin-left: 0;
    margin-top: 10px;
  }
  
  /* 移动端隐藏部分列 */
  .preview-card :deep(.el-table__column--hidden) {
    display: none;
  }
}

/* 数据质量统计卡片样式 */
.stats-summary {
  text-align: center;
}

.stat-box {
  padding: 15px;
  background-color: #f9fafb;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.stat-box:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 10px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  font-family: 'DIN Alternate', 'Helvetica Neue', Arial, sans-serif;
}

.rate-high {
  color: #67C23A; /* Success */
}

.rate-mid {
  color: #E6A23C; /* Warning */
}

.rate-low {
  color: #F56C6C; /* Danger */
}

/* 分类型统计样式 */
.type-stats-container {
  display: flex;
  flex-direction: column;
  gap: 8px; /* 增加行间距 */
  min-height: 40px;
  width: 100%;
  padding: 4px 0;
  justify-content: center; /* 垂直居中 */
}

.type-stat-item {
  display: flex;
  align-items: center; /* 垂直对齐 */
  gap: 12px; /* 增加元素间距 */
  width: 100%;
}

.type-tag {
  flex-shrink: 0;
  margin: 0 !important;
  width: 90px; /* 固定标签宽度 */
  text-align: center;
}

.stat-text {
  font-size: 12px;
  white-space: nowrap;
  color: #606266;
}

.stat-text span {
  font-weight: 600;
  margin-left: 4px;
}

.no-data {
  color: #909399;
  font-size: 12px;
  text-align: center;
  padding: 10px 0;
}

/* 日志查询控件统一样式 */
.log-query-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.log-query-form {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.log-query-form .el-form-item {
  margin: 0 !important;
}

/* 响应式日志查询 */
@media (max-width: 1200px) {
  .log-query-controls {
    flex-wrap: wrap;
    width: 100%;
  }
  .log-query-form {
    flex-wrap: wrap;
    width: 100%;
  }
}
</style> 