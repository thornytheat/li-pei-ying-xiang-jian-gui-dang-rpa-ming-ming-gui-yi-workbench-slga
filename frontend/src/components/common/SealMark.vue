<template>
  <span class="seal" :class="[`seal--${tone}`, size === 'sm' ? 'seal--sm' : '']" aria-hidden="true">
    <span class="seal__ring"></span>
    <span class="seal__text">{{ text }}</span>
  </span>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ text: string; tone?: 'red' | 'blue' | 'green'; size?: 'sm' | 'md' }>(), {
  tone: 'red',
  size: 'md',
})
</script>

<style scoped>
.seal {
  position: relative;
  display: inline-grid;
  place-items: center;
  width: 92px;
  height: 92px;
  border-radius: 50%;
  border: 2px solid currentColor;
  color: var(--seal-red);
  transform: rotate(-8deg);
  font-family: var(--font-serif);
  letter-spacing: 0.18em;
  opacity: 0.82;
  flex: none;
}

.seal--sm {
  width: 58px;
  height: 58px;
  font-size: 0.5rem;
  letter-spacing: 0.1em;
}

.seal--blue {
  color: var(--seal-blue);
}
.seal--green {
  color: var(--seal-green);
}

.seal__ring {
  position: absolute;
  inset: 5px;
  border: 1px solid currentColor;
  border-radius: 50%;
  opacity: 0.6;
}

.seal__text {
  font-size: 0.62rem;
  line-height: 1.3;
  text-align: center;
  padding: 0 8px;
  writing-mode: horizontal-tb;
}

.seal--sm .seal__text {
  font-size: 0.46rem;
  padding: 0 4px;
}
</style>
