import {describe, expect, it} from "vitest";
import {
  ASPECT_RATIOS,
  UPLOAD_MAX_BYTES,
  UPLOAD_MAX_DIMENSION,
  UploadValidationError,
  isAllowedImageType,
  isAspectRatio,
  validateUploadMetadata,
} from "../lib/studio-config";
import {parseSeedInput} from "../stores/generation";

function fileOf(name: string, type: string, size = 10): File {
  return new File([new Uint8Array(size)], name, {type});
}

describe("studio upload validation", () => {
  it("accepts PNG and JPEG", () => {
    expect(isAllowedImageType(fileOf("a.png", "image/png"))).toBe(true);
    expect(isAllowedImageType(fileOf("a.jpg", "image/jpeg"))).toBe(true);
    expect(isAllowedImageType(fileOf("a.gif", "image/gif"))).toBe(false);
  });

  it("rejects invalid type", () => {
    expect(() => validateUploadMetadata(fileOf("a.gif", "image/gif"))).toThrow(
      UploadValidationError,
    );
  });

  it("rejects files above the backend limit", () => {
    const file = fileOf("a.png", "image/png", UPLOAD_MAX_BYTES + 1);
    try {
      validateUploadMetadata(file);
      throw new Error("expected size error");
    } catch (error) {
      expect(error).toBeInstanceOf(UploadValidationError);
      expect((error as UploadValidationError).code).toBe("size");
    }
  });

  it("rejects dimensions above the backend limit", () => {
    try {
      validateUploadMetadata(fileOf("a.png", "image/png"), {
        width: UPLOAD_MAX_DIMENSION + 1,
        height: 100,
      });
      throw new Error("expected dimensions error");
    } catch (error) {
      expect(error).toBeInstanceOf(UploadValidationError);
      expect((error as UploadValidationError).code).toBe("dimensions");
    }
  });

  it("accepts a valid metadata pair", () => {
    expect(
      validateUploadMetadata(fileOf("a.jpg", "image/jpeg"), {width: 512, height: 512}),
    ).toEqual({width: 512, height: 512});
  });

  it("exposes exactly the five allowed aspect ratios", () => {
    expect(ASPECT_RATIOS.map((item) => item.value)).toEqual([
      "1:1",
      "4:3",
      "3:4",
      "16:9",
      "9:16",
    ]);
    expect(isAspectRatio("4:3")).toBe(true);
    expect(isAspectRatio("2:1")).toBe(false);
  });

  it("parses seeds safely", () => {
    expect(parseSeedInput("")).toBeUndefined();
    expect(parseSeedInput("0")).toBe(0);
    expect(parseSeedInput("42")).toBe(42);
    expect(parseSeedInput("2")).toBe(2);
    expect(parseSeedInput("-1")).toBeUndefined();
    expect(parseSeedInput("abc")).toBeUndefined();
    expect(parseSeedInput(String(2 ** 32))).toBeUndefined();
  });
});
