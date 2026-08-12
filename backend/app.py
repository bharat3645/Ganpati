import os
import io
import base64
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image, UnidentifiedImageError
from rembg import remove
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from typing import List
import uvicorn
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import logging

# Load environment variables from a local .env file if present
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Festive AI Greetings API", version="1.0.0")

# CORS middleware
# Configurable via CORS_ORIGINS env var (comma-separated). Defaults to common
# local dev origins for Vite (5173) and CRA (3000).
_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Input validation / limits -------------------------------------------------
# Uploaded photo size cap (base64-decoded bytes). Keeps request handling and
# rembg processing bounded and gives users a clear 400 instead of a slow 500.
MAX_USER_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MB

# Cap on any image fetched from a remote URL (logo images), enforced while
# streaming the response so an oversized/malicious response can't be used to
# exhaust server memory.
MAX_REMOTE_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "GIF"}

# Directory bundled with the backend containing the fixed set of Ganesh
# backdrop images. Compositing only ever needs these -- see GANESH_IMAGES_DB.
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


# Pydantic models
class GenerateRequest(BaseModel):
    # A known backdrop id (see GANESH_IMAGES_DB), *not* an arbitrary URL.
    # Earlier versions of this API accepted a caller-supplied
    # `ganeshImageURL` that the server would fetch directly -- that is a
    # textbook SSRF vector (a client could point the backend at internal
    # services, cloud metadata endpoints, etc). Since the UI only ever offers
    # a fixed set of bundled backdrops, the server loads them from local disk
    # instead of fetching a caller-supplied URL at all.
    ganeshImageId: str
    userPhotoBase64: str
    selectedLogoId: str

    @field_validator("ganeshImageId", "selectedLogoId")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v

    @field_validator("userPhotoBase64")
    @classmethod
    def _looks_like_image_payload(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        # Rough upper bound before we even attempt to base64-decode: base64
        # inflates size by ~4/3, so this rejects grossly oversized payloads
        # cheaply, ahead of the precise check in decode_base64_image().
        if len(v) > MAX_USER_PHOTO_BYTES * 2:
            raise ValueError("userPhotoBase64 payload is too large")
        return v

class Logo(BaseModel):
    id: str
    name: str
    imageUrl: str

class GaneshBackdrop(BaseModel):
    id: str
    name: str

# Known Ganesh backdrops, bundled locally under backend/assets/. Keep this in
# sync with the images offered in the frontend (src/App.tsx `ganeshImages`).
GANESH_IMAGES_DB = [
    {"id": "ganesh_1", "name": "Silver Floral Ganesh", "filename": "1.jpg"},
    {"id": "ganesh_2", "name": "Grand Pandal Ganesh", "filename": "2.jpg"},
    {"id": "ganesh_3", "name": "Royal Red & Gold Ganesh", "filename": "3.jpg"},
    {"id": "ganesh_4", "name": "Traditional Temple Ganesh", "filename": "4.jpg"},
    {"id": "ganesh_5", "name": "Golden Festive Ganesh", "filename": "5.jpg"},
    {"id": "ganesh_6", "name": "Majestic Golden Crown Ganesh", "filename": "6.jpg"},
]

# Logo database with working URLs
LOGOS_DB = [
    {
        "id": "logo_01",
        "name": "Aperture Labs",
        "imageUrl": "https://images.pexels.com/photos/7688136/pexels-photo-7688136.jpeg?auto=compress&cs=tinysrgb&w=200"
    },
    {
        "id": "logo_02",
        "name": "Cyberdyne Systems", 
        "imageUrl": "https://images.pexels.com/photos/7688347/pexels-photo-7688347.jpeg?auto=compress&cs=tinysrgb&w=200"
    },
    {
        "id": "logo_03",
        "name": "Stark Industries",
        "imageUrl": "https://images.pexels.com/photos/7688480/pexels-photo-7688480.jpeg?auto=compress&cs=tinysrgb&w=200"
    },
    {
        "id": "logo_04",
        "name": "Wayne Enterprises",
        "imageUrl": "https://images.pexels.com/photos/1181467/pexels-photo-1181467.jpeg?auto=compress&cs=tinysrgb&w=200"
    }
]

# Initialize Hugging Face client
# HF_TOKEN must be provided via environment variable (see backend/.env.example).
# No hardcoded fallback token is used -- AI enhancement is skipped gracefully
# (falls back to the base composite image) if it is not configured.
HF_TOKEN = os.environ.get("HF_TOKEN", "")
if not HF_TOKEN:
    logger.warning(
        "HF_TOKEN is not set. AI image enhancement will be skipped and the "
        "base composite image will be returned instead. Copy backend/.env.example "
        "to backend/.env and set HF_TOKEN to enable AI enhancement."
    )

@app.get("/")
async def root():
    return {"message": "Festive AI Greetings API is running!", "status": "healthy"}

@app.get("/api/logos", response_model=List[Logo])
async def get_logos():
    """Get available corporate logos"""
    try:
        logger.info("Fetching logos from database")
        return LOGOS_DB
    except Exception as e:
        logger.error(f"Error fetching logos: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch logos")

@app.get("/api/ganesh-images", response_model=List[GaneshBackdrop])
async def get_ganesh_images():
    """Get available Ganesh backdrop ids/names (the images themselves are
    bundled as static assets; this just documents the valid ids accepted by
    ganeshImageId in POST /api/generate)."""
    try:
        logger.info("Fetching Ganesh backdrops from database")
        return [{"id": g["id"], "name": g["name"]} for g in GANESH_IMAGES_DB]
    except Exception as e:
        logger.error(f"Error fetching Ganesh backdrops: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch Ganesh backdrops")

def _validate_decoded_image(image: Image.Image, context: str) -> Image.Image:
    """Shared validation for any image we're about to process: enforce a
    known raster format (defends against disguised/malformed payloads) and
    eagerly load pixel data so a truncated/corrupt file fails fast with a
    clear error instead of surfacing later mid-composite."""
    if image.format not in ALLOWED_IMAGE_FORMATS:
        raise ValueError(
            f"Unsupported image format '{image.format}' for {context}; "
            f"allowed formats: {', '.join(sorted(ALLOWED_IMAGE_FORMATS))}"
        )
    try:
        image.load()
    except Exception as e:
        raise ValueError(f"Corrupt or truncated image data for {context}: {e}")
    return image

def decode_base64_image(base64_string: str) -> Image.Image:
    """Decode a (optionally data-URL-prefixed) base64 string to a validated
    PIL Image, enforcing a size cap and a known image format."""
    try:
        # Remove data URL prefix if present
        if base64_string.startswith('data:image'):
            base64_string = base64_string.split(',', 1)[1]

        image_data = base64.b64decode(base64_string, validate=True)
    except Exception as e:
        logger.error(f"Error decoding base64 image: {str(e)}")
        raise ValueError("Invalid base64 image data")

    if len(image_data) > MAX_USER_PHOTO_BYTES:
        raise ValueError(
            f"Uploaded photo is too large ({len(image_data)} bytes); "
            f"the limit is {MAX_USER_PHOTO_BYTES} bytes"
        )
    if len(image_data) == 0:
        raise ValueError("Uploaded photo is empty")

    try:
        image = Image.open(io.BytesIO(image_data))
        _validate_decoded_image(image, "uploaded photo")
    except ValueError:
        raise
    except UnidentifiedImageError:
        raise ValueError("Uploaded data is not a recognizable image")
    except Exception as e:
        logger.error(f"Error decoding base64 image: {str(e)}")
        raise ValueError("Invalid base64 image data")

    logger.info(f"Decoded base64 image: {image.size} ({image.format})")
    return image

def remove_background(image: Image.Image) -> Image.Image:
    """Remove background from image using rembg"""
    try:
        logger.info("Removing background from user image")
        # Convert PIL image to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Remove background
        output = remove(img_byte_arr)
        
        # Convert back to PIL Image
        result_image = Image.open(io.BytesIO(output))
        logger.info("Background removal completed")
        return result_image
    except Exception as e:
        logger.error(f"Error removing background: {str(e)}")
        # Return original image if background removal fails
        return image

def _assert_public_http_url(url: str) -> None:
    """SSRF guard for any server-side fetch of a caller-influenced URL.

    Only http(s) URLs whose hostname resolves to a public (non-private,
    non-loopback, non-link-local, non-reserved) IP address are allowed. This
    stops the server from being used as a proxy to reach internal services,
    localhost, or cloud metadata endpoints (e.g. 169.254.169.254) even if a
    future change starts sourcing `url` from client input.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme or '(none)'}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL is missing a hostname")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve host '{hostname}': {e}")

    for family, _, _, _, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError(
                f"Refusing to fetch '{url}': host '{hostname}' resolves to a "
                f"non-public address ({ip})"
            )

def fetch_image_from_url(url: str) -> Image.Image:
    """Fetch an image from an external (logo) URL, guarded against SSRF and
    unbounded response sizes."""
    try:
        logger.info(f"Fetching image from URL: {url}")
        _assert_public_http_url(url)

        with requests.get(url, timeout=30, stream=True) as response:
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_REMOTE_IMAGE_BYTES:
                raise ValueError(
                    f"Remote image at '{url}' exceeds the {MAX_REMOTE_IMAGE_BYTES} byte limit"
                )

            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                total += len(chunk)
                if total > MAX_REMOTE_IMAGE_BYTES:
                    raise ValueError(
                        f"Remote image at '{url}' exceeds the {MAX_REMOTE_IMAGE_BYTES} byte limit"
                    )
                chunks.append(chunk)

        image = Image.open(io.BytesIO(b"".join(chunks)))
        _validate_decoded_image(image, f"remote image ({url})")
        logger.info(f"Fetched image: {image.size} ({image.format})")
        return image
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error fetching image from URL {url}: {str(e)}")
        raise ValueError(f"Failed to fetch image from URL: {url}")

def load_local_ganesh_image(ganesh_id: str) -> Image.Image:
    """Load a bundled Ganesh backdrop from local disk by id. No network
    request is made for these -- they ship with the backend -- which both
    sidesteps SSRF entirely for this path and removes the backend's runtime
    dependency on the frontend dev server being reachable."""
    entry = next((g for g in GANESH_IMAGES_DB if g["id"] == ganesh_id), None)
    if entry is None:
        raise ValueError(f"Unknown ganeshImageId: {ganesh_id}")

    path = (ASSETS_DIR / entry["filename"]).resolve()
    # Defense in depth: even though `filename` is server-controlled (not
    # derived from the request), make sure the resolved path can't escape
    # ASSETS_DIR before we open it.
    if ASSETS_DIR.resolve() not in path.parents:
        raise ValueError(f"Invalid asset path for ganeshImageId: {ganesh_id}")
    if not path.is_file():
        raise ValueError(f"Backdrop asset missing on disk: {entry['filename']}")

    logger.info(f"Loading local Ganesh backdrop: {path}")
    image = Image.open(path)
    _validate_decoded_image(image, f"Ganesh backdrop ({ganesh_id})")
    return image

def create_base_composite(ganesh_image: Image.Image, user_image: Image.Image, logo_image: Image.Image) -> Image.Image:
    """Create base composite image"""
    try:
        logger.info("Creating base composite image")
        
        # Convert all images to RGBA
        ganesh_image = ganesh_image.convert('RGBA')
        user_image = user_image.convert('RGBA')
        logo_image = logo_image.convert('RGBA')
        
        # Use Ganesh image as base canvas
        canvas = ganesh_image.copy()
        canvas_width, canvas_height = canvas.size
        logger.info(f"Canvas size: {canvas_width}x{canvas_height}")
        
        # Remove background from user image
        user_no_bg = remove_background(user_image)
        
        # Resize user image to fit in foreground (about 1/3 of canvas width)
        user_width = canvas_width // 3
        user_aspect = user_no_bg.height / user_no_bg.width
        user_height = int(user_width * user_aspect)
        user_resized = user_no_bg.resize((user_width, user_height), Image.Resampling.LANCZOS)
        
        # Position user in lower right area
        user_x = canvas_width - user_width - 50
        user_y = canvas_height - user_height - 50
        
        # Ensure coordinates are within bounds
        user_x = max(0, min(user_x, canvas_width - user_width))
        user_y = max(0, min(user_y, canvas_height - user_height))
        
        # Paste user image
        canvas.paste(user_resized, (user_x, user_y), user_resized)
        logger.info(f"Placed user image at: ({user_x}, {user_y})")
        
        # Resize logo (small, like on a sweet box)
        logo_size = min(canvas_width // 8, canvas_height // 8, 100)
        logo_resized = logo_image.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        
        # Position logo in the area where user would hold a sweet box
        logo_x = user_x + user_width // 4
        logo_y = user_y + user_height // 2
        
        # Ensure logo coordinates are within bounds
        logo_x = max(0, min(logo_x, canvas_width - logo_size))
        logo_y = max(0, min(logo_y, canvas_height - logo_size))
        
        # Paste logo
        canvas.paste(logo_resized, (logo_x, logo_y), logo_resized)
        logger.info(f"Placed logo at: ({logo_x}, {logo_y})")
        
        result = canvas.convert('RGB')
        logger.info("Base composite created successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error creating composite: {str(e)}")
        raise ValueError("Failed to create image composite")

def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string"""
    try:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        logger.error(f"Error converting image to base64: {str(e)}")
        raise ValueError("Failed to convert image to base64")

async def generate_ai_image(base_image: Image.Image) -> Image.Image:
    """Generate final image using FLUX.1-Kontext-dev model"""
    if not HF_TOKEN:
        logger.warning("HF_TOKEN not configured; skipping AI enhancement and returning base composite")
        return base_image

    try:
        logger.info("Starting AI image generation")

        # Initialize client
        client = InferenceClient(
            provider="fal-ai",
            api_key=HF_TOKEN,
        )
        
        # Convert PIL image to bytes for the API
        img_byte_arr = io.BytesIO()
        base_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        # Guiding prompt for the AI
        prompt_text = (
            "A photorealistic, 4K, ultra-detailed image for Ganesh Chaturthi festival. "
            "Blend all elements of the image together seamlessly and naturally. "
            "The person is holding a festive box of Indian sweets (modaks) with the corporate logo on it. "
            "The scene has warm, celebratory, divine lighting with golden and orange tones. "
            "Make it look like a real photograph with perfect lighting and composition. "
            "The background should be a beautiful Ganesh idol with traditional decorations."
        )
        
        logger.info("Calling FLUX.1-Kontext-dev model")
        
        # Call the image-to-image API
        final_image = client.image_to_image(
            image=img_byte_arr.getvalue(),
            prompt=prompt_text,
            model="black-forest-labs/FLUX.1-Kontext-dev",
            strength=0.75,  # Balance between preserving original and AI enhancement
            num_inference_steps=50,
        )
        
        logger.info("AI image generation completed successfully")
        return final_image
        
    except Exception as e:
        logger.error(f"Error generating AI image: {str(e)}")
        logger.warning("Falling back to base composite image")
        # Return base image if AI generation fails
        return base_image

@app.post("/api/generate")
async def generate_greeting(request: GenerateRequest):
    """Generate festive greeting image"""
    try:
        logger.info("Starting image generation process")

        # Step A: Prepare assets
        logger.info("Fetching and preparing assets")

        # Decode user photo from base64 (validated: size cap + known format)
        user_image = decode_base64_image(request.userPhotoBase64)

        # Load the selected Ganesh background from bundled local assets
        # (never fetched over the network -- see load_local_ganesh_image).
        ganesh_image = load_local_ganesh_image(request.ganeshImageId)

        # Find selected logo
        selected_logo = next((logo for logo in LOGOS_DB if logo["id"] == request.selectedLogoId), None)
        if not selected_logo:
            raise HTTPException(status_code=400, detail="Invalid logo ID")

        # Fetch logo image (validated: SSRF guard + size cap + known format)
        logo_image = fetch_image_from_url(selected_logo["imageUrl"])

        # Step B: Create base composite
        logger.info("Creating base composite image")
        base_composite = create_base_composite(ganesh_image, user_image, logo_image)

        # Step C: Generate AI-enhanced image
        logger.info("Generating AI-enhanced image")
        try:
            final_image = await generate_ai_image(base_composite)
        except Exception as ai_error:
            logger.warning(f"AI generation failed, using base composite: {str(ai_error)}")
            final_image = base_composite

        # Step D: Convert to base64 and return
        logger.info("Converting final image to base64")
        final_image_base64 = image_to_base64(final_image)

        logger.info("Image generation completed successfully")
        return JSONResponse(content={
            "success": True,
            "imageUrl": final_image_base64
        })

    except HTTPException:
        raise
    except ValueError as e:
        # Anything we raise deliberately during validation/decoding/fetching
        # is a client-input problem, not a server fault -- surface it as 400
        # rather than a generic 500.
        logger.warning(f"Invalid request in generate_greeting: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in generate_greeting: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)