<div align="center" markdown>
<img src="https://user-images.githubusercontent.com/106374579/183398752-8e83aaef-607c-4755-baa1-749f6c617d49.png"/>

# Copy Image Tags To Objects

<p align="center">
  <a href="#Overview">Overview</a> •
  <a href="#How-To-Run">How To Run</a>
</p>


[![](https://img.shields.io/badge/supervisely-ecosystem-brightgreen)](../../../../supervisely-ecosystem/copy-image-tags-to-objects)
[![](https://img.shields.io/badge/slack-chat-green.svg?logo=slack)](https://supervisely.com/slack)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/supervisely-ecosystem/copy-image-tags-to-objects)
[![views](https://app.supervisely.com/img/badges/views/supervisely-ecosystem/copy-image-tags-to-objects.png)](https://supervisely.com)
[![runs](https://app.supervisely.com/img/badges/runs/supervisely-ecosystem/copy-image-tags-to-objects.png)](https://supervisely.com)

</div>

## Overview

This app copies selected tags to objects of selected classes (by default all classes and tags are selected). New project is created. 

1. Input project info
2. Define the name of result project
3. Choose how to resolve conflicts with existing tags: skip existing tag, replace it or raise error
4. Choose what tags have to be copied
5. Select classes: tags are assigned to all objects of selected classes, objects of other classes will be copied without changes
6. Output section: after you press `Run` button, progress will appear. Then result project will be displayed.
7. App shuts down automatically

<img src="https://i.imgur.com/jBVHcxj.png"/>

## How To Run

1. Add app to your team if it is not there
2. Run this app from the context menu of project: `Run App` -> `Copy image tags to objects`

