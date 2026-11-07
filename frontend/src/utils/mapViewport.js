export const clampZoom = value => Math.min(4, Math.max(1, Number.isFinite(value) ? value : 1));

export function fitMapSize(width, height, aspectRatio) {
  const availableWidth = Math.max(1, width - 24);
  const availableHeight = Math.max(1, height - 24);
  const ratio = aspectRatio > 0 && Number.isFinite(aspectRatio) ? aspectRatio : 1.6;
  const fittedWidth = Math.min(availableWidth, availableHeight * ratio);
  return { width: fittedWidth, height: fittedWidth / ratio };
}

export function anchorScroll(offset, fraction, size, screenPosition) {
  return offset + fraction * size - screenPosition;
}
