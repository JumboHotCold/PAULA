import test from 'node:test';
import assert from 'node:assert/strict';
import { clampZoom, fitMapSize, anchorScroll } from './mapViewport.js';

test('map fits portrait, landscape and desktop bounds without stretching coordinates', () => {
  for (const [width,height] of [[312,180],[367,340],[514,220],[900,600]]) {
    const fit=fitMapSize(width,height,1.6);
    assert.ok(fit.width<=width-24 && fit.height<=height-24);
    assert.ok(Math.abs(fit.width/fit.height-1.6)<1e-9);
  }
});
test('zoom is bounded and invalid dimensions remain finite', () => {
  assert.equal(clampZoom(.2),1);assert.equal(clampZoom(10),4);assert.equal(clampZoom(NaN),1);
  assert.deepEqual(fitMapSize(0,0,0),{width:1,height:.625});
});
test('zoom anchoring retains the same map point under the gesture center', () => {
  const scroll=anchorScroll(12,.4,1000,150);
  assert.equal(12+.4*1000-scroll,150);
});
