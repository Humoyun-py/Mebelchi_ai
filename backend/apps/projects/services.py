from .models import Project, ProjectActivity


def log(project: Project, action: str, detail: str = ""):
    ProjectActivity.objects.create(project=project, action=action, detail=detail[:255])


def duplicate(project: Project) -> Project:
    """Copies the project and its saved designs (calculations/cutting lists are copied by value)."""
    from apps.calculations.models import Calculation
    from apps.cutting_lists.models import CuttingList, CuttingPart
    from apps.designs.models import Design
    new = Project.objects.get(pk=project.pk)
    new.pk = None
    new.name = f"{project.name} (copy)"[:160]
    new.status, new.pinned = Project.Status.ACTIVE, False
    new.save()
    for c in project.calculations.all():
        Calculation.objects.create(owner=c.owner, project=new, name=c.name, kind=c.kind, inputs=c.inputs, result=c.result)
    for d in project.designs.all():
        Design.objects.create(owner=d.owner, project=new, kind=d.kind, name=d.name, config=d.config, room_image=d.room_image)
    for cl in project.cutting_lists.all():
        parts = list(cl.parts.all())
        cl.pk = None
        cl.project = new
        cl.save()
        CuttingPart.objects.bulk_create([CuttingPart(cutting_list=cl, name=p.name, width=p.width, height=p.height, thickness=p.thickness,
                                                     quantity=p.quantity, material=p.material, can_rotate=p.can_rotate, edge_w=p.edge_w,
                                                     edge_h=p.edge_h, edge_note=p.edge_note) for p in parts])
    log(new, "created", f"Duplicated from '{project.name}'")
    return new
