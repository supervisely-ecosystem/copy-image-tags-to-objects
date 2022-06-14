import os
import supervisely as sly
from supervisely.annotation.tag_meta import TagApplicableTo
from supervisely.app.v1.app_service import AppService

my_app: AppService = AppService()

TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
PROJECT_ID = int(os.environ["modal.state.slyProjectId"])

PROJECT = None
RES_PROJECT = None
META: sly.ProjectMeta = None
UI_TAGS = None
UI_CLASSES = None


def add_tags_to_label(label: sly.Label, allowed_tags: set, image_tags: sly.TagCollection, resolve: str):
    new_tags = []
    for tag in image_tags:
        tag: sly.Tag
        if tag.name not in allowed_tags:
            continue
        else:
            existing_tag = label.tags.get(tag.name)
            if existing_tag is None:
                new_tags.append(tag)
            else:
                if resolve == "skip":
                    new_tags.append(existing_tag)
                elif resolve == "replace":
                    new_tags.append(tag)
                elif resolve == "raise error":
                    raise RuntimeError("Object already has tag {!r}".format(tag.name))

    for tag in label.tags:
        if tag.name not in allowed_tags:
            new_tags.append(tag)

    return label.clone(tags=sly.TagCollection(new_tags))


@my_app.callback("copy_tags")
@sly.timeit
def copy_tags(api: sly.Api, task_id, context, state, app_logger):
    global RES_PROJECT
    selected_tags = state["tagsSelected"].copy()
    selected_classes = state["classesSelected"].copy()

    fields = [
        {"field": "state.tagsDisabled", "payload": [True] * len(selected_tags)},
        {"field": "state.classesDisabled", "payload": [True] * len(selected_classes)},
        {"field": "data.started", "payload": True}
    ]
    api.task.set_fields(task_id, fields)

    RES_PROJECT = api.project.create(WORKSPACE_ID, state["resultProjectName"], change_name_if_conflict=True)
    app_logger.info("Result Project is created (name={!r}; id={})".format(RES_PROJECT.name, RES_PROJECT.id))

    api.project.update_meta(RES_PROJECT.id, META.to_json())

    allowed_tags = set()
    for tag, allowed in zip(UI_TAGS, selected_tags):
        if allowed:
            allowed_tags.add(tag["name"])

    allowed_classes = set()
    for obj_class, allowed in zip(UI_CLASSES, selected_classes):
        if allowed:
            allowed_classes.add(obj_class["title"])

    progress = sly.Progress("Processing", PROJECT.images_count, ext_logger=app_logger)
    for dataset in api.dataset.get_list(PROJECT.id):
        res_dataset = api.dataset.create(RES_PROJECT.id, dataset.name)
        ds_images = api.image.get_list(dataset.id)
        for batch in sly.batched(ds_images):
            image_ids = [image_info.id for image_info in batch]
            image_names = [image_info.name for image_info in batch]
            image_metas = [image_info.meta for image_info in batch]

            ann_infos = api.annotation.download_batch(dataset.id, image_ids)
            anns = [sly.Annotation.from_json(ann_info.annotation, META) for ann_info in ann_infos]

            res_anns = []
            for ann in anns:
                new_labels = []
                for label in ann.labels:
                    if label.obj_class.name not in allowed_classes:
                        new_labels.append(label.clone())
                    else:
                        new_labels.append(add_tags_to_label(label, allowed_tags, ann.img_tags, state["resolve"]))

                if state["imageTagAction"] == "keep":
                    res_anns.append(ann.clone(labels=new_labels))
                elif state["imageTagAction"] == "remove":
                    res_anns.append(ann.clone(img_tags=sly.TagCollection(), labels=new_labels))
                else:
                    raise ValueError(f"Unknown imageTagAction: {state['imageTagAction']}")

            res_image_infos = api.image.upload_ids(res_dataset.id, image_names, image_ids, metas=image_metas)
            res_image_ids = [image_info.id for image_info in res_image_infos]
            api.annotation.upload_anns(res_image_ids, res_anns)

            progress.iters_done_report(len(res_image_ids))
            fields = [
                {"field": "data.progress", "payload": int(progress.current * 100 / PROJECT.images_count)},
                {"field": "data.progressCurrent", "payload": progress.current}
            ]
            api.task.set_fields(task_id, fields)

    api.task.set_output_project(my_app.task_id, RES_PROJECT.id, RES_PROJECT.name)

    # to get correct "reference_image_url"
    res_project = api.project.get_info_by_id(RES_PROJECT.id)
    fields = [
        {"field": "data.resultProject", "payload": RES_PROJECT.name},
        {"field": "data.resultProjectId", "payload": RES_PROJECT.id},
        {"field": "data.resultProjectPreviewUrl",
         "payload": api.image.preview_url(res_project.reference_image_url, 100, 100)},
        #{"field": "data.started", "payload": False},
        {"field": "data.finished", "payload": False},
    ]
    api.task.set_fields(task_id, fields)
    my_app.stop()


def prepare_ui_tags():
    global UI_TAGS

    UI_TAGS = []
    tags_selected = []
    tags_disabled = []
    disabled_message = []

    for tag_meta in META.tag_metas:
        tag_meta: sly.TagMeta
        cur_json = tag_meta.to_json()
        UI_TAGS.append(cur_json)
        if tag_meta.applicable_to == TagApplicableTo.ALL:
            tags_selected.append(True)
            tags_disabled.append(False)
            disabled_message.append("")
        elif tag_meta.applicable_to == TagApplicableTo.IMAGES_ONLY:
            tags_selected.append(False)
            tags_disabled.append(True)
            disabled_message.append("applicable only to images")
        elif tag_meta.applicable_to == TagApplicableTo.OBJECTS_ONLY:
            tags_selected.append(False)
            tags_disabled.append(True)
            disabled_message.append("applicable only to objects")
    return UI_TAGS, tags_selected, tags_disabled, disabled_message


def prepare_ui_classes():
    global UI_CLASSES
    UI_CLASSES = []
    classes_selected = []
    for obj_class in META.obj_classes:
        obj_class: sly.ObjClass
        UI_CLASSES.append(obj_class.to_json())
        classes_selected.append(True)
    return UI_CLASSES, classes_selected, [False] * len(classes_selected)


def main():
    global PROJECT, META

    api = sly.Api.from_env()
    PROJECT = api.project.get_info_by_id(PROJECT_ID)
    META = sly.ProjectMeta.from_json(api.project.get_meta(PROJECT_ID))

    res_project_name = PROJECT.name + " (objects with tags)"

    _, tags_selected, tags_disabled, disabled_message = prepare_ui_tags()
    _, classes_selected, classes_disabled = prepare_ui_classes()

    data = {
        "projectId": PROJECT.id,
        "projectName": PROJECT.name,
        "projectPreviewUrl": api.image.preview_url(PROJECT.reference_image_url, 100, 100),
        "tags": UI_TAGS,
        "tagsDisabledMessage": disabled_message,
        "classes": UI_CLASSES,
        "resultProjectId": "",
        "resultProjectPreviewUrl": "",
        "started": False,
        "finished": False,
        "progress": 0,
        "progressCurrent": 0,
        "progressTotal": PROJECT.images_count
    }

    state = {
        "tagsSelected": tags_selected,
        "tagsDisabled": tags_disabled,
        "classesSelected": classes_selected,
        "classesDisabled": classes_disabled,
        "resultProjectName": res_project_name,
        "resolve": "skip",
        "imageTagAction": "keep",
    }

    # Run application service
    my_app.run(data=data, state=state)


if __name__ == "__main__":
    sly.main_wrapper("main", main)
