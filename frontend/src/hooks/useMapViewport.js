import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { anchorScroll, clampZoom, fitMapSize } from '../utils/mapViewport';

// Zoom changes only the rendered image/overlay size, never routing coordinates.
export default function useMapViewport(aspectRatio) {
  const viewportRef = useRef(null);
  const canvasRef = useRef(null);
  const [size, setSize] = useState({ width: 1, height: 1 });
  const [zoom, setZoom] = useState(1);
  const zoomRef = useRef(1);
  const anchor = useRef(null);
  const pointers = useRef(new Map());
  const gesture = useRef(null);
  const moved = useRef(false);

  useEffect(() => {
    const element = viewportRef.current;
    const observer = new ResizeObserver(() => setSize(fitMapSize(element.clientWidth, element.clientHeight, aspectRatio)));
    observer.observe(element);
    return () => observer.disconnect();
  }, [aspectRatio]);

  const zoomAt = useCallback((value, clientX, clientY) => {
    const viewport = viewportRef.current, canvas = canvasRef.current;
    if (!viewport || !canvas) return;
    const next = clampZoom(value);
    const frame = viewport.getBoundingClientRect(), image = canvas.getBoundingClientRect();
    const x = clientX ?? frame.left + frame.width / 2;
    const y = clientY ?? frame.top + frame.height / 2;
    anchor.current = { u: (x - image.left) / image.width, v: (y - image.top) / image.height,
                       x: x - frame.left, y: y - frame.top };
    zoomRef.current = next;
    setZoom(next);
  }, []);

  useLayoutEffect(() => {
    const point = anchor.current, viewport = viewportRef.current, canvas = canvasRef.current;
    if (!point || !viewport || !canvas) return;
    viewport.scrollLeft = anchorScroll(canvas.offsetLeft, point.u, canvas.offsetWidth, point.x);
    viewport.scrollTop = anchorScroll(canvas.offsetTop, point.v, canvas.offsetHeight, point.y);
    anchor.current = null;
  }, [zoom, size]);

  const reset = useCallback(() => {
    zoomRef.current = 1; anchor.current = null; setZoom(1);
    viewportRef.current?.scrollTo({ left: 0, top: 0 });
  }, []);

  const begin = event => {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    if (!pointers.current.size) moved.current = false;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const values = [...pointers.current.values()];
    gesture.current = values.length === 2
      ? { distance: Math.hypot(values[0].x - values[1].x, values[0].y - values[1].y), zoom: zoomRef.current }
      : { x: event.clientX, y: event.clientY, left: viewportRef.current.scrollLeft, top: viewportRef.current.scrollTop };
    if (values.length > 1) moved.current = true;
  };
  const move = event => {
    if (!pointers.current.has(event.pointerId)) return;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const values = [...pointers.current.values()], start = gesture.current;
    if (values.length === 2 && start?.distance) {
      moved.current = true;
      zoomAt(start.zoom * Math.hypot(values[0].x - values[1].x, values[0].y - values[1].y) / start.distance,
             (values[0].x + values[1].x) / 2, (values[0].y + values[1].y) / 2);
    } else if (values.length === 1 && start && !start.distance) {
      const dx = event.clientX - start.x, dy = event.clientY - start.y;
      if (Math.hypot(dx, dy) > 6) {
        moved.current = true;
        // Touch already has implicit capture on its original target. Moving
        // that capture to the viewport can disrupt the following tap gesture.
        if (event.pointerType === 'mouse') event.currentTarget.setPointerCapture(event.pointerId);
        event.currentTarget.scrollLeft = start.left - dx;
        event.currentTarget.scrollTop = start.top - dy;
      }
    }
  };
  const end = event => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    pointers.current.delete(event.pointerId);
    const point = [...pointers.current.values()][0];
    gesture.current = point ? { ...point, left: viewportRef.current.scrollLeft, top: viewportRef.current.scrollTop } : null;
  };
  const keyDown = event => {
    if (event.target !== event.currentTarget) return;
    if (['+', '=', '-'].includes(event.key)) { event.preventDefault(); zoomAt(zoomRef.current + (event.key === '-' ? -.5 : .5)); }
    if (event.key === '0') { event.preventDefault(); reset(); }
  };

  return { viewportRef, canvasRef, zoom, size, moved, zoomAt, reset,
    handlers: { onPointerDown: begin, onPointerMove: move, onPointerUp: end, onPointerCancel: end, onKeyDown: keyDown } };
}
