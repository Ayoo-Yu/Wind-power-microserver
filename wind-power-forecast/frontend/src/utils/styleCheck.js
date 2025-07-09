/**
 * 样式检查与修复工具
 * 用于解决不同环境下样式不一致问题
 */

/**
 * 检查并修复表单控件文字颜色
 * 在组件挂载后调用
 */
export function ensureFormControlsTextColor() {
  // 延迟执行，确保DOM已完全加载
  setTimeout(() => {
    const formControls = document.querySelectorAll('input, textarea, .el-input__inner, .el-textarea__inner, .el-select input, .el-date-picker input');
    formControls.forEach(element => {
      const computedStyle = window.getComputedStyle(element);
      const color = computedStyle.getPropertyValue('color');
      const backgroundColor = computedStyle.getPropertyValue('background-color');
      
      // 检测文字是否为白色或浅色，并且背景也是白色（导致文字不可见）
      if ((color.includes('255, 255, 255') || color.includes('rgb(255,') || 
           color.includes('#fff') || color.includes('#FFF')) && 
          (backgroundColor.includes('255, 255, 255') || backgroundColor.includes('rgb(255,') || 
           backgroundColor.includes('#fff') || backgroundColor.includes('#FFF'))) {
        console.log('检测到不可见文字，正在修复:', element);
        element.style.color = '#333 !important';
        
        // 尝试设置输入框的子元素文字颜色
        const inputElements = element.querySelectorAll('input');
        inputElements.forEach(input => {
          input.style.color = '#333 !important';
        });
      }
    });
    
    // 强制应用样式到Element Plus组件
    const style = document.createElement('style');
    style.innerHTML = `
      .el-input__inner, 
      .el-textarea__inner,
      .el-select-dropdown__item,
      .el-date-editor .el-input__inner,
      .el-date-editor .el-range-input,
      .el-date-picker input,
      .el-input input,
      .el-select input {
        color: #333 !important;
      }
    `;
    document.head.appendChild(style);
    
    console.log('表单控件文字颜色检查完成');
  }, 500);
}

export default {
  ensureFormControlsTextColor
}; 