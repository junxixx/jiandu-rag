<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

type LoadedGltf = {
  scene: THREE.Object3D;
  animations: THREE.AnimationClip[];
};

type AvatarPose = "idle" | "thinking" | "speaking";

const props = withDefaults(
  defineProps<{
    roleKey: string;
    accent: string;
    enabled: boolean;
    /** 为 true 时高度随父容器（用于左侧角色卡与 2D 立绘同槽位） */
    fillContainer?: boolean;
    /** 对话节奏：待机 / 等待回复 / 答问中（可驱动 GLB 多片段或叠加微动） */
    avatarPose?: AvatarPose;
  }>(),
  {
    accent: "#8b6914",
    enabled: true,
    fillContainer: false,
    avatarPose: "idle",
  }
);

const wrapRef = ref<HTMLDivElement | null>(null);
const modelLoading = ref(true);
let mountGeneration = 0;
let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
/** 含地面 + 人物（或 GLB） */
let root: THREE.Object3D | null = null;
let mixer: THREE.AnimationMixer | null = null;
/** 当前 GLB 内全部动画片段（用于按姿态切换） */
let gltfAnimationClips: THREE.AnimationClip[] = [];
let currentPoseAction: THREE.AnimationAction | null = null;
let raf = 0;
let clock = new THREE.Clock();
let groundMesh: THREE.Mesh | null = null;
const cachedFitSize = new THREE.Vector3(1, 1.6, 0.5);
let cachedFitScale = 1;

function isLiGanStrict(): boolean {
  return props.roleKey === "li_gan";
}

function firstMatchingClip(clips: THREE.AnimationClip[], patterns: RegExp[]): THREE.AnimationClip | null {
  for (const re of patterns) {
    const c = clips.find((x) => re.test(x.name));
    if (c) return c;
  }
  return null;
}

function clipForMood(clips: THREE.AnimationClip[], mood: AvatarPose): THREE.AnimationClip | null {
  if (!clips.length) return null;
  if (mood === "thinking") {
    return (
      firstMatchingClip(clips, [
        /think|ponder|worry|consider/i,
        /疑惑|思考|想|沉|凝|默|斟酌|寻思|忖|考虑|琢磨|迟疑/i,
      ]) ??
      firstMatchingClip(clips, [/idle|stand|breath|loop|默认|待機|待机|休闲|站立|平常|静止/i]) ??
      clips[0]
    );
  }
  if (mood === "speaking") {
    return (
      firstMatchingClip(clips, [
        /talk|speak|gesture|chat|mouth|lip/i,
        /说话|言|答|讲|谈|诉|论|开口|演讲|对白|陈述|讲解/i,
      ]) ??
      firstMatchingClip(clips, [/idle|stand|breath|loop|待机|站立/i]) ??
      clips[0]
    );
  }
  return (
    firstMatchingClip(clips, [
      /idle|stand|breath|loop|rest|pose|t-?pose/i,
      /默认|待機|待机|休闲|站立|站姿|平常|静止|基础/i,
    ]) ??
    clips[0]
  );
}

/**
 * 李敢（li_gan）：待机时骨骼停在首帧，仅在对话态播放片段。
 * 其余角色：待机照常循环 Idle，保持「自己会动」。
 */
