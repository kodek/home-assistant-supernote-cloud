# home-assistant-supernote-cloud

Home Assistant Custom Component for accessing your Supernote Private Cloud instance. This is meant work with the excellent Ratta Supernote products.

This custom component authenticates with your local private cloud server
and provides access to the contents of your notebooks through the media
player.

The motivation is to use with [Journal Assistant](https://github.com/allenporter/home-assistant-journal-assistant) and [Supernote LLM](https://github.com/allenporter/supernote-llm/).

## Media Source

Notebooks are exposed as a [Media Source](https://www.home-assistant.io/integrations/media_source/). This can be
used to browse contents of the notebooks and view notebook pages as `.png` files. The media source
will query the Supernote Private Cloud API to look for backups and let you
browse them directly.

## Development

The client library used for accessing Supernote Contents:

- http://github.com/allenporter/supernote-lite/

With prior art from these libraries:

- https://github.com/bwhitman/supernote-cloud-python/
- https://github.com/adrianba/supernote-cloud-api/
- https://github.com/colingourlay/supernote-cloud-api/

## Local Development

### Pre-requisites

```bash
$ script/bootstrap
$ script/setup
```

### Run Home Assistant

From then on run home assistant:

```bash
$ script/server
```
