from fastapi import  Depends,Form, UploadFile, APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from app.core.deps import DepUser
from app.features.user_file.user_file_crud import user_file_crud
from app.core.deps import DbSessionDeps

from app.features.user.photo_crud import photo_crud
from app.services.file_svc import delete_image_by_public_id
from app.features.db_base import ApiResp
import os

router = APIRouter(prefix="/files", tags=["files"])

@router.get("/download/{file_id}") #user friend can download or view the file.
async def download_file(file_id: int, db:DbSessionDeps):
    file = await user_file_crud.get_file_by_id(db, id=file_id)
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = file.filepath
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server")
    
    file.already_used += 1
    await user_file_crud.update(db, db_obj=file, obj_in={"already_used": file.already_used})
    return FileResponse(path=file.filepath, media_type="application/octet-stream", filename=file.filename)


#photo upload , file shares in chat room 
@router.post("/upload")
async def upload_file(file: UploadFile,db:DbSessionDeps,cur_user:DepUser,type:str = Form(...),  )->ApiResp:
    #create a file in db and the cloud db.
    if type =='photo':
        resp = await photo_crud.create(db=db, file=file, user=cur_user)      
        return resp
    elif type == 'file':
        resp = await user_file_crud.create(db=db, file=file, user=cur_user) 
        #return a file url for the uploaded file, the url can be used in the chat room to share the file.
             
        return resp
    return ApiResp(success=False, message="不支持的文件类型")


@router.put("/avatar")
async def upload_avatar(
    *,
    db: DbSessionDeps,
    avatar: UploadFile = File(...),
    current_user: DepUser,
) -> ApiResp:
    """
    Upload user avatar.
    """
    # Check if the uploaded file is an image
    content = avatar.content_type
    if content and not content.startswith("image"):
        raise HTTPException(
            status_code=400,
            detail="File must be an image"
        )
    
    return  await photo_crud.add_or_update_avatar(db=db,file=avatar,user=current_user)
   
    
   

@router.delete("/del_photo/{photo_id}")
async def delete_photo(photo_id: int, db:DbSessionDeps, cur_user: DepUser):
    if not cur_user.id:
        return ApiResp(success=False, message="用户ID不能为空") 
    isAvatar,deleted_photo =await photo_crud.delete_photo(db=db, photo_id=photo_id)
   
    if not deleted_photo:
        return ApiResp(success=True, message="图片未找到或已被删除")
    if isAvatar:
        return ApiResp(success=True, message="ok")
    
    res =  delete_image_by_public_id(str(deleted_photo.cloudinary_pub_id))
    if not res:
        return ApiResp(success=False, message="删除失败")    
    return ApiResp(success=True, message="ok")


@router.get("/get_photos")
async def get_photos(db: DbSessionDeps, cur_user: DepUser):
    user_id = cur_user.id
    if not user_id:
        return ApiResp(success=False, message="用户ID不能为空")
    
    # 获取用户上传的图片
    photos =await photo_crud.get_user_photos(db=db, user_id=user_id)
    if not photos:
        return ApiResp(data=[], message="没有找到用户上传的图片", success=False)

    return ApiResp(data=photos, message="获取用户上传的图片成功", success=True)


@router.patch('/is_private/{photo_id}')
async def toggle_photo_privacy(photo_id: int, db:DbSessionDeps, cur_user: DepUser):
    if not cur_user.id:
        return ApiResp(success=False, message="用户ID不能为空") 
    updated_photo = await photo_crud.update_privacy(db=db, photo_id=photo_id, user_id=cur_user.id)
    if not updated_photo:
        return ApiResp(success=False, message="图片未找到或无法更改隐私设置")
    return ApiResp(success=True, message="图片隐私设置已更新", data=updated_photo)
