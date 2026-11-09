"""Marca d'agua e metadados de IA (Pillow) para imagens publicadas."""

from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageFilter

from shared_kernel.security_errors import C2PARequiredError

logger = logging.getLogger(__name__)


class PillowWatermarker:
    """Aplica a logo no canto inferior direito com alfa, sombra e cache."""

    def __init__(
        self,
        *,
        logo_path: str,
        width_ratio: float = 0.20,
        min_width_px: int = 96,
        margin_ratio: float = 0.025,
        opacity: float = 0.9,
        shadow: bool = True,
    ) -> None:
        self._width_ratio = width_ratio
        self._min_width_px = min_width_px
        self._margin_ratio = margin_ratio
        self._opacity = opacity
        self._shadow = shadow
        self._logo = Image.open(Path(logo_path))
        self._logo.load()
        if self._logo.mode != "RGBA":
            self._logo = self._logo.convert("RGBA")
        self._cache: dict[int, Image.Image] = {}

    def geometry(self, width: int, height: int) -> tuple[int, int, int, int, int]:
        """Devolve (x, y, logo_w, logo_h, margem) para testes/previsao."""
        margin = int(round(width * self._margin_ratio))
        target_w = min(width, max(self._min_width_px, int(round(width * self._width_ratio))))
        target_h = max(1, int(round(self._logo.height * target_w / self._logo.width)))
        if target_h > height:
            target_h = height
            target_w = max(1, int(round(self._logo.width * target_h / self._logo.height)))
        x = max(0, width - target_w - margin)
        y = max(0, height - target_h - margin)
        return x, y, target_w, target_h, margin

    def apply(self, image_bytes: bytes) -> bytes:
        source = Image.open(io.BytesIO(image_bytes))
        source.load()
        icc_profile = source.info.get("icc_profile")
        original_mode = source.mode
        if source.mode not in ("RGB", "RGBA"):
            source = source.convert("RGBA")
        x, y, target_w, target_h, _margin = self.geometry(source.width, source.height)
        logo = self._resized_logo(target_w)
        if self._shadow:
            source = self._with_shadow(source, logo, x, y)
        source = source.convert("RGBA")
        source.alpha_composite(logo, (max(0, x), max(0, y)))
        if original_mode in ("RGB", "RGBA"):
            source = source.convert(original_mode)
        return _save_png(source, icc_profile=icc_profile)

    def _resized_logo(self, target_w: int) -> Image.Image:
        cached = self._cache.get(target_w)
        if cached is not None:
            return cached
        ratio = target_w / self._logo.width
        target_h = max(1, int(round(self._logo.height * ratio)))
        resized = self._logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
        if self._opacity < 1.0:
            alpha = resized.getchannel("A").point(lambda value: int(value * self._opacity))
            resized.putalpha(alpha)
        self._cache[target_w] = resized
        return resized

    def _with_shadow(self, image: Image.Image, logo: Image.Image, x: int, y: int) -> Image.Image:
        base = image.convert("RGBA")
        shadow_alpha = logo.getchannel("A").filter(
            ImageFilter.GaussianBlur(radius=max(1, logo.width // 80))
        )
        shadow = Image.new("RGBA", logo.size, (0, 0, 0, 0))
        shadow.putalpha(shadow_alpha.point(lambda value: int(value * 0.45)))
        offset = max(1, logo.width // 80)
        base.alpha_composite(shadow, (max(0, x + offset), max(0, y + offset)))
        return base


class AiMetadataWriter:
    """Grava tEXt/iTXt + XMP/IPTC sem qualquer dado pessoal."""

    def apply(
        self,
        image_bytes: bytes,
        *,
        model_name: str,
        created_at: datetime | None = None,
    ) -> bytes:
        created = (created_at or datetime.now(UTC)).astimezone(UTC)
        timestamp = created.isoformat().replace("+00:00", "Z")
        source_type = "trainedAlgorithmicMedia"
        xmp = _xmp_packet(model_name=model_name, timestamp=timestamp)

        image = Image.open(io.BytesIO(image_bytes))
        image.load()
        from PIL.PngImagePlugin import PngInfo

        info = PngInfo()
        info.add_text("DigitalSourceType", source_type)
        info.add_text("Generator", "AImaginator")
        info.add_text("AI Model", model_name)
        info.add_text("AI Generated At", timestamp)
        info.add_itxt("XML:com.adobe.xmp", xmp)
        icc = image.info.get("icc_profile")
        return _save_png(image, pnginfo=info, icc_profile=icc)


class C2PASigner:
    """Assinatura C2PA opcional; ausencia de lib/certificados apenas avisa."""

    def __init__(
        self,
        *,
        enabled: bool,
        cert_path: str = "",
        key_path: str = "",
        required: bool = False,
        algorithm: str = "es256",
        version: str = "0.1.0",
    ) -> None:
        self._enabled = enabled
        self._cert_path = cert_path
        self._key_path = key_path
        self._required = required
        self._algorithm = algorithm
        self._version = version

    def _fail_or_warn(self, message: str) -> bytes | None:
        if self._required:
            raise C2PARequiredError(message)
        logger.warning(message)
        return None

    def sign(self, image_bytes: bytes) -> bytes:
        if not self._enabled:
            return image_bytes
        if not self._cert_path or not self._key_path:
            failed = self._fail_or_warn("c2pa_certificate_missing")
            return image_bytes if failed is None else failed
        try:
            import c2pa  # noqa: F401
        except ImportError:
            failed = self._fail_or_warn("c2pa_library_missing")
            return image_bytes if failed is None else failed
        try:
            return self._sign_with_c2pa(image_bytes)
        except Exception as exc:
            if self._required:
                raise C2PARequiredError("c2pa_signing_failed") from exc
            logger.warning("c2pa_signing_failed", exc_info=True)
            return image_bytes

    def _sign_with_c2pa(self, image_bytes: bytes) -> bytes:
        from c2pa import Builder, Signer

        cert = Path(self._cert_path).read_bytes()
        key = Path(self._key_path).read_bytes()
        manifest = json.dumps(
            {
                "claim_generator": f"AImaginator/{self._version}",
                "assertions": [
                    {
                        "label": "c2pa.actions",
                        "data": {
                            "actions": [
                                {
                                    "action": "c2pa.created",
                                    "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
                                }
                            ]
                        },
                    }
                ],
            }
        )
        signer = Signer.from_info({"private_key": key, "sign_cert": cert, "alg": self._algorithm})
        builder = Builder.from_json(manifest)
        with builder:
            signed = builder.sign(signer, "image/png", io.BytesIO(image_bytes))
            return signed.read()


def _xmp_packet(*, model_name: str, timestamp: str) -> str:
    return f"""<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/"
    xmp:CreatorTool="AImaginator"
    xmp:CreateDate="{timestamp}"
    Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia">
   <Iptc4xmpExt:Model>{model_name}</Iptc4xmpExt:Model>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


def _save_png(
    image: Image.Image,
    *,
    pnginfo=None,
    icc_profile: bytes | None = None,
) -> bytes:
    out = io.BytesIO()
    kwargs = {"format": "PNG", "optimize": True}
    if pnginfo is not None:
        kwargs["pnginfo"] = pnginfo
    if icc_profile:
        kwargs["icc_profile"] = icc_profile
    image.save(out, **kwargs)
    return out.getvalue()
