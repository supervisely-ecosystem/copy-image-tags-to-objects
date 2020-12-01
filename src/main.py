import os
import supervisely_lib as sly
from supervisely_lib.annotation.tag_meta import TagApplicableTo

my_app = sly.AppService()

TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
PROJECT_ID = int(os.environ["modal.state.slyProjectId"])

PROJECT = None
RES_PROJECT = None
META: sly.ProjectMeta = None
UI_TAGS = None
UI_CLASSES = None

@my_app.callback("copy_tags")
@sly.timeit
def preprocessing(api: sly.Api, task_id, context, state, app_logger):
    global RES_PROJECT
    RES_PROJECT = api.project.create(WORKSPACE_ID, state["resultProjectName"], change_name_if_conflict=True)
    my_app.logger.info("Result Project is created (name={!r}; id={})".format(RES_PROJECT.name, RES_PROJECT.id))

    api.project.update_meta(RES_PROJECT.id, RES_META.to_json())

    allowed_tags = set()
    for tag, allowed in zip(UI_TAGS, state["tagsSelected"]):
        if allowed:
            allowed_tags.add(tag["name"])

    allowed_classes = set()
    for obj_class, allowed in zip(UI_CLASSES, state["classesSelected"]):
        if allowed:
            allowed_classes.add(obj_class["title"])

    progress = sly.Progress("Processing", PROJECT.images_count, ext_logger=my_app.logger)
    for dataset in api.dataset.get_list(PROJECT.id):
        res_dataset = api.dataset.create(RES_PROJECT.id, dataset.name)
        ds_images = api.image.get_list(dataset.id)
        for batch in sly.batched(ds_images):
            image_ids = [image_info.id for image_info in batch]
            image_names = [image_info.name for image_info in batch]
            image_metas = [image_info.meta for image_info in batch]

            ann_infos = api.annotation.download_batch(dataset.id, image_ids)
            anns = [sly.Annotation.from_json(ann_info.annotation, META) for ann_info in ann_infos]

            original_ids = []
            res_image_names = []
            res_anns = []
            res_metas = []

            for image_id, image_name, image_meta, ann in zip(image_ids, image_names, image_metas, anns):
                tag: sly.Tag = ann.img_tags.get(IMAGE_TAG_NAME)
                if tag is None:
                    my_app.logger.warn("Image {!r} in dataset {!r} doesn't have tag {!r}. Image is skipped"
                                       .format(image_name, dataset.name, IMAGE_TAG_NAME))
                    progress.iter_done_report()
                    continue

                csv_row = CSV_INDEX.get(str(tag.value), None)
                if csv_row is None:
                    my_app.logger.warn(
                        "Match not found (id={}, name={!r}, dataset={!r}, tag_value={!r}). Image is skipped"
                        .format(image_id, image_name, dataset.name, str(tag.value)))
                    progress.iter_done_report()
                    continue

                res_ann = ann.clone()
                res_meta = image_meta.copy()

                if ASSIGN_AS == "tags":
                    res_ann = assign_csv_row_as_tags(image_id, image_name, res_ann, csv_row)
                else:  # metadata
                    res_meta = assign_csv_row_as_metadata(image_id, image_name, image_meta, csv_row)

                original_ids.append(image_id)
                res_image_names.append(image_name)
                res_anns.append(res_ann)
                res_metas.append(res_meta)

            res_image_infos = api.image.upload_ids(res_dataset.id, res_image_names, original_ids, metas=res_metas)
            res_image_ids = [image_info.id for image_info in res_image_infos]
            api.annotation.upload_anns(res_image_ids, res_anns)
            progress.iters_done_report(len(res_image_ids))

    api.task.set_output_project(my_app.task_id, RES_PROJECT.id, RES_PROJECT.name)


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
    return UI_CLASSES, classes_selected


def main():
    global PROJECT, META

    api = sly.Api.from_env()
    PROJECT = api.project.get_info_by_id(PROJECT_ID)
    META = sly.ProjectMeta.from_json(api.project.get_meta(PROJECT_ID))

    res_project_name = PROJECT.name + " (objects with tags)"

    _, tags_selected, tags_disabled, disabled_message = prepare_ui_tags()
    _, classes_selected = prepare_ui_classes()

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
        "progress": 0
    }

    state = {
        "tagsSelected": tags_selected,
        "tagsDisabled": tags_disabled,
        "classesSelected": classes_selected,
        "resultProjectName": res_project_name,
        "resolve": "skip"
    }

    # Run application service
    my_app.run(data=data, state=state)


if __name__ == "__main__":
    sly.main_wrapper("main", main)