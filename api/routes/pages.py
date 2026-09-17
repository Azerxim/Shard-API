import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

from ..core import utils, documentation

# Pages HTML et fichiers techniques de l'API (hors /api, sauf /api/version/)
router = APIRouter()

templates = Jinja2Templates(directory=os.path.join(utils.ROOT_DIR, "templates"))

FAVICON_URL = "/assets/images/favicon_shard.ico"


def page_context(request: Request, **extra):
    return {
        "request": request,
        "name": utils.CONFIG['api']['name'],
        "version": utils.VERSION,
        "hostname": utils.HOSTNAME,
        **extra,
    }

# -----------------------------------------------
#region Fichiers techniques

@router.get('/favicon_shard.ico', include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(utils.ROOT_DIR, "assets", "images", "favicon_shard.ico"))

@router.get('/robots.txt', include_in_schema=False)
async def robots():
    return FileResponse(os.path.join(utils.ROOT_DIR, "robots.txt"), media_type='text/plain')

@router.get('/sitemap.xml', include_in_schema=False)
async def sitemap(request: Request):
    """Generate sitemap.xml dynamically"""
    base_url = str(request.base_url).rstrip('/')

    # Define routes with their priority and change frequency
    routes = [
        {'loc': '/', 'priority': '1.0', 'changefreq': 'weekly'},
        {'loc': '/docs', 'priority': '0.8', 'changefreq': 'weekly'},
        {'loc': '/wrapper', 'priority': '0.6', 'changefreq': 'monthly'},
        {'loc': '/redoc', 'priority': '0.6', 'changefreq': 'monthly'},
    ]

    # Build XML sitemap
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for route in routes:
        xml_content += '  <url>\n'
        xml_content += f'    <loc>{base_url}{route["loc"]}</loc>\n'
        xml_content += f'    <changefreq>{route["changefreq"]}</changefreq>\n'
        xml_content += f'    <priority>{route["priority"]}</priority>\n'
        xml_content += '  </url>\n'

    xml_content += '</urlset>'

    return Response(content=xml_content, media_type='application/xml')

#endregion
# -----------------------------------------------
#region Pages

@router.get("/", response_class=HTMLResponse)
def html_main(request: Request):
    return templates.TemplateResponse("landing.html", page_context(request))

@router.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def documentation_html(request: Request):
    doc = documentation.get_documentation()
    if doc is None:
        raise HTTPException(status_code=404, detail="DOCUMENTATION.md introuvable")
    return templates.TemplateResponse("documentation.html", page_context(request, doc=doc))

@router.get("/documentation.md", include_in_schema=False)
async def documentation_markdown():
    if not os.path.exists(documentation.DOC_PATH):
        raise HTTPException(status_code=404, detail="DOCUMENTATION.md introuvable")
    return FileResponse(documentation.DOC_PATH, media_type="text/markdown; charset=utf-8")

@router.get("/swagger", response_class=HTMLResponse, include_in_schema=False)
async def custom_swagger_ui_html(request: Request):
    swagger_ui = get_swagger_ui_html(
        openapi_url=request.app.openapi_url,
        title=f"{utils.CONFIG['api']['name']} - Documentation",
        swagger_favicon_url=FAVICON_URL
    )
    return templates.TemplateResponse("docs.html", page_context(request, swagger_ui_html=swagger_ui.body.decode()))

@router.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
async def redoc_html(request: Request):
    redoc_ui = get_redoc_html(
        openapi_url=request.app.openapi_url,
        title=f"{utils.CONFIG['api']['name']} - ReDoc Documentation",
        redoc_favicon_url=FAVICON_URL
    )
    return templates.TemplateResponse("redoc.html", page_context(request, redoc_ui_html=redoc_ui.body.decode()))

#endregion
# -----------------------------------------------
#region Version

@router.get("/api/version/")
def app_version():
    result = {'name': utils.CONFIG['api']['name'], 'version': utils.VERSION, 'version_dev': utils.VERSION_DEV, 'version_short': utils.VERSION_SHORT, 'hostname': utils.HOSTNAME}
    return JSONResponse(content=jsonable_encoder(result))

#endregion
# -----------------------------------------------
