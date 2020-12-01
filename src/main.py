import os
import supervisely_lib as sly
from supervisely_lib.annotation.tag_meta import TagApplicableTo

my_app = sly.AppService()

TEAM_ID = int(os.environ['context.teamId'])
WORKSPACE_ID = int(os.environ['context.workspaceId'])
PROJECT_ID = int(os.environ["modal.state.slyProjectId"])

PROJECT = None
RES_PROJECT = None
RES_PROJECT_NAME = None
META: sly.ProjectMeta = None


@my_app.callback("generate")
@sly.timeit
def generate_random_string(api: sly.Api, task_id, context, state, app_logger):
    rand_string = ''.join((random.choice(string.ascii_letters + string.digits)) for _ in range(LENGTH))
    rand_string = state["prefix"] + rand_string
    api.task.set_field(task_id, "data.randomString", rand_string)


@my_app.callback("preprocessing")
@sly.timeit
def preprocessing(api: sly.Api, task_id, context, state, app_logger):
    sly.logger.info("do something here")


def prepare_ui_tags():
    tags = []
    tags_selected = []
    tags_disabled = []
    disabled_message = []

    for tag_meta in META.tag_metas:
        tag_meta: sly.TagMeta
        cur_json = tag_meta.to_json()
        tags.append(cur_json)
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
    return tags, tags_selected, tags_disabled, disabled_message


def prepare_ui_classes():
    classes = []
    classes_selected = []
    for obj_class in META.obj_classes:
        obj_class: sly.ObjClass
        classes.append(obj_class.to_json())
        classes_selected.append(True)
    return classes, classes_selected


def main():
    global PROJECT, META, RES_PROJECT_NAME

    api = sly.Api.from_env()
    PROJECT = api.project.get_info_by_id(PROJECT_ID)
    META = sly.ProjectMeta.from_json(api.project.get_meta(PROJECT_ID))

    RES_PROJECT_NAME = PROJECT.name + " (objects with tags)"

    tags, tags_selected, tags_disabled, disabled_message = prepare_ui_tags()
    classes, classes_selected = prepare_ui_classes()

    data = {
        "projectId": PROJECT.id,
        "projectName": PROJECT.name,
        "projectPreviewUrl": api.image.preview_url(PROJECT.reference_image_url, 100, 100),
        "tags": tags,
        "tagsDisabledMessage": disabled_message,
        "classes": classes,
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
        "resultProjectName": RES_PROJECT_NAME,
    }

    # Run application service
    my_app.run(data=data, state=state, initial_events=[{"command": "preprocessing"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)