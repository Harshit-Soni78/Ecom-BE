from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from typing import List, Optional

from app.api.v1.endpoints.auth import admin_required
from app.utils.image import save_uploaded_file, delete_uploaded_file

router = APIRouter()

@router.post("/upload/image")
def upload_image(
    file: UploadFile = File(...),
    folder: str = "general",
    image_type: str = None,
    admin: dict = Depends(admin_required)
):
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    file_url = save_uploaded_file(file, folder, image_type)
    
    return {
        "message": "Image uploaded and optimized successfully",
        "url": file_url,
        "filename": file.filename,
        "optimized_for": image_type or folder
    }

@router.post("/upload/logo")
def upload_logo(
    file: UploadFile = File(...),
    admin: dict = Depends(admin_required)
):
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    file_url = save_uploaded_file(file, "branding", "logo")
    
    return {
        "message": "Logo uploaded and optimized successfully",
        "url": file_url,
        "filename": file.filename,
        "optimized_size": "400x120 max (aspect ratio preserved)"
    }

@router.post("/upload/favicon")
def upload_favicon(
    file: UploadFile = File(...),
    admin: dict = Depends(admin_required)
):
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    file_url = save_uploaded_file(file, "branding", "favicon")
    
    return {
        "message": "Favicon uploaded and optimized successfully",
        "url": file_url,
        "filename": file.filename,
        "optimized_size": "32x32 pixels"
    }

@router.post("/upload/multiple")
def upload_multiple_images(
    files: List[UploadFile] = File(...),
    folder: str = "general",
    image_type: str = None,
    admin: dict = Depends(admin_required)
):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed")
    
    uploaded_files = []
    for file in files:
        if not file.content_type or not file.content_type.startswith('image/'):
            continue
        
        try:
            file_url = save_uploaded_file(file, folder, image_type)
            uploaded_files.append({
                "url": file_url,
                "filename": file.filename
            })
        except Exception:
            continue
    
    return {
        "message": f"Uploaded and optimized {len(uploaded_files)} images successfully",
        "files": uploaded_files,
        "optimized_for": image_type or folder
    }

@router.delete("/upload/delete")
def delete_image(
    file_url: str = Query(..., description="URL of the file to delete"),
    admin: dict = Depends(admin_required)
):
    delete_uploaded_file(file_url)
    return {"message": "Image deleted successfully"}
