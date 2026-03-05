export const PERMISSION_TREE = [
  {
    id: 'menu_dashboard',
    label: '首页看板',
    children: [
      { id: 'view_dashboard', label: '查看首页看板' },
      { id: 'view_all_data', label: '查看全场站数据' }
    ]
  },
  {
    id: 'menu_predict',
    label: '预测与调整',
    children: [
      { id: 'auto_predictions', label: '自动预测页面' },
      { id: 'modify_prediction_curve', label: '修改预测曲线' },
      { id: 'manual_intervention_workspace', label: '人工修正工作台' }
    ]
  },
  {
    id: 'menu_report',
    label: '上报与报表',
    children: [
      { id: 'manual_report', label: '手动上报' },
      { id: 'manage_reports', label: '上报管理' },
      { id: 'export_reports', label: '导出报表' },
      { id: 'view_accuracy_report', label: '准确率考核报表' }
    ]
  },
  {
    id: 'menu_ops_quality',
    label: '运维与质量',
    children: [
      { id: 'view_alarm_center', label: '统一告警中心' },
      { id: 'manage_data_quality', label: '数据质量与限电标记' }
    ]
  },
  {
    id: 'menu_system',
    label: '系统与配置',
    children: [
      { id: 'manage_weather_data', label: '气象数据管理' },
      { id: 'manage_tasks', label: '任务管理' },
      { id: 'system_maintenance', label: '系统维护' },
      { id: 'manage_system_settings', label: '系统基础配置' }
    ]
  },
  {
    id: 'menu_user',
    label: '用户与权限',
    children: [
      { id: 'manage_users', label: '用户列表管理' },
      { id: 'manage_roles', label: '角色管理' },
      { id: 'view_audit_logs', label: '查看操作日志' }
    ]
  }
]

export const ALL_PERMISSION_KEYS = PERMISSION_TREE.flatMap(group => group.children.map(item => item.id))

export const ROLE_PRESETS = [
  {
    key: 'sys_admin',
    name: '系统管理员',
    description: '全权限，可管理用户、角色和系统配置',
    permissions: [...ALL_PERMISSION_KEYS]
  },
  {
    key: 'operator',
    name: '运行值班员',
    description: '可查看数据、修改预测曲线并执行手动上报',
    permissions: [
      'view_dashboard',
      'view_all_data',
      'auto_predictions',
      'modify_prediction_curve',
      'manual_intervention_workspace',
      'manual_report',
      'manage_reports',
      'view_accuracy_report',
      'view_alarm_center',
      'manage_data_quality'
    ]
  },
  {
    key: 'viewer',
    name: '浏览者/领导',
    description: '仅查看看板与关键数据，无操作权限',
    permissions: [
      'view_dashboard',
      'view_all_data'
    ]
  }
]
