import shutil
import logging
from pathlib import Path
from fastapi import UploadFile, HTTPException
from PIL import Image
from app.core.config import settings

def save_uploaded_file(file: UploadFile, folder: str = "general", image_type: str = None) -> str:
    """Save uploaded file and return the URL"""
    try:
        # Create folder if it doesn't exist
        folder_path = settings.UPLOAD_DIR / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        
        # We need a way to generate unique ID. 
        # Since this module doesn't import from server or utils, let's just use uuid here.
        import uuid
        unique_filename = f"{str(uuid.uuid4())}.{file_extension}"
        file_path = folder_path / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Optimize image if it's an image file
        if file_extension.lower() in ['jpg', 'jpeg', 'png', 'webp']:
            # Determine image type based on folder or explicit type
            if image_type:
                optimize_image(file_path, image_type=image_type)
            elif folder == "branding":
                optimize_image(file_path, image_type="logo")  # Default for branding
            elif folder == "banners":
                optimize_image(file_path, image_type="banner")
            elif folder == "categories":
                optimize_image(file_path, image_type="category")
            elif folder == "products":
                optimize_image(file_path, image_type="product")
            else:
                optimize_image(file_path, image_type="general")
        
        # Return URL
        return f"/uploads/{folder}/{unique_filename}"
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

def optimize_image(file_path: Path, max_size: tuple = (1200, 1200), quality: int = 85, image_type: str = "general"):
    """Optimize image size and quality with specific handling for different image types"""
    try:
        with Image.open(file_path) as img:
            # Convert to RGB if necessary, but preserve transparency for logos/favicons
            if img.mode in ('RGBA', 'LA', 'P'):
                # For logos and favicons, preserve transparency by converting to RGBA
                if image_type in ['logo', 'favicon', 'branding']:
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                else:
                    img = img.convert('RGB')
            
            # Specific sizing for different image types
            if image_type == 'logo':
                # Logo: Resize to fit within 400x120 while maintaining aspect ratio
                img.thumbnail((400, 120), Image.Resampling.LANCZOS)
            elif image_type == 'favicon':
                # Favicon: Create 32x32 size
                img = img.resize((32, 32), Image.Resampling.LANCZOS)
            elif image_type == 'banner':
                # Banner: Resize to 1200x400 (3:1 aspect ratio)
                img = img.resize((1200, 400), Image.Resampling.LANCZOS)
            elif image_type == 'category':
                # Category: Square aspect ratio, max 500x500
                # Make it square by cropping to center
                width, height = img.size
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                img = img.crop((left, top, left + size, top + size))
                img = img.resize((500, 500), Image.Resampling.LANCZOS)
            elif image_type == 'product':
                # Product: Square aspect ratio, max 800x800
                width, height = img.size
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                img = img.crop((left, top, left + size, top + size))
                img = img.resize((800, 800), Image.Resampling.LANCZOS)
            else:
                # General: Use provided max_size
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save optimized image
            if img.mode == 'RGBA' and file_path.suffix.lower() in ['.jpg', '.jpeg']:
                # Convert RGBA to RGB for JPEG (no transparency support)
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
                img.save(file_path, optimize=True, quality=quality)
            else:
                # Save with transparency support for PNG
                img.save(file_path, optimize=True, quality=quality)
            
    except Exception as e:
        # If optimization fails, keep original file
        logging.warning(f"Failed to optimize image {file_path}: {str(e)}")

def delete_uploaded_file(file_url: str):
    """Delete uploaded file"""
    try:
        if file_url and file_url.startswith('/uploads/'):
            file_path = Path(file_url[1:])  # Remove leading slash
            if file_path.exists():
                file_path.unlink()
    except Exception as e:
        logging.warning(f"Failed to delete file {file_url}: {str(e)}")
