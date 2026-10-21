// 斗法台实验场：仅供视觉验收的独立页面（游戏内不链接），按固定剧本循环演示单体斗法。
// 样式由脚本设置：服务端 CSP 不允许内联 <style>。
import { runLab } from '/arena3d.js';

const host = document.getElementById('lab');
const hud = document.getElementById('lab-hud');
const statsEl = document.getElementById('lab-stats');
Object.assign(document.documentElement.style, { height: '100%', background: '#0b1416' });
Object.assign(document.body.style, { margin: '0', height: '100%', overflow: 'hidden', fontFamily: '"Microsoft YaHei", sans-serif' });
Object.assign(host.style, { position: 'fixed', inset: '0' });
Object.assign(hud.style, { position: 'fixed', left: '14px', top: '12px', color: '#f6ebcb', textShadow: '0 1px 4px #000', pointerEvents: 'none', display: 'grid', gap: '4px', fontSize: '12px' });
hud.querySelector('b').style.font = '600 18px "KaiTi", "STKaiti", serif';

const params = new URLSearchParams(location.search);
const arena = runLab(host);
if (params.has('clean')) hud.style.display = 'none';
if (arena) setInterval(() => {
  const s = arena.stats();
  statsEl.textContent = `${s.fps} 帧/秒 · 绘制 ${s.calls} 次 · 三角形 ${(s.triangles / 1000).toFixed(0)}k · 几何体 ${s.geometries} · 纹理 ${s.textures} · 镜头 ${s.shot} · ${s.t}s`;
}, 500);
