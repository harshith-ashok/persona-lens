<template>
  <div>
    <video controls width="600">
      <source src="/video.mp4" type="video/mp4" />
      Your browser does not support the video tag.
    </video>
  </div>
</template>

<script>
export default {
  name: "VideoPlayer"
}
</script>

<style scoped>
video {
  border-radius: 8px;
}
</style>