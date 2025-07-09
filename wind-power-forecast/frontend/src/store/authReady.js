import { ref } from 'vue';

// 认证状态初始化标志
export const isAuthReady = ref(false); // 标记认证流程是否已完成且成功

// 认证状态加载标志
export const isAuthLoading = ref(true); // 标记认证状态是否正在检查中 