function playAvatarPose(mood: AvatarPose) {
  if (!mixer || !gltfAnimationClips.length) return;

  if (mood === "idle" && isLiGanStrict()) {
    const clip = clipForMood(gltfAnimationClips, "idle") ?? gltfAnimationClips[0];
    if (!clip) return;
    const rest = mixer.clipAction(clip);
    if (currentPoseAction === rest && rest.paused && rest.time <= 0.02) return;

    mixer.stopAllAction();
    rest.stop();
    rest.reset();
    rest.time = 0;
    rest.setLoop(THREE.LoopRepeat, Infinity);
    rest.enabled = true;
    rest.weight = 1;
    rest.play();
    rest.paused = true;
    currentPoseAction = rest;
    mixer.update(0);
    return;
  }

  if (mood === "idle" && !isLiGanStrict()) {
    const clip = clipForMood(gltfAnimationClips, "idle") ?? gltfAnimationClips[0];
    if (!clip) return;
    const next = mixer.clipAction(clip);
    const fade = 0.38;
    next.paused = false;
    next.setLoop(THREE.LoopRepeat, Infinity);
    next.reset();
    if (!currentPoseAction) {
      next.play();
      currentPoseAction = next;
      return;
    }
    if (currentPoseAction.getClip() === clip) {
      currentPoseAction.paused = false;
      if (!currentPoseAction.isRunning()) currentPoseAction.play();
      return;
    }
    currentPoseAction.paused = false;
    next.play();
    currentPoseAction.crossFadeTo(next, fade, false);
    currentPoseAction = next;
    return;
  }

  const clip = clipForMood(gltfAnimationClips, mood);
  if (!clip) return;
  const next = mixer.clipAction(clip);
  const fade = 0.4;
  next.paused = false;
  next.setLoop(THREE.LoopRepeat, Infinity);
  next.clampWhenFinished = false;
  next.reset();

  if (!currentPoseAction) {
    next.play();
    currentPoseAction = next;
    return;
  }
  if (currentPoseAction.getClip() === clip) {
    currentPoseAction.paused = false;
    currentPoseAction.reset();
    currentPoseAction.setLoop(THREE.LoopRepeat, Infinity);
    currentPoseAction.play();
    return;
  }
  currentPoseAction.paused = false;
  next.play();
  currentPoseAction.crossFadeTo(next, fade, false);
  currentPoseAction = next;
}

/** 按包围盒自动拉远相机，保证全身与宽道具（如旗）尽量入画 */
function fitCameraToBounds(cam: THREE.PerspectiveCamera, modelSize: THREE.Vector3, scale: number) {
  const h = modelSize.y * scale;
  const w = modelSize.x * scale;
  const zDepth = modelSize.z * scale;
  const fovV = THREE.MathUtils.degToRad(cam.fov);
  const aspect = Math.max(cam.aspect, 0.42);
  const padV = 1.28;
  const padH = 1.24;
  const distV = (h * padV) / (2 * Math.tan(fovV / 2));
  const tanHalfH = Math.tan(fovV / 2) * aspect;
  const distH = (w * padH) / (2 * tanHalfH);
  let dist = Math.max(distV, distH, zDepth * 0.62 + 1.35, 2.5);
  dist = Math.min(dist, 22);
  const lookY = h * 0.45;
  const camY = THREE.MathUtils.clamp(h * 0.33, 0.34, 1.2);
  cam.position.set(0, camY, dist);
  cam.lookAt(0, lookY, 0);
  cam.updateProjectionMatrix();
}

function applyDefaultCamera(cam: THREE.PerspectiveCamera) {
  cam.fov = 40;
  cam.position.set(0, 1.05, 2.75);
  cam.lookAt(0, 0.88, 0);
  cam.updateProjectionMatrix();
}

function parseAccent(hex: string): THREE.Color {
  try {
    return new THREE.Color(hex);
  } catch {
    return new THREE.Color("#8b6914");
  }
}

function phongRobe(color: THREE.Color): THREE.MeshPhongMaterial {
  const c = color.clone();
  return new THREE.MeshPhongMaterial({
    color: c,
    shininess: 22,
    specular: new THREE.Color(0x332218),
    emissive: c.clone().multiplyScalar(0.06),
  });
}

function phongSkin(): THREE.MeshPhongMaterial {
  return new THREE.MeshPhongMaterial({
    color: 0xe8d4bc,
    shininess: 12,
    specular: new THREE.Color(0x443322),
    emissive: 0x221810,
    emissiveIntensity: 0.08,
  });
}

function phongDark(): THREE.MeshPhongMaterial {
  return new THREE.MeshPhongMaterial({
    color: 0x2a1810,
    shininess: 8,
    specular: 0x111008,
  });
}

/**
 * 低面数「宽袍剪影」：比圆柱+球更接近汉服轮廓；按角色微调节点。
 */
