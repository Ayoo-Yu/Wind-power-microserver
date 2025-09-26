"""
Report template management router for Report Service
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Form
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import TemplateCreate, TemplateUpdate, TemplateResponse
from ..services import template_service
from ..exceptions import TemplateNotFoundException, ValidationException
from ..utils import get_logger, create_success_response, create_error_response

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.post("/", response_model=TemplateResponse)
async def create_template(
    template_data: TemplateCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new report template."""
    try:
        logger.info(f"Creating template: {template_data.name} (type: {template_data.report_type})")

        template = await template_service.create_template(db, template_data)

        return template

    except ValidationException as e:
        logger.error(f"Validation error creating template: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail="Failed to create template")


@router.get("/", response_model=Dict[str, Any])
async def list_templates(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db)
):
    """Get list of report templates."""
    try:
        logger.info(f"Listing templates with filters: type={report_type}, active={is_active}")

        # Build filters
        filters = {}
        if report_type:
            filters["report_type"] = report_type
        if is_active is not None:
            filters["is_active"] = is_active

        # Get templates from service
        templates, total = await template_service.list_templates(
            db, skip=skip, limit=limit, filters=filters
        )

        return create_success_response(
            "Templates retrieved successfully",
            {
                "templates": templates,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        )

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list templates")


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str = Path(..., description="Template ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific template by ID."""
    try:
        logger.info(f"Getting template: {template_id}")

        template = await template_service.get_template(db, template_id)
        if not template:
            raise TemplateNotFoundException(template_id)

        return template

    except TemplateNotFoundException as e:
        logger.error(f"Template not found: {template_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get template")


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str = Path(..., description="Template ID"),
    template_data: TemplateUpdate = ...,
    db: AsyncSession = Depends(get_db)
):
    """Update a template."""
    try:
        logger.info(f"Updating template: {template_id}")

        template = await template_service.update_template(db, template_id, template_data)
        if not template:
            raise TemplateNotFoundException(template_id)

        return template

    except TemplateNotFoundException as e:
        logger.error(f"Template not found: {template_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.error(f"Validation error updating template: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update template")


@router.delete("/{template_id}")
async def delete_template(
    template_id: str = Path(..., description="Template ID"),
    db: AsyncSession = Depends(get_db)
):
    """Delete a template."""
    try:
        logger.info(f"Deleting template: {template_id}")

        success = await template_service.delete_template(db, template_id)
        if not success:
            raise TemplateNotFoundException(template_id)

        return create_success_response(f"Template {template_id} deleted successfully")

    except TemplateNotFoundException as e:
        logger.error(f"Template not found: {template_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete template")


@router.post("/{template_id}/duplicate")
async def duplicate_template(
    template_id: str = Path(..., description="Template ID"),
    new_name: Optional[str] = Query(None, description="Name for the duplicated template"),
    db: AsyncSession = Depends(get_db)
):
    """Duplicate an existing template."""
    try:
        logger.info(f"Duplicating template: {template_id}")

        new_template = await template_service.duplicate_template(db, template_id, new_name)
        if not new_template:
            raise TemplateNotFoundException(template_id)

        return create_success_response(
            f"Template {template_id} duplicated successfully",
            {"new_template_id": new_template.id, "name": new_template.name}
        )

    except TemplateNotFoundException as e:
        logger.error(f"Template not found: {template_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error duplicating template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to duplicate template")


@router.put("/{template_id}/activate")
async def activate_template(
    template_id: str = Path(..., description="Template ID"),
    db: AsyncSession = Depends(get_db)
):
    """Activate a template."""
    try:
        logger.info(f"Activating template: {template_id}")

        template = await template_service.activate_template(db, template_id)
        if not template:
            raise TemplateNotFoundException(template_id)

        return create_success_response(f"Template {template_id} activated successfully")

    except TemplateNotFoundException as e:
        logger.error(f"Template not found: {template_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error activating template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate template")


@router.put("/{template_id}/deactivate")
async def deactivate_template(
    template_id: str = Path(..., description="Template ID"),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate a template."""
    try:
        logger.info(f"Deactivating template: {template_id}")

        template = await template_service.deactivate_template(db, template_id)
        if not template:
            raise TemplateNotFoundException(template_id)

        return create_success_response(f"Template {template_id} deactivated successfully")

    except TemplateNotFoundException as e:
        logger.error(f"Template not found: {template_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deactivating template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to deactivate template")


@router.get("/types/available")
async def get_available_template_types():
    """Get available template types and their configurations."""
    try:
        logger.info("Getting available template types")

        template_types = await template_service.get_available_template_types()

        return create_success_response(
            "Available template types retrieved successfully",
            {"template_types": template_types}
        )

    except Exception as e:
        logger.error(f"Error getting template types: {e}")
        raise HTTPException(status_code=500, detail="Failed to get template types")


@router.post("/{template_id}/preview")
async def preview_template(
    template_id: str = Path(..., description="Template ID"),
    sample_data: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db)
):
    """Preview a template with sample data."""
    try:
        logger.info(f"Previewing template: {template_id}")

        preview = await template_service.preview_template(db, template_id, sample_data)
        if not preview:
            raise TemplateNotFoundException(template_id)

        return create_success_response("Template preview generated successfully", preview)

    except TemplateNotFoundException as e:
        logger.error(f"Template not found: {template_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error previewing template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to preview template")


@router.get("/defaults/list")
async def get_default_templates():
    """Get built-in default templates."""
    try:
        logger.info("Getting default templates")

        defaults = await template_service.get_default_templates()

        return create_success_response(
            "Default templates retrieved successfully",
            {"default_templates": defaults}
        )

    except Exception as e:
        logger.error(f"Error getting default templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to get default templates")


@router.post("/import")
async def import_template(
    name: str = Form(..., description="Template name"),
    report_type: str = Form(..., description="Report type"),
    template_content: str = Form(..., description="Template content (HTML)"),
    css_styles: Optional[str] = Form(None, description="CSS styles"),
    header_template: Optional[str] = Form(None, description="Header template"),
    footer_template: Optional[str] = Form(None, description="Footer template"),
    default_parameters: Optional[str] = Form(None, description="JSON default parameters"),
    default_charts: Optional[str] = Form(None, description="JSON default charts configuration"),
    description: Optional[str] = Form(None, description="Template description"),
    db: AsyncSession = Depends(get_db)
):
    """Import a template from form data."""
    try:
        logger.info(f"Importing template: {name} (type: {report_type})")

        # Parse JSON fields
        parameters = {}
        if default_parameters:
            try:
                parameters = json.loads(default_parameters)
            except json.JSONDecodeError:
                raise ValidationException("Invalid JSON for default parameters")

        charts = []
        if default_charts:
            try:
                charts = json.loads(default_charts)
            except json.JSONDecodeError:
                raise ValidationException("Invalid JSON for default charts")

        # Create template data
        template_data = TemplateCreate(
            name=name,
            report_type=report_type,
            template_content=template_content,
            css_styles=css_styles,
            header_template=header_template,
            footer_template=footer_template,
            default_parameters=parameters,
            default_charts=charts,
            description=description
        )

        template = await template_service.create_template(db, template_data)

        return create_success_response(
            "Template imported successfully",
            {"template_id": template.id, "name": template.name}
        )

    except ValidationException as e:
        logger.error(f"Validation error importing template: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing template: {e}")
        raise HTTPException(status_code=500, detail="Failed to import template")


@router.get("/{template_id}/export")
async def export_template(
    template_id: str = Path(..., description="Template ID"),
    db: AsyncSession = Depends(get_db)
):
    """Export a template for backup or sharing."""
    try:
        logger.info(f"Exporting template: {template_id}")

        export_data = await template_service.export_template(db, template_id)
        if not export_data:
            raise TemplateNotFoundException(template_id)

        return create_success_response("Template exported successfully", export_data)

    except TemplateNotFoundException as e:
        logger.error(f"Template not found: {template_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to export template")