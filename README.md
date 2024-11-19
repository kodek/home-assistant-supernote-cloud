# home-assistant-supernote-cloud

Home Assistant Custom Component dedicated to the excellent Ratta Supernote products.

This custom component efficiently synchronizes a backup of your notebook to your
local storage and exposes the contents through the media player.

The motivation is to use with [Journal Assistant](https://github.com/allenporter/home-assistant-journal-assistant) and [Supernote LLM](https://github.com/allenporter/supernote-llm/).

## Media Source

Notebook backups are exposed as a [Media Source](https://www.home-assistant.io/integrations/media_source/). This can be
used to browse contents of the backups and view notebook pages as `.png` files. The media source
will query the Supernote Cloud API to look for backups, and caches responses for
one hour to reduce load on the server. Any notebook contents md5 hashes are compared
to the contents on the server and sync'd down to local disk when there is a difference.


## Development

Library for efficient backup based on:

- https://github.com/bwhitman/supernote-cloud-python/
- https://github.com/adrianba/supernote-cloud-api/
- https://github.com/colingourlay/supernote-cloud-api/

### Development plan

- [x] Authentication library and configuration flow
- [x] Media player skeleton of directory contents
- [x] Tests for store
- [x] read cached meta.json from disk
- [x] tests for png fetching
- [x] Syncing of note contents
- [x] cache backup metadata on disk to reduce api calls
- [ ] handle non .note files
- [x] Extracting png content
- [x] async iterator to page through contents
- [x] concurrency fixes
- [x] fully async io
- [ ] invalidate .png files when the notebook contents chnage
