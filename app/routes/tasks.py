from fastapi import APIRouter, Depends, HTTPException, status
from .. import database, models, schemas
from sqlalchemy.orm import Session
from typing import List
from ..auth import get_current_user

router = APIRouter(
    prefix="/tasks",
    tags=['Posts']
)

def _to_subtask_response(s: models.Subtask) -> schemas.SubtaskResponse:
    return schemas.SubtaskResponse(
        id=s.id,
        task_id=s.task_id,
        title=s.title,
        content=s.content or "",
        completed=s.completed or False,
        is_completed=s.completed or False,
        due_date=s.due_date,
    )

def _to_task_post(t: models.tasks) -> schemas.TasksPost:
    sub_list = [_to_subtask_response(s) for s in (getattr(t, "subtasks", None) or [])]
    return schemas.TasksPost(
        id=t.id,
        title=t.title,
        content=t.content or "",
        description=t.content or "",
        completed=t.completed or False,
        is_completed=t.completed or False,
        priority=t.priority or "medium",
        due_date=t.due_date,
        created_at=t.created_at,
        updated_at=t.updated_at,
        subtasks=sub_list,
    )

@router.get("/", status_code=status.HTTP_200_OK, response_model=List[schemas.TasksPost])
def get_tasks(current_user=Depends(get_current_user), db: Session = Depends(database.get_db)):
    task_records = db.query(models.tasks).filter(models.tasks.users_id == current_user["id"]).all()
    return [_to_task_post(t) for t in task_records]

@router.post("/", status_code=status.HTTP_200_OK, response_model=schemas.TasksPost)
def post_tasks(posts: schemas.Tasks, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    content_val = posts.content or posts.description or ""
    completed_val = posts.completed if posts.completed is not None else (posts.is_completed or False)
    added = models.tasks(
        title=posts.title,
        content=content_val,
        completed=completed_val,
        priority=posts.priority or "medium",
        due_date=posts.due_date,
        users_id=current_user["id"],
    )
    db.add(added)
    db.commit()
    db.refresh(added)
    return _to_task_post(added)

@router.get("/{id}", status_code=status.HTTP_200_OK, response_model=schemas.TasksPost)
def getting_tasks(id: int, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    ans = db.query(models.tasks).filter(models.tasks.id == id, models.tasks.users_id == current_user["id"]).first()
    if not ans:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid id")
    return _to_task_post(ans)

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_tasks(id: int, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    deli = db.query(models.tasks).filter(models.tasks.id == id, models.tasks.users_id == current_user["id"]).first()
    if not deli:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid id or id does not exist")
    db.delete(deli)
    db.commit()
    return {"message": "Deleted successfully"}

@router.put("/{id}", status_code=status.HTTP_200_OK, response_model=schemas.TasksPost)
def update_tasks(id: int, posts: schemas.Tasks, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    qur = db.query(models.tasks).filter(models.tasks.id == id, models.tasks.users_id == current_user["id"]).first()
    if not qur:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="id does not exist or not found")
    
    if posts.title:
        qur.title = posts.title
    if posts.content or posts.description:
        qur.content = posts.content or posts.description
    if posts.completed is not None:
        qur.completed = posts.completed
    elif posts.is_completed is not None:
        qur.completed = posts.is_completed
    if posts.priority:
        qur.priority = posts.priority
    if posts.due_date is not None:
        qur.due_date = posts.due_date

    db.commit()
    db.refresh(qur)
    return _to_task_post(qur)

@router.patch("/{id}", status_code=status.HTTP_200_OK, response_model=schemas.TasksPost)
def patch_tasks(id: int, posts: schemas.Tasks, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    return update_tasks(id=id, posts=posts, db=db, current_user=current_user)

# Subtask endpoints
@router.get("/{task_id}/subtasks", response_model=List[schemas.SubtaskResponse])
def get_subtasks(task_id: int, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    task = db.query(models.tasks).filter(models.tasks.id == task_id, models.tasks.users_id == current_user["id"]).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    subtasks = db.query(models.Subtask).filter(models.Subtask.task_id == task_id).all()
    return [_to_subtask_response(s) for s in subtasks]

@router.post("/{task_id}/subtasks", status_code=status.HTTP_201_CREATED, response_model=schemas.SubtaskResponse)
def create_subtask(task_id: int, post: schemas.SubtaskCreate, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    task = db.query(models.tasks).filter(models.tasks.id == task_id, models.tasks.users_id == current_user["id"]).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    subtask = models.Subtask(
        task_id=task_id,
        title=post.title,
        content=post.content or "",
        completed=post.completed or False,
        due_date=post.due_date,
    )
    db.add(subtask)
    db.commit()
    db.refresh(subtask)
    return _to_subtask_response(subtask)

@router.put("/subtasks/{subtask_id}", response_model=schemas.SubtaskResponse)
def update_subtask(subtask_id: int, post: schemas.SubtaskCreate, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    subtask = db.query(models.Subtask).join(models.tasks).filter(
        models.Subtask.id == subtask_id,
        models.tasks.users_id == current_user["id"]
    ).first()
    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found")
    if post.title:
        subtask.title = post.title
    if post.content is not None:
        subtask.content = post.content
    if post.completed is not None:
        subtask.completed = post.completed
    db.commit()
    db.refresh(subtask)
    return _to_subtask_response(subtask)

@router.delete("/subtasks/{subtask_id}", status_code=status.HTTP_200_OK)
def delete_subtask(subtask_id: int, db: Session = Depends(database.get_db), current_user=Depends(get_current_user)):
    subtask = db.query(models.Subtask).join(models.tasks).filter(
        models.Subtask.id == subtask_id,
        models.tasks.users_id == current_user["id"]
    ).first()
    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtask not found")
    db.delete(subtask)
    db.commit()
    return {"message": "Subtask deleted successfully"}
