"use client";

import * as React from "react";
import {useRef, useEffect, useState, useCallback} from "react";
import {X, Check} from "lucide-react";

interface ImageCropperProps {
  src: string;
  onComplete: (croppedDataUrl: string) => void;
  onCancel: () => void;
  aspectRatio?: number;
  cancelLabel?: string;
  applyLabel?: string;
}

export function ImageCropper({
  src,
  onComplete,
  onCancel,
  aspectRatio = 1,
  cancelLabel = "Cancel",
  applyLabel = "Apply",
}: ImageCropperProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  type CropRect = {x: number; y: number; width: number; height: number};
  type DragState =
    | {type: "move"; startX: number; startY: number; startCrop: CropRect}
    | {
        type: "resize";
        handle: "tl" | "tr" | "bl" | "br";
        startX: number;
        startY: number;
        startCrop: CropRect;
      };

  const [dragState, setDragState] = useState<DragState | null>(null);

  const [crop, setCrop] = useState({x: 0, y: 0, width: 200, height: 200});
  const [imageSize, setImageSize] = useState({width: 0, height: 0, naturalWidth: 0, naturalHeight: 0});

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;
    const updateSize = () => {
      setImageSize({
        width: img.width,
        height: img.height,
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
      });
      // Inicializar crop no centro
      const size = Math.min(img.width, img.height) * 0.8;
      setCrop({
        x: (img.width - size) / 2,
        y: (img.height - size) / 2,
        width: size,
        height: size,
      });
    };
    if (img.complete) updateSize();
    else img.onload = updateSize;
  }, [src]);

  const draw = React.useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = imageSize.width;
    canvas.height = imageSize.height;

    // Desenhar imagem original
    ctx.drawImage(img, 0, 0, imageSize.width, imageSize.height);

    // Escurecer fora do crop
    ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
    ctx.fillRect(0, 0, imageSize.width, imageSize.height);

    // Limpar área do crop
    ctx.clearRect(crop.x, crop.y, crop.width, crop.height);
    ctx.drawImage(
      img,
      crop.x * (imageSize.naturalWidth / imageSize.width),
      crop.y * (imageSize.naturalHeight / imageSize.height),
      crop.width * (imageSize.naturalWidth / imageSize.width),
      crop.height * (imageSize.naturalHeight / imageSize.height),
      crop.x,
      crop.y,
      crop.width,
      crop.height
    );

    // Borda do crop
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.strokeRect(crop.x, crop.y, crop.width, crop.height);

    // Handles de redimensionamento
    const handleSize = 12;
    const handles = [
      {x: crop.x, y: crop.y}, // top-left
      {x: crop.x + crop.width, y: crop.y}, // top-right
      {x: crop.x, y: crop.y + crop.height}, // bottom-left
      {x: crop.x + crop.width, y: crop.y + crop.height}, // bottom-right
    ];
    ctx.fillStyle = "#fff";
    handles.forEach((h) => {
      ctx.fillRect(h.x - handleSize / 2, h.y - handleSize / 2, handleSize, handleSize);
    });
  }, [crop, imageSize]);

  useEffect(() => {
    draw();
  }, [draw]);

  const getHandleAt = (x: number, y: number): "tl" | "tr" | "bl" | "br" | null => {
    const handleSize = 12;
    const handles: {type: "tl" | "tr" | "bl" | "br"; x: number; y: number}[] = [
      {type: "tl", x: crop.x, y: crop.y},
      {type: "tr", x: crop.x + crop.width, y: crop.y},
      {type: "bl", x: crop.x, y: crop.y + crop.height},
      {type: "br", x: crop.x + crop.width, y: crop.y + crop.height},
    ];
    for (const h of handles) {
      if (x >= h.x - handleSize / 2 && x <= h.x + handleSize / 2 &&
          y >= h.y - handleSize / 2 && y <= h.y + handleSize / 2) {
        return h.type;
      }
    }
    return null;
  };

  const onMouseDown = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const handle = getHandleAt(x, y);
    if (handle) {
      setDragState({
        type: "resize",
        startX: x,
        startY: y,
        startCrop: {...crop},
        handle,
      });
    } else if (x >= crop.x && x <= crop.x + crop.width && y >= crop.y && y <= crop.y + crop.height) {
      setDragState({
        type: "move",
        startX: x,
        startY: y,
        startCrop: {...crop},
      });
    }
  };

  const onMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!dragState) return;
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const dx = x - dragState.startX;
      const dy = y - dragState.startY;

      if (dragState.type === "move") {
        let newX = dragState.startCrop.x + dx;
        let newY = dragState.startCrop.y + dy;
        // Limites
        newX = Math.max(0, Math.min(newX, imageSize.width - dragState.startCrop.width));
        newY = Math.max(0, Math.min(newY, imageSize.height - dragState.startCrop.height));
        setCrop({...dragState.startCrop, x: newX, y: newY});
      } else if (dragState.type === "resize") {
        const {handle} = dragState;
        let {x: newX, y: newY, width: newW, height: newH} = dragState.startCrop;

        if (handle.includes("l")) {
          newX = Math.max(0, Math.min(dragState.startCrop.x + dx, dragState.startCrop.x + dragState.startCrop.width - 50));
          newW = dragState.startCrop.x + dragState.startCrop.width - newX;
        }
        if (handle.includes("r")) {
          newW = Math.max(50, Math.min(dragState.startCrop.width + dx, imageSize.width - dragState.startCrop.x));
        }
        if (handle.includes("t")) {
          newY = Math.max(0, Math.min(dragState.startCrop.y + dy, dragState.startCrop.y + dragState.startCrop.height - 50));
          newH = dragState.startCrop.y + dragState.startCrop.height - newY;
        }
        if (handle.includes("b")) {
          newH = Math.max(50, Math.min(dragState.startCrop.height + dy, imageSize.height - dragState.startCrop.y));
        }

        // Manter aspect ratio
        if (aspectRatio) {
          if (handle.includes("l") || handle.includes("r")) {
            newH = newW / aspectRatio;
          } else {
            newW = newH * aspectRatio;
          }
        }

        // Limites finais
        newX = Math.max(0, Math.min(newX, imageSize.width - newW));
        newY = Math.max(0, Math.min(newY, imageSize.height - newH));
        newW = Math.min(newW, imageSize.width - newX);
        newH = Math.min(newH, imageSize.height - newY);

        setCrop({x: newX, y: newY, width: newW, height: newH});
      }
    },
    [dragState, imageSize, aspectRatio],
  );

  const onMouseUp = () => {
    setDragState(null);
  };

  useEffect(() => {
    if (dragState) {
      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
      return () => {
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };
    }
  }, [dragState, onMouseMove]);

  const generateCroppedImage = () => {
    const canvas = document.createElement("canvas");
    const img = imgRef.current;
    if (!img) return;
    const scaleX = img.naturalWidth / imageSize.width;
    const scaleY = img.naturalHeight / imageSize.height;
    const size = Math.min(crop.width * scaleX, crop.height * scaleY);
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(
      img,
      crop.x * scaleX,
      crop.y * scaleY,
      crop.width * scaleX,
      crop.height * scaleY,
      0,
      0,
      size,
      size
    );
    return canvas.toDataURL("image/jpeg", 0.9);
  };

  return (
    <div className="relative w-full max-w-md mx-auto">
      <canvas
        ref={canvasRef}
        onMouseDown={onMouseDown}
        className="w-full h-auto cursor-crosshair border border-foreground/10 rounded-lg bg-surface"
        style={{touchAction: "none"}}
      />
      <div className="mt-4 flex items-center justify-center gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium text-muted hover:text-foreground transition-colors"
        >
          <X className="h-4 w-4 inline mr-1" aria-hidden /> {cancelLabel}
        </button>
        <button
          type="button"
          onClick={() => onComplete(generateCroppedImage()!)}
          className="bg-accent-gradient px-4 py-2 text-sm font-medium text-foreground rounded-md hover:brightness-110"
        >
          <Check className="h-4 w-4 inline mr-1" aria-hidden /> {applyLabel}
        </button>
      </div>
    </div>
  );
}