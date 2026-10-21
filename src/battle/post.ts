// Post-processing via pmndrs/postprocessing: HDR bloom, AgX tone mapping, a light painterly grade,
// vignette, impact flash and chromatic aberration. Lower quality tiers drop the costly passes.
import * as THREE from 'three';
import { clamp, lerp } from './util';
import {
  EffectComposer, RenderPass, EffectPass, BloomEffect, ChromaticAberrationEffect, VignetteEffect, ToneMappingEffect, ToneMappingMode,
  HueSaturationEffect, BrightnessContrastEffect, Effect, BlendFunction, KernelSize,
} from 'postprocessing';

class FlashEffect extends Effect {
  constructor() {
    super('FlashEffect', `uniform float amount; uniform vec3 tint;
      void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor){
        vec2 d = uv - .5; float edge = smoothstep(.2, .8, length(d));
        outputColor = vec4(mix(inputColor.rgb, tint, amount * (.55 + .45 * edge)), inputColor.a); }`,
    { blendFunction: BlendFunction.NORMAL, uniforms: new Map<string, THREE.Uniform>([['amount', new THREE.Uniform(0)], ['tint', new THREE.Uniform(new THREE.Color(1, 1, 1))]]) });
  }
}

export interface Post { composer: EffectComposer; flash(amount: number, color?: THREE.ColorRepresentation): void; aberrate(amount: number): void; desaturate(amount: number): void; update(dt: number): void; setSize(w: number, h: number): void; dispose(): void }

export function buildPost(renderer: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.PerspectiveCamera, quality: number, reduced: boolean): Post {
  renderer.toneMapping = THREE.NoToneMapping;
  const composer = new EffectComposer(renderer, { frameBufferType: THREE.HalfFloatType, multisampling: quality >= 2 ? 4 : quality === 1 ? 2 : 0 });
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new BloomEffect({ intensity: 1.15, luminanceThreshold: .92, luminanceSmoothing: .25, mipmapBlur: true, radius: .72, kernelSize: KernelSize.LARGE });
  const tone = new ToneMappingEffect({ mode: ToneMappingMode.AGX });
  const sat = new HueSaturationEffect({ saturation: .16 });
  const contrast = new BrightnessContrastEffect({ brightness: .02, contrast: .1 });
  const vignette = new VignetteEffect({ darkness: .42, offset: .32 });
  const flash = new FlashEffect();
  const aberration = new ChromaticAberrationEffect({ offset: new THREE.Vector2(0, 0), radialModulation: true, modulationOffset: .25 });
  composer.addPass(new EffectPass(camera, ...(quality >= 1 ? [bloom] : []), tone, sat, contrast));
  composer.addPass(new EffectPass(camera, ...(quality >= 1 && !reduced ? [aberration] : []), vignette, flash));
  let flashAmt = 0, ab = 0;
  const flashTint = flash.uniforms.get('tint')!.value as THREE.Color;
  return {
    composer,
    flash(amount, color = 0xffffff) { flashAmt = Math.max(flashAmt, amount * (reduced ? .3 : 1)); flashTint.set(color).lerp(new THREE.Color(1, 1, 1), .5); },
    aberrate(amount) { ab = Math.min(.012, Math.max(ab, amount)); },
    /** 0 = the normal grade, 1 = drained of colour (defeat). */
    desaturate(amount) { sat.saturation = lerp(.16, -.85, clamp(amount, 0, 1)); },
    update(dt) {
      flashAmt = Math.max(0, flashAmt - dt * 3.2);
      ab = Math.max(0, ab - dt * .04);
      flash.uniforms.get('amount')!.value = flashAmt;
      aberration.offset.set(ab, ab * .6);
    },
    setSize(w, h) { composer.setSize(w, h); },
    dispose() { composer.dispose(); },
  };
}