function buildFallbackFigure(accent: THREE.Color, roleKey: string): THREE.Group {
  const g = new THREE.Group();
  const robe = phongRobe(accent);
  const skin = phongSkin();
  const dark = phongDark();

  const skirt = new THREE.Mesh(
    new THREE.CylinderGeometry(0.5, 0.36, 0.92, 22, 1),
    robe
  );
  skirt.position.y = 0.46;
  g.add(skirt);

  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.33, 0.4, 0.52, 16), robe);
  torso.position.y = 1.02;
  g.add(torso);

  const head = new THREE.Mesh(new THREE.SphereGeometry(0.22, 18, 14), skin);
  head.position.y = 1.32;
  head.scale.set(1, 1.05, 0.95);
  g.add(head);

  const hair = new THREE.Mesh(new THREE.SphereGeometry(0.13, 10, 8), dark);
  hair.position.set(0, 1.48, -0.02);
  hair.scale.set(1.15, 0.55, 1.05);
  g.add(hair);

  const sleeveL = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.42, 0.12), robe);
  sleeveL.position.set(-0.38, 1.05, 0.02);
  sleeveL.rotation.z = 0.35;
  const sleeveR = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.42, 0.12), robe);
  sleeveR.position.set(0.38, 1.05, 0.02);
  sleeveR.rotation.z = -0.35;
  g.add(sleeveL, sleeveR);

  if (roleKey === "shang_guan") {
    const hat = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.1, 0.36), dark);
    hat.position.set(0, 1.52, 0);
    g.add(hat);
    const hatTop = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.08, 0.28), phongRobe(new THREE.Color(0x8b6914)));
    hatTop.position.set(0, 1.58, 0);
    g.add(hatTop);
  }

  if (roleKey === "ban_chao") {
    const cloak = new THREE.Mesh(new THREE.ConeGeometry(0.62, 0.55, 12, 1, true), phongRobe(accent.clone().multiplyScalar(0.75)));
    cloak.position.set(0, 1.15, -0.18);
    cloak.rotation.x = 0.15;
    g.add(cloak);
  }

  if (roleKey === "geng_gong") {
    const strap = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.06, 0.14), phongRobe(new THREE.Color(0x6a7a88)));
    strap.position.set(0, 1.12, 0.12);
    g.add(strap);
  }

  if (roleKey === "zhang_qian") {
    const sash = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.55, 0.08), phongRobe(new THREE.Color(0xa04030)));
    sash.position.set(0.08, 0.95, 0.14);
    sash.rotation.z = -0.08;
    g.add(sash);
  }

  if (roleKey === "fu_jiezi") {
    const cap = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.2, 8), phongRobe(new THREE.Color(0xa02818)));
    cap.position.set(0, 1.55, 0);
    g.add(cap);
  }

  return g;
}

function clearScene() {
  if (raf) cancelAnimationFrame(raf);
  raf = 0;
  mixer = null;
  gltfAnimationClips = [];
  currentPoseAction = null;
  if (groundMesh && scene) {
    scene.remove(groundMesh);
    groundMesh.geometry.dispose();
    (groundMesh.material as THREE.Material).dispose();
    groundMesh = null;
  }
  if (root && scene) {
    scene.remove(root);
    root.traverse((obj: THREE.Object3D) => {
      const m = obj as THREE.Mesh;
      if (m.geometry) m.geometry.dispose();
      const mat = m.material;
      if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
      else if (mat) (mat as THREE.Material).dispose();
    });
    root = null;
  }
}

function addGround(targetScene: THREE.Scene) {
  const mat = new THREE.MeshBasicMaterial({
    color: 0xddcbb8,
    transparent: true,
    opacity: 0.42,
    depthWrite: false,
  });
  const g = new THREE.Mesh(new THREE.CircleGeometry(1.45, 56), mat);
  g.rotation.x = -Math.PI / 2;
  g.position.y = 0.002;
  targetScene.add(g);
  groundMesh = g;
}

let animT = 0;

