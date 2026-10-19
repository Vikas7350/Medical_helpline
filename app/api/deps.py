from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.security import verify_admin_access
from app.database.session import get_db

# Dependency shortcuts
DatabaseSession = Depends(get_db)
AdminAuth = Depends(verify_admin_access)
