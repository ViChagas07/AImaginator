export const UPLOAD_MAX_BYTES = 10 * 1024 * 1024;
export const UPLOAD_MAX_MB = 10;
export const UPLOAD_MAX_DIMENSION = 8192;

export const ASPECT_RATIOS = [
  {value: "1:1", labelKey: "aspectRatioSquare"},
  {value: "4:3", labelKey: "aspectRatioFourThree"},
  {value: "3:4", labelKey: "aspectRatioPortrait"},
  {value: "16:9", labelKey: "aspectRatioLandscape"},
  {value: "9:16", labelKey: "aspectRatioTall"},
] as const;

export type AspectRatioValue = (typeof ASPECT_RATIOS)[number]["value"];

export type UploadErrorCode = "type" | "size" | "dimensions";

export function isAspectRatio(value: string): value is AspectRatioValue {
  return ASPECT_RATIOS.some((item) => item.value === value);
}

export class UploadValidationError extends Error {
  code: UploadErrorCode;

  constructor(code: UploadErrorCode) {
    super(code);
    this.code = code;
  }
}

const ALLOWED_TYPES = new Set(["image/png", "image/jpeg"]);
const ALLOWED_EXTENSIONS = /\.(png|jpe?g)$/i;

export function isAllowedImageType(file: File): boolean {
  if (file.type) return ALLOWED_TYPES.has(file.type.toLowerCase());
  return ALLOWED_EXTENSIONS.test(file.name);
}

export function validateUploadMetadata(
  file: File,
  dimensions?: {width: number; height: number},
): {width: number; height: number} {
  if (!isAllowedImageType(file)) throw new UploadValidationError("type");
  if (file.size > UPLOAD_MAX_BYTES) throw new UploadValidationError("size");
  if (dimensions) {
    if (
      dimensions.width <= 0 ||
      dimensions.height <= 0 ||
      dimensions.width > UPLOAD_MAX_DIMENSION ||
      dimensions.height > UPLOAD_MAX_DIMENSION
    ) {
      throw new UploadValidationError("dimensions");
    }
    return dimensions;
  }
  return {width: 0, height: 0};
}

export async function readImageDimensions(
  file: File,
): Promise<{width: number; height: number}> {
  if (typeof createImageBitmap === "function") {
    try {
      const bitmap = await createImageBitmap(file);
      const dimensions = {width: bitmap.width, height: bitmap.height};
      bitmap.close?.();
      return dimensions;
    } catch {
      // fallback to HTMLImageElement below
    }
  }
  if (typeof Image === "undefined" || typeof URL.createObjectURL !== "function") {
    return {width: 0, height: 0};
  }
  return await new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve({width: image.naturalWidth, height: image.naturalHeight});
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new UploadValidationError("type"));
    };
    image.src = url;
  });
}

export async function validateUploadFile(
  file: File,
): Promise<{width: number; height: number}> {
  validateUploadMetadata(file);
  const dimensions = await readImageDimensions(file);
  if (dimensions.width === 0 || dimensions.height === 0) return dimensions;
  return validateUploadMetadata(file, dimensions);
}
