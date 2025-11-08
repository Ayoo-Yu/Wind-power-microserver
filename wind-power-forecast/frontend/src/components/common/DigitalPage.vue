<template>
  <div class="digital-page">
    <div class="digital-page__background" aria-hidden="true" />
    <div class="digital-page__shell">
      <slot />
    </div>
  </div>
</template>

<script>
export default {
  name: 'DigitalPage',
}
</script>