function tick() {
  if (!renderer || !scene || !camera) return;
  const dt = clock.getDelta();
  animT += dt;
  if (mixer) mixer.update(dt);
  const mood = props.avatarPose;
  if (root) {
    if (mixer) {
      if (mood === "thinking") {
        root.position.y = Math.sin(animT * 0.95) * 0.02;
        root.rotation.z = Math.sin(animT * 0.48) * 0.03;
        root.rotation.y = Math.sin(animT * 0.35) * 0.04;
      } else if (mood === "speaking") {
        root.position.y = Math.sin(animT * 2.05) * 0.028;
        root.rotation.z = Math.sin(animT * 1.15) * 0.025;
        root.rotation.y = Math.sin(animT * 1.5) * 0.05;
      } else {
        root.position.y = 0;
        root.rotation.z = 0;
        root.rotation.y = 0;
      }
    } else {
      const inner = root.children[0];
      if (mood === "idle" && isLiGanStrict()) {
        root.position.y = 0;
        root.rotation.y = 0;
        root.rotation.z = 0;
        if (inner) inner.rotation.x = 0;
      } else if (mood === "idle") {
        const baseY = Math.sin(animT * 1.15) * 0.028;
        const rotY = 0.1 * Math.sin(animT * 0.65) + 0.06 * Math.sin(animT * 0.38);
        root.position.y = baseY;
        root.rotation.y = rotY;
        root.rotation.z = 0;
        if (inner) inner.rotation.x = 0;
      } else if (mood === "thinking") {
        const baseY = Math.sin(animT * 1.15) * 0.028 * 0.82;
        const rotY = (0.1 * Math.sin(animT * 0.65) + 0.06 * Math.sin(animT * 0.38)) * 0.5;
        const rotX = 0.14 + Math.sin(animT * 0.78) * 0.07;
        root.position.y = baseY;
        root.rotation.y = rotY;
        root.rotation.z = 0;
        if (inner) inner.rotation.x = rotX;
      } else {
        const rotX = Math.sin(animT * 2.35) * 0.09;
        const rotY = 0.1 * Math.sin(animT * 0.65) + 0.06 * Math.sin(animT * 0.38) + Math.sin(animT * 1.85) * 0.05;
        const baseY = Math.sin(animT * 1.65) * 0.036;
        root.position.y = baseY;
        root.rotation.y = rotY;
        root.rotation.z = 0;
        if (inner) inner.rotation.x = rotX;
      }
    }
  }
  renderer.render(scene, camera);
  raf = requestAnimationFrame(tick);
}

function initThree() {
  const el = wrapRef.value;
  if (!el || !props.enabled) return;

  mountGeneration += 1;
  const gen = mountGeneration;
  modelLoading.value = true;

  clearScene();
  animT = 0;
  if (renderer) {
    renderer.dispose();
    renderer = null;
  }
  el.innerHTML = "";
  clock = new THREE.Clock();

  const w = el.clientWidth || 280;
  const h = el.clientHeight || 220;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf0e4d4);

  camera = new THREE.PerspectiveCamera(40, w / h, 0.08, 120);
  applyDefaultCamera(camera);

  scene.add(new THREE.HemisphereLight(0xfff8f0, 0x8b7355, 0.58));
  const key = new THREE.DirectionalLight(0xffffff, 0.85);
  key.position.set(2.2, 4.5, 3.2);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xffeedd, 0.35);
  fill.position.set(-2.8, 2.2, 1.8);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0xc9b8a8, 0.22);
  rim.position.set(-0.5, 1.5, -3);
  scene.add(rim);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  el.appendChild(renderer.domElement);

  const accentCol = parseAccent(props.accent);
  const loader = new GLTFLoader();

  const attachStage = (obj: THREE.Object3D, clips?: THREE.AnimationClip[]) => {
    if (gen !== mountGeneration || !scene) return;
    obj.traverse((child) => {
      const mesh = child as THREE.Mesh;
      const mats = mesh.material;
      if (!mats) return;
      const list = Array.isArray(mats) ? mats : [mats];
      for (const m of list) {
        if (m instanceof THREE.MeshStandardMaterial && m.envMapIntensity < 0.2) {
          m.envMapIntensity = 0.45;
        }
      }
    });
    addGround(scene);
    root = new THREE.Group();
    root.add(obj);
    const box = new THREE.Box3().setFromObject(obj);
    const c = new THREE.Vector3();
    const size = new THREE.Vector3();
    box.getCenter(c);
    box.getSize(size);
    const scale = isLiGanStrict() ? 1.32 / Math.max(size.y, 0.001) : 1.55 / Math.max(size.y, 0.001);
    obj.scale.setScalar(scale);
    obj.position.sub(c.multiplyScalar(scale));
    obj.position.y = 0;
    scene.add(root);
    if (isLiGanStrict()) {
      cachedFitSize.copy(size);
      cachedFitScale = scale;
      fitCameraToBounds(camera, size, scale);
    } else {
      applyDefaultCamera(camera);
    }
    gltfAnimationClips = clips ?? [];
    currentPoseAction = null;
    if (gltfAnimationClips.length > 0) {
      mixer = new THREE.AnimationMixer(obj);
      playAvatarPose(props.avatarPose);
    } else {
      mixer = null;
    }
    if (gen === mountGeneration) modelLoading.value = false;
    tick();
  };

  function loadGltfUrl(url: string): Promise<LoadedGltf> {
    return new Promise((resolve, reject) => {
      loader.load(
        url,
        (gltf: LoadedGltf) => resolve(gltf),
        undefined,
        (err) => reject(err ?? new Error(url))
      );
    });
  }

  const glbCandidates = [`/models/chat/${props.roleKey}.glb`, "/models/chat/idle.glb"];

  void (async () => {
    for (const url of glbCandidates) {
      try {
        const gltf = await loadGltfUrl(url);
        if (gen !== mountGeneration || !scene) return;
        attachStage(gltf.scene, gltf.animations);
        return;
      } catch {
        continue;
      }
    }
    if (gen !== mountGeneration || !scene) return;
    const figure = buildFallbackFigure(accentCol, props.roleKey);
    attachStage(figure, undefined);
  })();
}

