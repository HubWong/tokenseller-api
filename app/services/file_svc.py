import mimetypes
from typing import Optional
import cloudinary
import cloudinary.uploader
import cloudinary.api
from datetime import datetime, timedelta
from app.core.config import settings
from fastapi import UploadFile
from app.features.user.schemas.photo_schema import PhotoUploadResp
from app.features.db_base import ApiResp
import os
import io 

def create_upload_dir():    
    upload_path = settings.UPLOAD_DIR
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
    return upload_path

def gen_file_path(filename: str) -> str:
    """生成文件存储路径"""
    upload_dir = create_upload_dir()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_filename = filename.replace(" ", "_")  # 简单处理文件名中的空格
    file_path = os.path.join(upload_dir, f"{timestamp}_{safe_filename}")
    return file_path

# def compress_image_by_size(image: Image.Image, max_size=settings.MAX_DIMENSION):
#     """按尺寸压缩"""
#     original_width, original_height = image.size
#     if original_width > max_size or original_height > max_size:
#         image.thumbnail((max_size, max_size), Resampling.LANCZOS)
#     return image


# def compress_image_by_quality(img_io: io.BytesIO, image_format: str, quality:str='IMAGE_QUALITY'):
#     """按质量压缩"""
#     compressed_io = io.BytesIO()
#     image = Image.open(img_io)
#     image.save(compressed_io, format=image_format, quality=quality)
#     compressed_io.seek(0)
#     return compressed_io


def is_large_file(contents: bytes):
    """判断是否是大文件"""
    return len(contents) >settings.MAX_UPLOAD_SIZE


# def process_image(contents: bytes, isThumbnail:bool=False) -> io.BytesIO:
#     """
#     综合处理图片：尺寸 + 质量压缩
#     返回处理后的 BytesIO 对象
#     """
#     image = Image.open(io.BytesIO(contents))
#     original_format = image.format

#     if isThumbnail:
#         image = image.resize((80,80), Image.Resampling.LANCZOS)
#     else:
#         # 按尺寸压缩        
#         image = compress_image_by_size(image)

#     # 创建新的BytesIO对象并保存resize后的图像
#     output_io = io.BytesIO()
#     image.save(output_io, format=original_format)
    
#     # 按质量压缩（如果原始文件太大）
#     if is_large_file(output_io.getvalue()):
#         output_io = compress_image_by_quality(output_io, str(original_format))

#     output_io.seek(0)  # 重置指针位置
#     return output_io


cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)


    
def _upload_to_cloudinary(img_io: io.BytesIO, folder=settings.PROJECT_NAME):
    result = cloudinary.uploader.upload(
        img_io,
        folder=folder,
        use_filename=True,
        unique_filename=True
    )
    return result

async def delete_old_images(folder=settings.PROJECT_NAME, days=settings.KEEP_DAYS):
    """删除指定文件夹下 N 天前的图片"""
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    result = cloudinary.api.delete_resources_by_prefix(f"{folder}/", from_date=from_date)
    print("Deleted old images:", result)
    return result

def delete_image_by_public_id(public_id: str):
    """
    根据 public_id 删除图片
    :param public_id: 如 "folder/image_name"
    :return: {
            'deleted': {'app global chat/wyb6688@hotmail.com/stream_pgcztq': 'deleted'},
            'deleted_counts': {'app global chat/wyb6688@hotmail.com/stream_pgcztq':{'original': 1, 'derived': 0}}, 
            'partial': False
            }
    """
    try:
        result = cloudinary.api.delete_resources(public_ids=[public_id])
        apiRes = result['deleted'][public_id]
        if apiRes =='deleted' :                      
            return ApiResp(success=True,data=True)
        else:
            return ApiResp(success=False,data = False)
    except Exception as e:
        return ApiResp(success=False, message=str(e))


async def upload_and_resize_image(file: UploadFile, folder: str,isThumbnail:bool=False) -> ApiResp[Optional[PhotoUploadResp]]:
    
    if not file.filename:
        return ApiResp(success=False,message="文件名不能为空")
    if not file.content_type:
        return ApiResp(success=False,message="文件类型不能为空")
    if not mimetypes.guess_type(file.filename)[0]:
        return ApiResp(success=False,message="无法识别的文件类型")
    try:
        #resize image
        data = process_image(await file.read(),isThumbnail=isThumbnail)     
        upload_result = _upload_to_cloudinary(img_io=data,folder=f'{settings.PROJECT_NAME}/{folder}')
        # 获取上传后的文件URL
        resp = PhotoUploadResp(            
            url= upload_result.get("secure_url"),
            public_id= upload_result.get("public_id")           
        )
        return ApiResp(success=True, data=resp)
    except Exception as e:
        return ApiResp(success=False,message=f"上传失败: {str(e)}")