function onResize() {
  const el = wrapRef.value;
  if (!el || !renderer || !camera) return;
  const w = el.clientWidth || 280;
  const h = el.clientHeight || 220;
  camera.aspect = w / h;
  if (isLiGanStrict() && root && cachedFitSize.y > 0.01) {
    fitCameraToBounds(camera, cachedFitSize, cachedFitScale);
  } else {
    camera.updateProjectionMatrix();
  }
  renderer.setSize(w, h);
}

onMounted(() => {
  if (props.enabled) void nextTick(() => initThree());
  window.addEventListener("resize", onResize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", onResize);
  clearScene();
  if (renderer) {
    renderer.dispose();
    renderer.domElement.remove();
    renderer = null;
  }
  scene = null;
  camera = null;
});

watch(
  () => [props.roleKey, props.accent, props.enabled, props.fillContainer] as const,
  () => {
    if (!props.enabled) {
      modelLoading.value = false;
      clearScene();
      if (renderer) {
        renderer.dispose();
        if (wrapRef.value) wrapRef.value.innerHTML = "";
        renderer = null;
      }
      scene = null;
      camera = null;
      return;
    }
    void nextTick(() => initThree());
  }
);

watch(
  () => props.avatarPose,
  (mood) => {
    playAvatarPose(mood);
  }
);
</script>

<template>
  <div class="avatar-3d-shell" :class="{ 'avatar-3d-shell-fill': fillContainer }">
    <div
      ref="wrapRef"
      class="avatar-3d-wrap"
      :class="{ 'avatar-3d-fill': fillContainer }"
      role="img"
      :aria-label="`三维小影：${roleKey}`"
    />
    <Transition name="avatar-fade">
      <div v-if="modelLoading" class="avatar-loading-mask">
        <span class="load-pulse" aria-hidden="true" />
        <span class="avatar-loading-text">载入烽影</span>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.avatar-3d-shell {
  position: relative;
  width: 100%;
  border-radius: 12px;
}
.avatar-3d-shell-fill {
  height: 100%;
  min-height: 0;
}
.avatar-3d-shell:not(.avatar-3d-shell-fill) {
  min-height: 220px;
}
.avatar-3d-wrap {
  width: 100%;
  height: 220px;
  border-radius: 12px;
  overflow: hidden;
  background: radial-gradient(ellipse 85% 72% at 50% 32%, #fdf8f0 0%, #efe2d0 42%, #e0d0b8 100%);
  border: 1px solid rgba(120, 96, 64, 0.22);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.55),
    0 4px 20px rgba(62, 42, 24, 0.07);
}
.avatar-3d-wrap.avatar-3d-fill {
  height: 100%;
  min-height: 0;
  border-radius: 10px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.5),
    0 3px 14px rgba(62, 42, 24, 0.08);
}
.avatar-loading-mask {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: linear-gradient(165deg, rgba(253, 248, 240, 0.96) 0%, rgba(235, 222, 200, 0.93) 100%);
  border-radius: inherit;
  z-index: 4;
  pointer-events: none;
}
.avatar-loading-text {
  font-size: 11px;
  letter-spacing: 0.28em;
  color: var(--dj-ink-soft, #6b5a48);
}
.load-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dj-bamboo, #8b7355);
  animation: avatar-pulse 1.1s ease-in-out infinite;
}
@keyframes avatar-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.55;
  }
  50% {
    transform: scale(1.35);
    opacity: 1;
  }
}
.avatar-fade-enter-active,
.avatar-fade-leave-active {
  transition: opacity 0.32s ease;
}
.avatar-fade-enter-from,
.avatar-fade-leave-to {
  opacity: 0;
}
.avatar-3d-wrap :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}
</style>
